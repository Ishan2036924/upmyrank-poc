"""
Memory summarizer — writes memory, keeps it fresh over time.

Entry points:
    summarize_session()       → compress a study session into 1 summary string
                                  BLOCKING — called synchronously on /session/end
    update_hot_context()      → push new summary to Redis hot:{student_id} list
    maybe_compress_profile()  → rewrite student_memory.compressed_profile every 5 sessions
                                  BACKGROUND — never block session end on this
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Optional

import asyncpg
import openai

from app.config import settings

logger = logging.getLogger(__name__)


# ── Session summarizer ────────────────────────────────────────────────────────

async def summarize_session(
    study_session_id: str,
    db: asyncpg.Pool,
    openai_client: Optional[openai.AsyncOpenAI] = None,
) -> Optional[str]:
    """
    Compress all doubt_block summaries for a study session into one short paragraph.

    Called BLOCKING on /session/end — do not fire-and-forget.
    Returns the summary string, or None if insufficient data or failure.
    """
    try:
        session_uuid = uuid.UUID(study_session_id)
    except ValueError:
        logger.warning("summarize_session: invalid study_session_id %s", study_session_id)
        return None

    try:
        rows = await db.fetch(
            """
            SELECT db.topic, db.summary
            FROM doubt_blocks db
            WHERE db.study_session_id = $1
              AND db.summary IS NOT NULL
            ORDER BY db.started_at ASC
            """,
            session_uuid,
        )
    except Exception as exc:
        logger.error("summarize_session: DB fetch failed: %s", exc)
        return None

    if not rows:
        return None

    # Extract unique topics
    topics = list(dict.fromkeys(r["topic"] for r in rows if r["topic"]))
    summaries_text = "\n".join(
        f"[{r['topic'] or 'Unknown'}] {r['summary']}" for r in rows
    )

    # Build summary via GPT-4o-mini (cheap model only)
    client = openai_client or openai.AsyncOpenAI(api_key=settings.openai_api_key)
    summary: Optional[str] = None

    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.model_cheap,
                max_tokens=120,
                temperature=0.3,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are summarizing a student's physics study session for future "
                            "context injection into an AI tutor. Be specific about errors and "
                            "struggles. Max 80 words."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Summarize this session from these doubt summaries:\n"
                            + summaries_text
                        ),
                    },
                ],
            ),
            timeout=3.0,
        )
        summary = resp.choices[0].message.content.strip()
    except asyncio.TimeoutError:
        logger.error("summarize_session: LLM timeout (3s) for session %s", study_session_id)
        return None
    except Exception as exc:
        logger.error("summarize_session: LLM call failed: %s", exc)
        return None

    # Write back to Postgres
    try:
        await db.execute(
            """
            UPDATE study_sessions
            SET session_summary = $1,
                topics_covered  = $2
            WHERE study_session_id = $3
            """,
            summary,
            topics,
            session_uuid,
        )
    except Exception as exc:
        logger.error("summarize_session: DB write failed: %s", exc)
        # Still return the summary — the write failure is non-fatal for the caller

    return summary


# ── Redis hot context ─────────────────────────────────────────────────────────

async def update_hot_context(student_id: str, new_summary: str) -> None:
    """
    Push new_summary to the Redis hot context list for this student.

    Maintains a rolling window of the last 2 session summaries.
    TTL: 48 hours. Redis failures are always silent.
    """
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        key = f"hot:{student_id}"

        raw = await r.get(key)
        items: list[str] = []
        if raw:
            try:
                items = json.loads(raw)
                if not isinstance(items, list):
                    items = []
            except Exception:
                items = []

        # Prepend new summary, keep only last 2
        items = [new_summary] + items
        items = items[:2]

        await r.set(key, json.dumps(items), ex=172800)  # 48 hours
        await r.aclose()
        logger.info("Hot context updated for student %s", student_id)
    except Exception as exc:
        logger.warning("update_hot_context: Redis write failed (non-fatal): %s", exc)


# ── Profile compressor ────────────────────────────────────────────────────────

async def maybe_compress_profile(
    student_id: str,
    db: asyncpg.Pool,
    openai_client: Optional[openai.AsyncOpenAI] = None,
) -> None:
    """
    Rewrite the student's compressed_profile every 5 sessions.

    BACKGROUND task — never block session end on this.
    Silently skips if not enough data or any failure occurs.
    """
    try:
        student_uuid = uuid.UUID(student_id)
    except ValueError:
        return

    try:
        mem_row = await db.fetchrow(
            "SELECT sessions_since_compress, compressed_profile FROM student_memory WHERE student_id = $1",
            student_uuid,
        )

        # Upsert row if missing (e.g. student pre-dates the migration)
        if mem_row is None:
            await db.execute(
                """
                INSERT INTO student_memory (student_id)
                VALUES ($1)
                ON CONFLICT (student_id) DO NOTHING
                """,
                student_uuid,
            )
            return  # No data yet — nothing to compress

        sessions_since = (mem_row["sessions_since_compress"] or 0) + 1
        existing_profile = mem_row["compressed_profile"] or ""

        # Always increment the counter
        await db.execute(
            "UPDATE student_memory SET sessions_since_compress = $1 WHERE student_id = $2",
            sessions_since, student_uuid,
        )

        if sessions_since < 5:
            return  # Not time to compress yet

        # Fetch last 10 session summaries
        summary_rows = await db.fetch(
            """
            SELECT session_summary FROM study_sessions
            WHERE student_id = $1
              AND session_summary IS NOT NULL
            ORDER BY started_at DESC
            LIMIT 10
            """,
            student_uuid,
        )
        summaries = [r["session_summary"] for r in summary_rows]

        if len(summaries) < 3:
            return  # Not enough data yet

        summaries_text = "\n".join(f"- {s}" for s in summaries)
        client = openai_client or openai.AsyncOpenAI(api_key=settings.openai_api_key)

        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.model_cheap,
                max_tokens=160,
                temperature=0.3,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You maintain a rolling student profile for an AI Physics tutor. "
                            "Update it to reflect the current state. Max 120 words. "
                            "Be specific about patterns, errors, improvements."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Existing profile:\n{existing_profile or 'No profile yet'}\n\n"
                            f"Last 10 sessions:\n{summaries_text}\n\n"
                            "Write an updated profile paragraph."
                        ),
                    },
                ],
            ),
            timeout=5.0,
        )
        new_profile = resp.choices[0].message.content.strip()

        await db.execute(
            """
            UPDATE student_memory
            SET compressed_profile      = $1,
                sessions_since_compress = 0,
                profile_last_updated    = NOW()
            WHERE student_id = $2
            """,
            new_profile, student_uuid,
        )
        logger.info("Compressed profile updated for student %s", student_id)

    except asyncio.TimeoutError:
        logger.error("maybe_compress_profile: LLM timeout for student %s", student_id)
    except Exception as exc:
        logger.error("maybe_compress_profile: failed for student %s: %s", student_id, exc)
