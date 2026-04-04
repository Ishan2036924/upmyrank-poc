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

from app.services.memory.summarizer import (
    maybe_compress_profile,
    summarize_session,
    update_hot_context,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/session", tags=["session"])


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
