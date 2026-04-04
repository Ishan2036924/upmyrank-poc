"""
Student genome endpoints.

GET  /student/{student_id}                → full knowledge genome
POST /student/{student_id}/update-mastery → update one concept's mastery score
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_student_id
from app.services.mastery import update_concept_mastery

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/student", tags=["student"])


class MasteryUpdateRequest(BaseModel):
    concept_id: str
    performance_score: float = Field(..., ge=0.0, le=1.0)


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_student_uuid(student_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(student_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid student ID: {student_id}") from exc


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{student_id}")
async def get_student(
    student_id: str,
    request: Request,
    _: str = Depends(get_current_student_id),
):
    """
    Return the full knowledge genome for a student.

    Includes:
      - Per-topic mastery breakdown (Relations vs Functions)
      - Overall weighted mastery score
      - Weakest 3 concepts
      - Session statistics (total, resolved)
    """
    pool = request.app.state.db_pool
    s_uuid = _parse_student_uuid(student_id)

    try:
        # ── 1. Fetch student ──────────────────────────────────────────────────
        student = await pool.fetchrow(
            "SELECT id, name, exam_type, target_year FROM students WHERE id = $1",
            s_uuid,
        )
        if student is None:
            raise HTTPException(status_code=404, detail="Student not found")

        # ── 2. Fetch all concept mastery rows ─────────────────────────────────
        mastery_rows = await pool.fetch(
            """
            SELECT cm.concept_id,
                   cm.mastery_score,
                   cm.error_count,
                   cm.attempt_count,
                   cm.last_reviewed,
                   cm.next_review_due,
                   c.topic,
                   c.subtopic
            FROM concept_mastery cm
            JOIN concepts c ON c.id = cm.concept_id
            WHERE cm.student_id = $1
            ORDER BY c.topic, cm.mastery_score
            """,
            s_uuid,
        )

        # ── 3. Group by topic ─────────────────────────────────────────────────
        topic_concepts: Dict[str, List[dict]] = defaultdict(list)
        for row in mastery_rows:
            topic_concepts[row["topic"]].append(
                {
                    "concept_id": row["concept_id"],
                    "subtopic": row["subtopic"],
                    "mastery": round(float(row["mastery_score"]), 3),
                    "error_count": row["error_count"],
                    "attempt_count": row["attempt_count"],
                    "last_reviewed": (
                        row["last_reviewed"].isoformat()
                        if row["last_reviewed"] else None
                    ),
                    "next_review_due": (
                        row["next_review_due"].isoformat()
                        if row["next_review_due"] else None
                    ),
                }
            )

        # ── 4. Per-topic averages ─────────────────────────────────────────────
        topic_mastery: dict = {}
        all_scores: List[float] = []

        for topic, concepts in topic_concepts.items():
            avg = sum(c["mastery"] for c in concepts) / len(concepts)
            topic_mastery[topic] = {
                "average": round(avg, 3),
                "concepts": sorted(concepts, key=lambda x: x["mastery"]),
            }
            all_scores.extend(c["mastery"] for c in concepts)

        overall_mastery = (
            round(sum(all_scores) / len(all_scores), 3) if all_scores else 0.0
        )

        # ── 5. Weakest 3 concepts (across all topics) ─────────────────────────
        all_flat = [c for cs in topic_concepts.values() for c in cs]
        weakest_3 = sorted(all_flat, key=lambda x: x["mastery"])[:3]

        # ── 6. Session statistics ─────────────────────────────────────────────
        session_stats = await pool.fetchrow(
            """
            SELECT
                COUNT(*)                                         AS total,
                SUM(CASE WHEN resolved THEN 1 ELSE 0 END)       AS resolved_count
            FROM doubt_sessions
            WHERE student_id = $1
            """,
            s_uuid,
        )

        return {
            "student_id": str(student["id"]),
            "name": student["name"],
            "exam_type": student["exam_type"],
            "target_year": student["target_year"],
            "overall_mastery": overall_mastery,
            "topic_mastery": topic_mastery,
            "weakest_concepts": weakest_3,
            "total_sessions": int(session_stats["total"] or 0),
            "resolved_sessions": int(session_stats["resolved_count"] or 0),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get_student failed for %s: %s", student_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{student_id}/update-mastery")
async def update_mastery(
    student_id: str,
    body: MasteryUpdateRequest,
    request: Request,
    _: str = Depends(get_current_student_id),
):
    """
    Update a student's mastery for one concept.

    Uses exponential moving average:
        new_mastery = 0.7 × old_mastery + 0.3 × performance_score

    Also increments attempt_count, conditionally increments error_count
    (when performance_score < 0.5), and schedules next review via SM-2.
    """
    pool = request.app.state.db_pool
    s_uuid = _parse_student_uuid(student_id)

    try:
        # Verify student exists
        student = await pool.fetchrow(
            "SELECT id FROM students WHERE id = $1", s_uuid
        )
        if student is None:
            raise HTTPException(status_code=404, detail="Student not found")

        result = await update_concept_mastery(
            pool=pool,
            student_id=s_uuid,
            concept_id=body.concept_id,
            performance_score=body.performance_score,
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No mastery record found for concept_id='{body.concept_id}'",
            )

        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("update_mastery failed for %s: %s", student_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
