"""
Memory context builder — reads the 3-layer student memory and produces a
fixed-size context bundle for injection into the Socratic engine.

Entry points:
    build_context_bundle()      → fetch and assemble raw bundle dict
    format_context_for_prompt() → render bundle to a ≤350-token string
    update_error_fingerprint()  → decay/reinforce per-concept error strengths
    update_forgetting_rate()    → adjust per-concept Ebbinghaus decay rate
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

# Hard token cap enforced by tiktoken
_MAX_TOKENS = 350
_ENCODING_NAME = "cl100k_base"

# Lazy-initialise tiktoken encoder (import is fast but we avoid module-level
# side effects in case the package is missing in test environments)
_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        import tiktoken
        _encoder = tiktoken.get_encoding(_ENCODING_NAME)
    return _encoder


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to at most max_tokens tokens, preserving whole words."""
    enc = _get_encoder()
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return enc.decode(tokens[:max_tokens])


# ── Redis helper ──────────────────────────────────────────────────────────────

async def _get_hot_context(student_id: str) -> list[str]:
    """
    Read the last 2 session summaries from Redis.
    Returns empty list on any failure — Redis is always optional.
    """
    try:
        import redis.asyncio as aioredis
        from app.config import settings
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        raw = await r.get(f"hot:{student_id}")
        await r.aclose()
        if raw:
            data = json.loads(raw)
            if isinstance(data, list):
                return data[:2]
    except Exception as exc:
        logger.warning("Redis hot context read failed (non-fatal): %s", exc)
    return []


# ── Main builder ──────────────────────────────────────────────────────────────

async def build_context_bundle(student_id: str, db: asyncpg.Pool) -> dict:
    """
    Fetch and assemble the 3-layer context bundle for a student.

    Returns:
    {
        "compressed_profile": str | None,
        "hot_context":        list[str],   # max 2 items
        "weak_concepts":      list[dict],  # top 5 weakest
    }

    Never raises — always returns a valid (possibly empty) bundle.
    """
    try:
        student_uuid = uuid.UUID(student_id)
    except ValueError:
        logger.warning("build_context_bundle: invalid student_id %s", student_id)
        return {"compressed_profile": None, "hot_context": [], "weak_concepts": []}

    # ── Layer 1: Redis hot context ─────────────────────────────────────────────
    hot_context = await _get_hot_context(student_id)

    # ── Layer 2: Postgres compressed profile + persona ────────────────────────
    compressed_profile: Optional[str] = None
    persona_summary: Optional[str] = None
    persona_sessions_ago: int = 0
    try:
        row = await db.fetchrow(
            """
            SELECT compressed_profile, persona_profile, persona_profile_updated_at
            FROM student_memory WHERE student_id = $1
            """,
            student_uuid,
        )
        if row:
            compressed_profile = row["compressed_profile"]

            # Extract persona_summary text from the persona_profile JSONB
            raw_persona = row["persona_profile"]
            if raw_persona:
                if isinstance(raw_persona, str):
                    try:
                        raw_persona = json.loads(raw_persona)
                    except Exception:
                        raw_persona = {}
                if isinstance(raw_persona, dict):
                    persona_summary = raw_persona.get("persona_summary") or None

            # Count sessions since persona was last updated
            if row["persona_profile_updated_at"]:
                count_row = await db.fetchrow(
                    """
                    SELECT COUNT(*) AS cnt FROM study_sessions
                    WHERE student_id = $1 AND started_at > $2
                    """,
                    student_uuid,
                    row["persona_profile_updated_at"],
                )
                persona_sessions_ago = int(count_row["cnt"]) if count_row else 0

        # Fallback: if no Redis data, try last 2 session summaries from Postgres
        if not hot_context:
            summary_rows = await db.fetch(
                """
                SELECT session_summary FROM study_sessions
                WHERE student_id = $1
                  AND session_summary IS NOT NULL
                ORDER BY started_at DESC
                LIMIT 2
                """,
                student_uuid,
            )
            hot_context = [r["session_summary"] for r in summary_rows]
    except Exception as exc:
        logger.warning("build_context_bundle: profile fetch failed: %s", exc)

    # ── Layer 3: Top 5 weak concepts with error fingerprints ──────────────────
    weak_concepts: list[dict] = []
    try:
        concept_rows = await db.fetch(
            """
            SELECT cm.concept_id, cm.mastery_score,
                   cm.error_fingerprint, cm.forgetting_rate,
                   c.subtopic
            FROM   concept_mastery cm
            JOIN   concepts c ON c.id = cm.concept_id
            WHERE  cm.student_id = $1
            ORDER  BY cm.mastery_score ASC
            LIMIT  5
            """,
            student_uuid,
        )
        for r in concept_rows:
            fp = r["error_fingerprint"] or {}
            if isinstance(fp, str):
                try:
                    fp = json.loads(fp)
                except Exception:
                    fp = {}
            # Top 3 errors by strength
            top_errors = sorted(fp.items(), key=lambda x: -x[1])[:3]
            weak_concepts.append({
                "concept_id":     r["concept_id"],
                "subtopic":       r["subtopic"] or r["concept_id"],
                "mastery":        round(float(r["mastery_score"]) * 100),
                "top_errors":     [e for e, _ in top_errors],
                "forgetting_rate": round(float(r["forgetting_rate"] or 0.3), 2),
            })
    except Exception as exc:
        logger.warning("build_context_bundle: weak concepts fetch failed: %s", exc)

    return {
        "compressed_profile":  compressed_profile,
        "hot_context":         hot_context,
        "weak_concepts":       weak_concepts,
        "persona_summary":     persona_summary,
        "persona_sessions_ago": persona_sessions_ago,
    }


# ── Prompt formatter ──────────────────────────────────────────────────────────

def format_context_for_prompt(bundle: dict) -> str:
    """
    Render the context bundle into a ≤350-token string ready for prompt injection.
    Returns "New student — no history yet." for an empty bundle.
    """
    profile            = bundle.get("compressed_profile") or ""
    hot                = bundle.get("hot_context") or []
    weak               = bundle.get("weak_concepts") or []
    persona_summary    = bundle.get("persona_summary") or ""
    persona_sessions_ago = bundle.get("persona_sessions_ago") or 0

    if not profile and not hot and not weak and not persona_summary:
        return "New student — no history yet."

    parts: list[str] = ["STUDENT CONTEXT:"]

    if profile:
        parts.append(profile)
    else:
        parts.append("Building profile...")

    if persona_summary:
        freshness = f"updated {persona_sessions_ago} session{'s' if persona_sessions_ago != 1 else ''} ago"
        parts.append(f"\nSTUDENT PERSONA ({freshness}):")
        parts.append(persona_summary)
        if persona_sessions_ago > 15:
            parts.append("Note: persona may be outdated — treat with lower confidence.")

    if hot:
        parts.append("\nRECENT SESSIONS:")
        for s in hot[:2]:
            parts.append(f"- {s}")

    if weak:
        parts.append("\nPRIORITY WEAK AREAS:")
        for c in weak[:5]:
            errors = ", ".join(c["top_errors"]) if c["top_errors"] else "none"
            parts.append(
                f"- {c['subtopic']} | {c['mastery']}% mastery | errors: {errors}"
            )

    text = "\n".join(parts)
    return _truncate_to_tokens(text, _MAX_TOKENS)


# ── Error fingerprint updater ─────────────────────────────────────────────────

async def update_error_fingerprint(
    student_id: str,
    concept_id: str,
    error_type: str,
    was_correct: bool,
    db: asyncpg.Pool,
) -> None:
    """
    Decay or reinforce a specific error type in the concept fingerprint.

    Correct:   strength × 0.7  (error becoming less relevant)
    Wrong:     strength + 0.3, capped at 1.0
    Prune:     remove entries below 0.1
    """
    if not error_type:
        return
    try:
        student_uuid = uuid.UUID(student_id)
        row = await db.fetchrow(
            "SELECT error_fingerprint FROM concept_mastery WHERE student_id = $1 AND concept_id = $2",
            student_uuid, concept_id,
        )
        if row is None:
            return

        fp = row["error_fingerprint"] or {}
        if isinstance(fp, str):
            try:
                fp = json.loads(fp)
            except Exception:
                fp = {}

        current = float(fp.get(error_type, 0.5 if was_correct else 0.0))
        if was_correct:
            fp[error_type] = current * 0.7
        else:
            fp[error_type] = min(1.0, current + 0.3)

        # Prune weak signals
        fp = {k: v for k, v in fp.items() if v >= 0.1}

        await db.execute(
            "UPDATE concept_mastery SET error_fingerprint = $1::jsonb WHERE student_id = $2 AND concept_id = $3",
            json.dumps(fp), student_uuid, concept_id,
        )
    except Exception as exc:
        logger.warning("update_error_fingerprint failed (non-fatal): %s", exc)


# ── Forgetting rate updater ───────────────────────────────────────────────────

async def update_forgetting_rate(
    student_id: str,
    concept_id: str,
    days_since_last_review: int,
    performance: float,
    db: asyncpg.Pool,
) -> None:
    """
    Adjust the per-concept Ebbinghaus decay rate based on retention performance.

    Retained well (perf > 0.8, gap > 7d): rate × 0.9  (concept sticks — slow decay)
    Forgotten fast (perf < 0.5):           rate × 1.1  (concept fades — fast decay)
    Capped: [0.1, 0.9]
    """
    try:
        student_uuid = uuid.UUID(student_id)
        row = await db.fetchrow(
            "SELECT forgetting_rate FROM concept_mastery WHERE student_id = $1 AND concept_id = $2",
            student_uuid, concept_id,
        )
        if row is None:
            return

        rate = float(row["forgetting_rate"] or 0.3)

        if performance > 0.8 and days_since_last_review > 7:
            rate = rate * 0.9
        elif performance < 0.5:
            rate = rate * 1.1

        rate = max(0.1, min(0.9, rate))

        await db.execute(
            "UPDATE concept_mastery SET forgetting_rate = $1 WHERE student_id = $2 AND concept_id = $3",
            rate, student_uuid, concept_id,
        )

        # Mirror into student_memory.forgetting_rates for fast batch reads
        await db.execute(
            """
            INSERT INTO student_memory (student_id, forgetting_rates)
            VALUES ($1, $2::jsonb)
            ON CONFLICT (student_id) DO UPDATE
                SET forgetting_rates = student_memory.forgetting_rates || $2::jsonb
            """,
            student_uuid,
            json.dumps({concept_id: rate}),
        )
    except Exception as exc:
        logger.warning("update_forgetting_rate failed (non-fatal): %s", exc)


# ── Persona profile helpers ───────────────────────────────────────────────────

_DEFAULT_PERSONA_PROFILE = {
    "scaffolding_level": "HIGH",
    "preferred_style": "analogy",
    "common_misconceptions": [],
    "allowed_hint_depth": 3,
    "interaction_depth_score": 0.0,
    "learning_velocity": 0.0,
}


async def get_persona_profile(student_id: str, db: asyncpg.Pool) -> dict:
    """
    Fetch persona_profile from student_memory for this student.
    Returns the default profile if no row exists or profile is null.
    Never raises — always returns a valid dict.
    """
    try:
        student_uuid = uuid.UUID(student_id)
        row = await db.fetchrow(
            "SELECT persona_profile FROM student_memory WHERE student_id = $1",
            student_uuid,
        )
        if row and row["persona_profile"]:
            profile = row["persona_profile"]
            if isinstance(profile, str):
                try:
                    profile = json.loads(profile)
                except Exception:
                    profile = {}
            if isinstance(profile, dict) and profile:
                # Merge with defaults so any missing keys are filled in
                merged = dict(_DEFAULT_PERSONA_PROFILE)
                merged.update(profile)
                return merged
    except Exception as exc:
        logger.warning("get_persona_profile failed (non-fatal): %s", exc)
    return dict(_DEFAULT_PERSONA_PROFILE)


async def update_persona_profile(
    student_id: str, updates: dict, db: asyncpg.Pool
) -> None:
    """
    Merge updates into the existing persona_profile (does not replace entirely).
    If no student_memory row exists, inserts with the merged profile.
    Never raises.
    """
    try:
        student_uuid = uuid.UUID(student_id)
        current = await get_persona_profile(student_id, db)
        merged = {**current, **updates}
        await db.execute(
            """
            INSERT INTO student_memory (student_id, persona_profile)
            VALUES ($1, $2::jsonb)
            ON CONFLICT (student_id) DO UPDATE
                SET persona_profile = $2::jsonb
            """,
            student_uuid,
            json.dumps(merged),
        )
    except Exception as exc:
        logger.warning("update_persona_profile failed (non-fatal): %s", exc)


async def infer_scaffolding_level(student_id: str, db: asyncpg.Pool) -> str:
    """
    Compute scaffolding level from average mastery score across all concepts.

    avg mastery < 0.4  → HIGH
    avg mastery 0.4–0.7 → MEDIUM
    avg mastery > 0.7  → LOW

    Updates persona_profile with the inferred level and returns the level string.
    Falls back to HIGH on any error.
    """
    level = "HIGH"
    try:
        student_uuid = uuid.UUID(student_id)
        row = await db.fetchrow(
            "SELECT AVG(mastery_score) AS avg_mastery FROM concept_mastery WHERE student_id = $1",
            student_uuid,
        )
        if row and row["avg_mastery"] is not None:
            avg = float(row["avg_mastery"])
            if avg > 0.7:
                level = "LOW"
            elif avg >= 0.4:
                level = "MEDIUM"
            else:
                level = "HIGH"
    except Exception as exc:
        logger.warning("infer_scaffolding_level: mastery fetch failed: %s", exc)

    await update_persona_profile(student_id, {"scaffolding_level": level}, db)
    return level


async def get_sessions_count(student_id: str, db: asyncpg.Pool) -> int:
    """
    Return the total number of study sessions for this student.
    Returns 0 on any error.
    """
    try:
        student_uuid = uuid.UUID(student_id)
        row = await db.fetchrow(
            "SELECT COUNT(*) AS cnt FROM study_sessions WHERE student_id = $1",
            student_uuid,
        )
        return int(row["cnt"]) if row else 0
    except Exception as exc:
        logger.warning("get_sessions_count failed (non-fatal): %s", exc)
        return 0
