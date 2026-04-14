"""
Feedback API — per-response thumbs up/down collection.

POST /feedback/response — upsert a thumbs_up/thumbs_down rating for a specific AI message
"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.middleware.auth import get_current_student_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feedback")


class FeedbackRequest(BaseModel):
    doubt_session_id: str
    response_idx: int           # 0-based index of the AI message in the conversation
    rating: Literal['thumbs_up', 'thumbs_down']


@router.post("/response")
async def submit_feedback(
    body: FeedbackRequest,
    student_id: str = Depends(get_current_student_id),
    request: Request = None,  # type: ignore[assignment]
):
    """
    Upsert a feedback rating for a specific AI response.
    If the same (student_id, doubt_session_id, response_idx) already exists,
    the rating is updated. This allows toggling between thumbs_up and thumbs_down.
    """
    pool = request.app.state.db_pool

    try:
        await pool.execute(
            """
            INSERT INTO response_feedback (student_id, doubt_session_id, response_idx, rating)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (student_id, doubt_session_id, response_idx)
            DO UPDATE SET rating = EXCLUDED.rating
            """,
            student_id,
            body.doubt_session_id,
            body.response_idx,
            body.rating,
        )
    except Exception as exc:
        logger.error("Failed to save feedback: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save feedback")

    return {"status": "ok"}


@router.get("/summary/{doubt_session_id}")
async def get_feedback_summary(
    doubt_session_id: str,
    student_id: str = Depends(get_current_student_id),
    request: Request = None,  # type: ignore[assignment]
):
    """
    Return thumbs up/down counts + per-message ratings for a given doubt session.
    Only returns data for the authenticated student.
    """
    pool = request.app.state.db_pool

    rows = await pool.fetch(
        """
        SELECT response_idx, rating
        FROM response_feedback
        WHERE student_id = $1 AND doubt_session_id = $2
        ORDER BY response_idx
        """,
        student_id,
        doubt_session_id,
    )

    ratings = {row["response_idx"]: row["rating"] for row in rows}
    thumbs_up   = sum(1 for r in ratings.values() if r == "thumbs_up")
    thumbs_down = sum(1 for r in ratings.values() if r == "thumbs_down")

    return {
        "doubt_session_id": doubt_session_id,
        "thumbs_up":        thumbs_up,
        "thumbs_down":      thumbs_down,
        "ratings":          ratings,
    }
