"""
Study Path API — v0.20 dual-loop Mode 1.

GET /study/card?subject=Physics&chapter=Kinematics&topic=Projectile Motion
    → concept card (notes + practice + PYQs + mastery).

Zero content generation. Everything composed from existing indexed data.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.middleware.auth import get_current_student_id
from app.services.study.card_composer import compose_concept_card

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/study", tags=["study"])

_VALID_SUBJECTS = {"Physics", "Chemistry", "Maths"}


@router.get("/card")
async def get_concept_card(
    request: Request,
    subject: str = Query(..., description="Physics | Chemistry | Maths"),
    topic:   str = Query(..., description="Topic name, e.g. 'Projectile Motion'"),
    chapter: Optional[str] = Query(None, description="Optional chapter context"),
    current_student_id: str = Depends(get_current_student_id),
):
    if subject not in _VALID_SUBJECTS:
        raise HTTPException(
            status_code=422,
            detail=f"subject must be one of {sorted(_VALID_SUBJECTS)}, got '{subject}'",
        )
    topic = (topic or "").strip()
    if not topic:
        raise HTTPException(status_code=422, detail="topic is required")

    pool      = request.app.state.db_pool
    retriever = request.app.state.retriever

    try:
        card = await compose_concept_card(
            pool=pool,
            retriever=retriever,
            student_id=current_student_id,
            subject=subject,
            chapter=chapter,
            topic=topic,
        )
    except Exception as exc:
        logger.exception("compose_concept_card failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to assemble concept card. See server logs.",
        ) from exc

    # v0.20.2: log a study_card_view event so admin dashboard can rank topics
    # by real usage. Best-effort — never blocks card delivery.
    #
    # v0.20.4: pass NULL for session_id (was gen_random_uuid() which violated
    # the FK to doubt_sessions). study_card_view isn't tied to a doubt_session
    # — the event stands alone. session_id is nullable in the schema.
    try:
        await pool.execute(
            """
            INSERT INTO session_events
                (session_id, event_type, student_id, session_type,
                 time_to_solve_seconds, max_hint_level_used,
                 mistake_forensics_tag, give_up_flag, misconception_detected, payload)
            VALUES (NULL, $1, $2, $3,
                    NULL, 0, NULL, FALSE, FALSE, $4::jsonb)
            """,
            "study_card_view",
            uuid.UUID(current_student_id),
            "study",
            json.dumps({
                "subject": subject,
                "chapter": chapter,
                "topic": topic,
                "is_override": bool(card.get("notes", {}).get("is_override")),
                "notes_chunks": len(card.get("notes", {}).get("chunks") or []),
                "practice_count": len(card.get("practice", {}).get("problems") or []),
                "pyq_count": len(card.get("pyqs", {}).get("problems") or []),
            }),
        )
    except Exception as exc:
        # Bumped INFO → WARNING per v0.20.4 lesson: silent fallbacks hide bugs.
        logger.warning(
            "study_card_view event-log skipped (admin panel will lack data): %s",
            exc,
        )

    return card
