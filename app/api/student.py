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


# v0.20.2: profile patch — used by /settings save. Migration v16 adds the
# columns. Until that migration runs, the PATCH gracefully falls back to
# updating only the columns that exist (logged warning, no 500).
class StudentProfilePatch(BaseModel):
    name:               str | None = Field(None, min_length=1, max_length=120)
    phone:              str | None = Field(None, max_length=20)
    avatar_url:         str | None = Field(None, max_length=2_000_000)  # base64 inline OK
    timezone:           str | None = Field(None, max_length=64)
    preferred_language: str | None = Field(None, max_length=8)
    exam_type:          str | None = Field(None, max_length=16)
    target_year:        int | None = Field(None, ge=2024, le=2030)


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

        # ── 7. Persona profile from student_memory ────────────────────────────
        import json as _json
        persona_profile = None
        try:
            mem_row = await pool.fetchrow(
                "SELECT persona_profile FROM student_memory WHERE student_id = $1",
                s_uuid,
            )
            if mem_row and mem_row["persona_profile"]:
                raw = mem_row["persona_profile"]
                persona_profile = _json.loads(raw) if isinstance(raw, str) else dict(raw)
        except Exception as exc:
            logger.warning("get_student: persona_profile fetch failed (non-fatal): %s", exc)

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
            "persona_profile": persona_profile,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get_student failed for %s: %s", student_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.patch("/{student_id}")
async def patch_student(
    student_id: str,
    body: StudentProfilePatch,
    request: Request,
    current: str = Depends(get_current_student_id),
):
    """
    Update editable profile fields (v0.20.2).

    Auth rule: a student can only patch *their own* row. The path UUID must
    match the JWT-bound student_id.
    """
    if student_id != current:
        raise HTTPException(status_code=403, detail="Cannot edit another student's profile")

    s_uuid = _parse_student_uuid(student_id)
    pool = request.app.state.db_pool

    # Discover which columns exist (v16 migration may not yet be applied on
    # this deployment — graceful fallback keeps prod alive).
    col_rows = await pool.fetch(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'students'
        """
    )
    existing_cols = {r["column_name"] for r in col_rows}

    updates: dict = body.model_dump(exclude_none=True)
    if not updates:
        return {"updated": [], "ignored": [], "noop": True}

    settable: dict = {}
    skipped: list = []
    for key, val in updates.items():
        if key in existing_cols:
            settable[key] = val
        else:
            skipped.append(key)

    if not settable:
        logger.warning(
            "patch_student: no settable cols — migration v16 not applied? "
            "skipped=%s", skipped,
        )
        return {"updated": [], "ignored": skipped, "noop": True}

    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(settable.keys()))
    params = [s_uuid, *settable.values()]
    try:
        await pool.execute(
            f"UPDATE students SET {set_clause} WHERE id = $1",
            *params,
        )
    except Exception as exc:
        logger.exception("patch_student UPDATE failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "updated": list(settable.keys()),
        "ignored": skipped,
        "noop": False,
    }


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
