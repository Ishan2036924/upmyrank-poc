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

    # ── Atomic EMA update — single SQL statement prevents race conditions ─────
    # The EMA, counters, and SM-2 interval are all computed inside the UPDATE
    # so concurrent requests cannot overwrite each other.
    updated = await pool.fetchrow(
        """
        UPDATE concept_mastery
        SET mastery_score   = ROUND(LEAST(1.0, GREATEST(0.0,
                                  $1 * mastery_score + $2 * $3))::numeric, 4),
            attempt_count   = attempt_count + 1,
            error_count     = error_count + CASE WHEN $3 < 0.5 THEN 1 ELSE 0 END,
            last_reviewed   = NOW(),
            next_review_due = NOW() + make_interval(days =>
                                  GREATEST(1, (6 * LEAST(1.0, GREATEST(0.0,
                                      $1 * mastery_score + $2 * $3)) / 0.3)::int)),
            next_review_date = NOW() + make_interval(days =>
                                  GREATEST(1, (6 * LEAST(1.0, GREATEST(0.0,
                                      $1 * mastery_score + $2 * $3)) / 0.3)::int)),
            updated_at      = NOW(),
            error_pattern_array = CASE
                WHEN $6::text IS NOT NULL
                THEN jsonb_set(
                    COALESCE(error_pattern_array, '{}'),
                    ARRAY[$6::text],
                    to_jsonb(COALESCE(
                        (COALESCE(error_pattern_array,'{}') ->> $6)::int, 0
                    ) + 1)
                )
                ELSE COALESCE(error_pattern_array, '{}')
            END
        WHERE student_id = $4 AND concept_id = $5
        RETURNING mastery_score, error_count, attempt_count,
                  last_reviewed, next_review_due
        """,
        _ALPHA_OLD,
        _ALPHA_NEW,
        performance_score,
        student_id,
        concept_id,
        mistake_tag,
    )

    if updated is None:
        logger.warning(
            "No concept_mastery row for student=%s concept=%s — skipping",
            student_id, concept_id,
        )
        return None

    new_mastery = float(updated["mastery_score"])
    interval_days = max(1, int(6 * new_mastery / 0.3))

    logger.info(
        "Mastery updated: student=%s concept=%s  new=%.3f  (perf=%.2f)",
        student_id, concept_id, new_mastery, performance_score,
    )

    return {
        "concept_id": concept_id,
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
