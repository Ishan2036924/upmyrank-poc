"""
Concept-mastery update service.

Implements exponential moving-average (EMA) mastery tracking with
SM-2-style spaced-repetition scheduling.

Used by:
  • POST /student/{student_id}/update-mastery  (explicit API call)
  • SocraticEngine.get_hint()                  (auto-update on session resolve)
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

# EMA weight for prior mastery (vs. new performance observation)
_ALPHA_OLD = 0.7
_ALPHA_NEW = 0.3


async def update_concept_mastery(
    pool: asyncpg.Pool,
    student_id: uuid.UUID,
    concept_id: str,
    performance_score: float,
    mistake_tag: Optional[str] = None,
) -> Optional[dict]:
    """
    Update concept mastery for a student using exponential moving average.

    Algorithm:
        new_mastery = 0.7 * old_mastery + 0.3 * performance_score

    Spaced-repetition scheduling (SM-2 inspired):
        interval_days = max(1, int(6 * new_mastery / 0.3))
        → mastery 0.0 → 1 day   (review tomorrow)
        → mastery 0.3 → 6 days
        → mastery 0.5 → 10 days
        → mastery 1.0 → 20 days

    Args:
        pool:              asyncpg connection pool
        student_id:        student UUID
        concept_id:        concept text ID (e.g. "relations.equivalence")
        performance_score: 0.0–1.0 (0=wrong, 1=perfect)

    Returns:
        Updated mastery record dict, or None if the record doesn't exist.
    """
    performance_score = max(0.0, min(1.0, float(performance_score)))

    # ── 1. Fetch current record ───────────────────────────────────────────────
    row = await pool.fetchrow(
        """
        SELECT mastery_score, error_count, attempt_count
        FROM concept_mastery
        WHERE student_id = $1 AND concept_id = $2
        """,
        student_id,
        concept_id,
    )
    if row is None:
        logger.warning(
            "No concept_mastery row for student=%s concept=%s — skipping",
            student_id, concept_id,
        )
        return None

    old_mastery = float(row["mastery_score"])

    # ── 2. Compute new mastery (EMA) ─────────────────────────────────────────
    new_mastery = _ALPHA_OLD * old_mastery + _ALPHA_NEW * performance_score
    new_mastery = round(max(0.0, min(1.0, new_mastery)), 4)

    # ── 3. Update error / attempt counters ───────────────────────────────────
    error_delta = 1 if performance_score < 0.5 else 0
    new_error_count = row["error_count"] + error_delta
    new_attempt_count = row["attempt_count"] + 1

    # ── 4. SM-2 spacing: higher mastery → review less often ──────────────────
    interval_days = max(1, int(6 * new_mastery / 0.3))

    # ── 5. Persist (including JSONB error_pattern_array if mistake_tag given) ──
    updated = await pool.fetchrow(
        """
        UPDATE concept_mastery
        SET mastery_score        = $1,
            error_count          = $2,
            attempt_count        = $3,
            last_reviewed        = NOW(),
            next_review_due      = NOW() + make_interval(days => $4),
            next_review_date     = NOW() + make_interval(days => $4),
            updated_at           = NOW(),
            error_pattern_array  = CASE
                WHEN $7::text IS NOT NULL
                THEN jsonb_set(
                    COALESCE(error_pattern_array, '{}'),
                    ARRAY[$7::text],
                    to_jsonb(
                        COALESCE(
                            (COALESCE(error_pattern_array, '{}') ->> $7)::int,
                            0
                        ) + 1
                    )
                )
                ELSE COALESCE(error_pattern_array, '{}')
            END
        WHERE student_id = $5 AND concept_id = $6
        RETURNING mastery_score, error_count, attempt_count,
                  last_reviewed, next_review_due
        """,
        new_mastery,
        new_error_count,
        new_attempt_count,
        interval_days,
        student_id,
        concept_id,
        mistake_tag,
    )

    if updated is None:
        return None

    logger.info(
        "Mastery updated: student=%s concept=%s  %.3f → %.3f  (perf=%.2f)",
        student_id, concept_id, old_mastery, new_mastery, performance_score,
    )

    return {
        "concept_id": concept_id,
        "old_mastery": round(old_mastery, 4),
        "new_mastery": float(updated["mastery_score"]),
        "performance_score": performance_score,
        "error_count": updated["error_count"],
        "attempt_count": updated["attempt_count"],
        "interval_days": interval_days,
        "last_reviewed": (
            updated["last_reviewed"].isoformat()
            if updated["last_reviewed"] else None
        ),
        "next_review_due": (
            updated["next_review_due"].isoformat()
            if updated["next_review_due"] else None
        ),
    }
