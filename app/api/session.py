"""
Study-session lifecycle endpoints.

POST /session/start   — create a new study session
POST /session/end     — close a study session (+ fire-and-forget block summaries)
POST /session/resume  — resume an existing session, returning full state
"""
import asyncio
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.middleware.auth import get_current_student_id

from app.services.eval.judge import evaluate_response
from app.services.memory.summarizer import (
    maybe_compress_profile,
    summarize_session,
    update_hot_context,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/session", tags=["session"])


async def _run_judge_for_session(study_session_id: str, pool, openai_client) -> None:
    """
    Background task: run 4-dim judge evaluation for every doubt_session in a study session.
    Fires fire-and-forget from POST /session/end — never blocks the response.
    """
    try:
        session_uuid = uuid.UUID(study_session_id)
        rows = await pool.fetch(
            """
            SELECT ds.id AS doubt_session_id,
                   ds.conversation_history,
                   db.topic,
                   db.hint_level
            FROM doubt_sessions ds
            JOIN doubt_blocks db ON db.doubt_session_id = ds.id
            WHERE db.study_session_id = $1
              AND ds.conversation_history IS NOT NULL
            ORDER BY db.started_at ASC
            """,
            session_uuid,
        )

        for row in rows:
            try:
                doubt_session_id = str(row["doubt_session_id"])
                conv_raw = row["conversation_history"]
                if conv_raw is None:
                    continue

                if isinstance(conv_raw, str):
                    history = json.loads(conv_raw)
                else:
                    history = list(conv_raw)

                if not history:
                    continue

                # Find first student message (the question)
                # roles in engine.py are "student"/"tutor" (not "user"/"assistant")
                question = next(
                    (m.get("content", "") for m in history
                     if m.get("role") in ("user", "student")),
                    "",
                )
                # Find last AI message (the response to evaluate)
                ai_response = ""
                for m in reversed(history):
                    if m.get("role") in ("assistant", "tutor"):
                        ai_response = m.get("content", "")
                        break

                if not question or not ai_response:
                    continue

                hint_level = row["hint_level"] or 0
                prior_attempts = max(0, sum(1 for m in history if m.get("role") == "user") - 1)

                result = await evaluate_response(
                    question=question,
                    ai_response=ai_response,
                    hint_level=hint_level,
                    prior_attempts=prior_attempts,
                )

                if result["overall_score"] < 0:
                    continue  # judge failed, skip insert

                await pool.execute(
                    """
                    INSERT INTO judge_evaluations
                      (study_session_id, doubt_session_id, question, ai_response,
                       pedagogical_score, factual_score, context_relevance_score,
                       hint_appropriateness_score, overall_score, rationale_json)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    session_uuid,
                    uuid.UUID(doubt_session_id),
                    question[:4000],
                    ai_response[:4000],
                    result["pedagogical_score"],
                    result["factual_score"],
                    result["context_relevance_score"],
                    result["hint_appropriateness_score"],
                    result["overall_score"],
                    json.dumps(result["rationale"]),
                )
                logger.info("Judge eval stored for doubt_session %s", doubt_session_id)

            except Exception as exc:
                logger.warning("Judge eval failed for doubt_session %s: %s", row.get("doubt_session_id"), exc)

    except Exception as exc:
        logger.warning("_run_judge_for_session failed (non-fatal): %s", exc)


# ── request / response models ─────────────────────────────────────────────────

class StartRequest(BaseModel):
    student_id: str


class EndRequest(BaseModel):
    study_session_id: str


class ResumeRequest(BaseModel):
    study_session_id: str


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start")
async def start_session(
    body: StartRequest,
    request: Request,
    current_student_id: str = Depends(get_current_student_id),
):
    """Create a new study session for a student."""
    pool = request.app.state.db_pool

    try:
        student_uuid = uuid.UUID(current_student_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid student ID") from exc

    # Verify student exists
    student = await pool.fetchrow("SELECT id FROM students WHERE id = $1", student_uuid)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    row = await pool.fetchrow(
        """
        INSERT INTO study_sessions (student_id)
        VALUES ($1)
        RETURNING study_session_id, started_at
        """,
        student_uuid,
    )

    return {
        "study_session_id": str(row["study_session_id"]),
        "started_at": row["started_at"].isoformat(),
    }


@router.post("/end")
async def end_session(
    body: EndRequest,
    request: Request,
    _: str = Depends(get_current_student_id),
):
    """End a study session — close open doubt blocks, fire summarizer."""
    pool = request.app.state.db_pool
    engine = request.app.state.socratic_engine

    try:
        session_uuid = uuid.UUID(body.study_session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID") from exc

    # Fetch student_id (needed for memory update below)
    session_row = await pool.fetchrow(
        "SELECT student_id FROM study_sessions WHERE study_session_id = $1",
        session_uuid,
    )
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found or already ended")

    student_id = str(session_row["student_id"])

    # Mark session ended
    result = await pool.execute(
        """
        UPDATE study_sessions
        SET ended_at = NOW()
        WHERE study_session_id = $1 AND ended_at IS NULL
        """,
        session_uuid,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Session not found or already ended")

    # Close any open doubt blocks
    open_blocks = await pool.fetch(
        """
        SELECT doubt_block_id FROM doubt_blocks
        WHERE study_session_id = $1 AND ended_at IS NULL
        """,
        session_uuid,
    )
    for block in open_blocks:
        await pool.execute(
            "UPDATE doubt_blocks SET ended_at = NOW() WHERE doubt_block_id = $1",
            block["doubt_block_id"],
        )
        # Fire-and-forget summarizer
        asyncio.create_task(
            engine.summarize_doubt_block(str(block["doubt_block_id"]))
        )

    # ── Memory update: blocking summarize, then background compress ───────────
    try:
        summary = await summarize_session(body.study_session_id, pool)
    except Exception as exc:
        logger.error("summarize_session failed at session end: %s", exc)
        summary = None

    if summary:
        try:
            await update_hot_context(student_id, summary)
        except Exception as exc:
            logger.warning("update_hot_context failed (non-fatal): %s", exc)

    asyncio.create_task(maybe_compress_profile(student_id, pool))

    # ── Background judge evaluation across all doubt sessions ─────────────────
    openai_client = request.app.state.socratic_engine._client
    asyncio.create_task(
        _run_judge_for_session(body.study_session_id, pool, openai_client)
    )

    return {"status": "ended", "study_session_id": body.study_session_id}


@router.post("/resume")
async def resume_session(
    body: ResumeRequest,
    request: Request,
    _: str = Depends(get_current_student_id),
):
    """Resume an existing study session — return full state for frontend hydration."""
    pool = request.app.state.db_pool

    try:
        session_uuid = uuid.UUID(body.study_session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID") from exc

    session = await pool.fetchrow(
        """
        SELECT study_session_id, student_id, started_at, ended_at, doubt_count
        FROM study_sessions
        WHERE study_session_id = $1
        """,
        session_uuid,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Fetch all doubt blocks with their conversation history
    blocks = await pool.fetch(
        """
        SELECT db.doubt_block_id, db.topic, db.hint_level, db.solved,
               db.summary, db.started_at, db.ended_at,
               ds.conversation_history
        FROM doubt_blocks db
        LEFT JOIN doubt_sessions ds ON ds.id = db.doubt_session_id
        WHERE db.study_session_id = $1
        ORDER BY db.started_at ASC
        """,
        session_uuid,
    )

    doubt_blocks = []
    active_block_id: Optional[str] = None

    for b in blocks:
        # Parse conversation history
        conv = b["conversation_history"]
        if conv is None:
            messages = []
        elif isinstance(conv, str):
            messages = json.loads(conv)
        else:
            messages = list(conv)

        block_data = {
            "doubt_block_id": str(b["doubt_block_id"]),
            "topic": b["topic"],
            "hint_level": b["hint_level"],
            "solved": b["solved"],
            "summary": b["summary"],
            "started_at": b["started_at"].isoformat() if b["started_at"] else None,
            "ended_at": b["ended_at"].isoformat() if b["ended_at"] else None,
            "messages": messages,
        }
        doubt_blocks.append(block_data)

        # Active block = latest one that hasn't ended
        if b["ended_at"] is None:
            active_block_id = str(b["doubt_block_id"])

    return {
        "study_session_id": str(session["study_session_id"]),
        "started_at": session["started_at"].isoformat(),
        "ended_at": session["ended_at"].isoformat() if session["ended_at"] else None,
        "doubt_count": session["doubt_count"] or 0,
        "doubt_blocks": doubt_blocks,
        "active_block_id": active_block_id,
    }
