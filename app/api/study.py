"""
Study Path API — v0.20 dual-loop Mode 1.

GET /study/card?subject=Physics&chapter=Kinematics&topic=Projectile Motion
    → concept card (notes + practice + PYQs + mastery).

Zero content generation. Everything composed from existing indexed data.
"""
from __future__ import annotations

import logging
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
        return card
    except Exception as exc:
        logger.exception("compose_concept_card failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to assemble concept card. See server logs.",
        ) from exc
