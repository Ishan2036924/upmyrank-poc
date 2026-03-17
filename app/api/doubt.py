"""
Doubt-resolution API — intent-gated routing.

POST /doubt/ask    — classify intent → route to non-physics response or Socratic pipeline
POST /doubt/hint   — progressive hint for an active doubt session
POST /doubt/verify — two-layer solution verification
"""
import asyncio
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/doubt", tags=["doubt"])


# ── request / response models ─────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str
    student_id: str
    subject: str = "Physics"
    study_session_id: Optional[str] = None


class HintRequest(BaseModel):
    session_id: str
    student_response: Optional[str] = None
    jump_to_full_solution: bool = False
    study_session_id: Optional[str] = None
    give_up_flag: bool = False          # set True when student explicitly gives up
    mistake_tag: Optional[str] = None   # e.g. 'sign_error', 'wrong_formula'


class VerifyRequest(BaseModel):
    question: str
    solution: str
    context: str = ""


# ── doubt-block helpers ───────────────────────────────────────────────────────

async def _get_active_doubt_block(pool, study_session_id: str) -> Optional[dict]:
    """Get the latest unsolved, unclosed doubt block for a study session."""
    try:
        row = await pool.fetchrow(
            """
            SELECT doubt_block_id, doubt_session_id, topic, hint_level, solved
            FROM doubt_blocks
            WHERE study_session_id = $1
              AND ended_at IS NULL
              AND solved = FALSE
            ORDER BY started_at DESC
            LIMIT 1
            """,
            uuid.UUID(study_session_id),
        )
        if row:
            return dict(row)
        return None
    except Exception as exc:
        logger.warning("_get_active_doubt_block failed: %s", exc)
        return None


async def _create_doubt_block(
    pool,
    study_session_id: str,
    student_id: str,
    doubt_session_id: uuid.UUID,
    topic: str,
) -> str:
    """Create a new doubt block and increment the study session's doubt_count."""
    block = await pool.fetchrow(
        """
        INSERT INTO doubt_blocks (study_session_id, student_id, doubt_session_id, topic)
        VALUES ($1, $2, $3, $4)
        RETURNING doubt_block_id
        """,
        uuid.UUID(study_session_id),
        uuid.UUID(student_id),
        doubt_session_id,
        topic,
    )

    await pool.execute(
        """
        UPDATE study_sessions
        SET doubt_count = COALESCE(doubt_count, 0) + 1
        WHERE study_session_id = $1
        """,
        uuid.UUID(study_session_id),
    )

    return str(block["doubt_block_id"])


async def _close_doubt_block(pool, engine, doubt_block_id: str, solved: bool):
    """Close a doubt block and fire-and-forget the summarizer."""
    await pool.execute(
        """
        UPDATE doubt_blocks
        SET ended_at = NOW(), solved = $2
        WHERE doubt_block_id = $1
        """,
        uuid.UUID(doubt_block_id),
        solved,
    )
    asyncio.create_task(engine.summarize_doubt_block(doubt_block_id))


# ── background genome update ──────────────────────────────────────────────────

# Performance score mapping: hint level reached → how well the student did
_HINT_PERF_MAP = {
    0: 1.0,   # solved from Socratic question alone — excellent
    1: 0.90,  # needed 1 conceptual nudge
    2: 0.75,  # needed structural hint
    3: 0.55,  # needed partial solution
}
_GIVE_UP_PERF = 0.10    # student gave up — minimal positive signal


async def _genome_update_task(
    pool,
    doubt_session_id: str,
    give_up_flag: bool = False,
    mistake_tag: Optional[str] = None,
    session_type: str = "doubt",
) -> None:
    """
    Terminal-state background task — fires ONLY when a doubt block closes.

    Steps:
      1. Fetch session metadata (hint_level, concepts_involved, resolved, topic).
      2. Compute time_to_solve from doubt_session.created_at.
      3. INSERT a telemetry row into session_events (new pedagogical columns).
      4. UPSERT concept_mastery for every concept tested:
             mastery = 0.7 × old_mastery + 0.3 × performance_score  (EMA α=0.7)
         Also tag mistake_forensics in error_pattern_array if mistake_tag is set.
    """
    from app.services.mastery import update_concept_mastery

    try:
        session_uuid = uuid.UUID(doubt_session_id)
    except ValueError:
        logger.warning("_genome_update_task: invalid session UUID %s", doubt_session_id)
        return

    try:
        session = await pool.fetchrow(
            """
            SELECT student_id, current_hint_level, concepts_involved,
                   resolved, topic, created_at
            FROM doubt_sessions
            WHERE id = $1
            """,
            session_uuid,
        )
        if session is None:
            logger.warning("_genome_update_task: session %s not found", doubt_session_id)
            return

        student_uuid: uuid.UUID   = session["student_id"]
        hint_level:   int         = session["current_hint_level"] or 0
        concept_ids:  list        = list(session["concepts_involved"] or [])
        resolved:     bool        = bool(session["resolved"])
        topic:        str         = session["topic"] or "Unknown"
        created_at                = session["created_at"]

        # ── Time to solve ────────────────────────────────────────────────────
        import datetime
        time_seconds: Optional[int] = None
        if created_at:
            try:
                delta = datetime.datetime.now(datetime.timezone.utc) - created_at
                time_seconds = max(0, int(delta.total_seconds()))
            except Exception:
                pass

        # ── Performance score ────────────────────────────────────────────────
        if give_up_flag:
            performance = _GIVE_UP_PERF
        else:
            performance = _HINT_PERF_MAP.get(min(hint_level, 3), 0.2)

        # ── 1. INSERT telemetry into session_events ──────────────────────────
        await pool.execute(
            """
            INSERT INTO session_events
                (session_id, event_type, student_id, session_type,
                 time_to_solve_seconds, max_hint_level_used,
                 mistake_forensics_tag, give_up_flag, payload)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
            """,
            session_uuid,
            "session_terminal",
            student_uuid,
            session_type,
            time_seconds,
            min(hint_level, 3),
            mistake_tag,
            give_up_flag,
            json.dumps({"resolved": resolved, "topic": topic}),
        )

        # ── 2. UPSERT concept_mastery (EMA α=0.7) ────────────────────────────
        if concept_ids:
            for concept_id in concept_ids:
                try:
                    result = await update_concept_mastery(
                        pool=pool,
                        student_id=student_uuid,
                        concept_id=concept_id,
                        performance_score=performance,
                        mistake_tag=mistake_tag,
                    )
                    if result is None:
                        # Row missing → insert at baseline (new concept for this student)
                        await pool.execute(
                            """
                            INSERT INTO concept_mastery
                                (student_id, concept_id, mastery_score,
                                 error_count, attempt_count, updated_at)
                            VALUES ($1, $2, $3, $4, 1, NOW())
                            ON CONFLICT (student_id, concept_id) DO UPDATE
                                SET mastery_score = 0.7 * concept_mastery.mastery_score
                                                  + 0.3 * EXCLUDED.mastery_score,
                                    attempt_count = concept_mastery.attempt_count + 1,
                                    updated_at    = NOW()
                            """,
                            student_uuid,
                            concept_id,
                            performance,
                            1 if performance < 0.5 else 0,
                        )
                except Exception as exc:
                    logger.warning(
                        "Mastery update failed for concept=%s: %s", concept_id, exc,
                    )

        logger.info(
            "Genome updated: session=%s student=%s concepts=%d perf=%.2f give_up=%s",
            doubt_session_id, student_uuid, len(concept_ids), performance, give_up_flag,
        )

    except Exception as exc:
        logger.error("_genome_update_task failed for session %s: %s", doubt_session_id, exc)


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ask")
async def ask_doubt(body: AskRequest, request: Request, background_tasks: BackgroundTasks):
    """
    Intent-gated doubt handler.

    1. Classify intent (greeting, meta, emotional, out_of_scope, physics_doubt, continuation)
    2. Non-physics intents → immediate response, NO DB writes
    3. continuation → delegate to get_hint via active block's doubt_session_id
    4. physics_doubt → start new session + create doubt block
    """
    engine = request.app.state.socratic_engine
    pool = request.app.state.db_pool

    # ── 1. Check for active doubt block ───────────────────────────────────────
    active_block = None
    if body.study_session_id:
        active_block = await _get_active_doubt_block(pool, body.study_session_id)

    has_active_block = active_block is not None and not active_block.get("solved", False)

    # ── 2. Classify intent ────────────────────────────────────────────────────
    intent = await engine.classify_intent(body.question, has_active_block)
    logger.info("Intent classified: %s (active_block=%s)", intent, has_active_block)

    # ── 3. Non-physics intents → immediate response, NO DB writes ─────────────
    if intent in ("greeting", "meta", "emotional", "out_of_scope"):
        result = await engine.handle_non_physics_intent(intent, body.question)
        return result

    # ── 3b. Recap — summarise completed doubt blocks in this session ───────────
    if intent == "recap":
        if body.study_session_id:
            rows = await pool.fetch(
                """
                SELECT topic, summary, solved, started_at
                FROM doubt_blocks
                WHERE study_session_id = $1
                ORDER BY started_at ASC
                """,
                uuid.UUID(body.study_session_id),
            )
            completed = [r for r in rows if r["summary"]]
            if completed:
                lines = ["Here's what we've covered in this session:\n"]
                for i, row in enumerate(completed, 1):
                    topic = row["topic"] or "Physics question"
                    solved_label = "✓ Solved" if row["solved"] else "⟳ In progress"
                    lines.append(f"**{i}. {topic}** — {solved_label}\n{row['summary']}")
                response = "\n\n".join(lines)
            elif rows:
                # Blocks exist but summaries not yet generated (still in progress)
                topics = [r["topic"] or "Physics question" for r in rows]
                topic_list = ", ".join(f"**{t}**" for t in topics)
                response = (
                    f"We're currently working through: {topic_list}. "
                    "Summaries are generated once a question is resolved — "
                    "keep going! 💪"
                )
            else:
                response = (
                    "We haven't covered any topics yet in this session. "
                    "Ask me a Physics question to get started!"
                )
        else:
            response = (
                "I don't have a record of this session. "
                "Start a new session and I'll track everything you cover!"
            )
        return {"intent": "recap", "response": response, "session_id": None}

    # ── 4. Continuation (follow-up to active block) ───────────────────────────
    if intent == "continuation" and active_block:
        try:
            hint_result = await engine.get_hint(
                session_id=str(active_block["doubt_session_id"]),
                student_response=body.question,
            )

            # Update block hint_level
            await pool.execute(
                "UPDATE doubt_blocks SET hint_level = $1 WHERE doubt_block_id = $2",
                hint_result.get("hint_level", active_block["hint_level"]),
                active_block["doubt_block_id"],
            )

            # If resolved, close the block + schedule genome update
            if hint_result.get("resolved"):
                await _close_doubt_block(
                    pool, engine, str(active_block["doubt_block_id"]), solved=True,
                )
                background_tasks.add_task(
                    _genome_update_task,
                    pool,
                    str(active_block["doubt_session_id"]),
                    give_up_flag=False,
                    mistake_tag=None,
                )

            return {
                "intent": intent,
                "doubt_block_id": str(active_block["doubt_block_id"]),
                **hint_result,
            }
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("get_hint failed for continuation: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ── 5. New physics doubt ──────────────────────────────────────────────────
    # Close any existing active block first (if there was one but classified as new doubt)
    if active_block and body.study_session_id:
        await _close_doubt_block(
            pool, engine, str(active_block["doubt_block_id"]), solved=False,
        )

    try:
        result = await engine.start_session(
            question=body.question,
            student_id=body.student_id,
            subject=body.subject,
            study_session_id=body.study_session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("SocraticEngine.start_session failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Create doubt block if within a study session
    doubt_block_id = None
    if body.study_session_id:
        topic = result.get("analysis", {}).get("topic", "Physics")
        doubt_block_id = await _create_doubt_block(
            pool,
            body.study_session_id,
            body.student_id,
            uuid.UUID(result["session_id"]),
            topic,
        )

    # Get current doubt count
    doubt_count = 0
    if body.study_session_id:
        count_row = await pool.fetchrow(
            "SELECT doubt_count FROM study_sessions WHERE study_session_id = $1",
            uuid.UUID(body.study_session_id),
        )
        if count_row:
            doubt_count = count_row["doubt_count"] or 0

    return {
        "intent": "physics_doubt",
        "doubt_block_id": doubt_block_id,
        "doubt_block_topic": result.get("analysis", {}).get("topic", "Physics"),
        "doubt_block_number": doubt_count,
        **result,
    }


@router.post("/hint")
async def get_hint(body: HintRequest, request: Request, background_tasks: BackgroundTasks):
    """
    Request the next progressive hint for an existing doubt session.

    Hint level escalation:
        1 → gentle conceptual nudge
        2 → structural / approach hint
        3 → partial solution (60-70 %)
        4+ → full solution, session marked resolved
    """
    engine = request.app.state.socratic_engine
    pool = request.app.state.db_pool

    try:
        result = await engine.get_hint(
            session_id=body.session_id,
            student_response=body.student_response,
            jump_to_full=body.jump_to_full_solution,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("SocraticEngine.get_hint failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # If within a study session, update the doubt block
    if body.study_session_id:
        block = await _get_active_doubt_block(pool, body.study_session_id)
        if block:
            await pool.execute(
                "UPDATE doubt_blocks SET hint_level = $1 WHERE doubt_block_id = $2",
                result.get("hint_level", block["hint_level"]),
                block["doubt_block_id"],
            )
            if result.get("resolved"):
                await _close_doubt_block(
                    pool, engine, str(block["doubt_block_id"]), solved=True,
                )
                # Genome update fires asynchronously after the response is sent
                background_tasks.add_task(
                    _genome_update_task,
                    pool,
                    body.session_id,
                    body.give_up_flag,
                    body.mistake_tag,
                )
            result["doubt_block_id"] = str(block["doubt_block_id"])

    return result


@router.post("/verify")
async def verify_solution(body: VerifyRequest, request: Request):
    """
    Run the two-layer verification pipeline on an arbitrary question + solution.
    """
    verifier = request.app.state.verifier
    try:
        result = await verifier.verify(
            question=body.question,
            solution=body.solution,
            context=body.context,
        )
    except Exception as exc:
        logger.exception("VerificationPipeline.verify failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result
