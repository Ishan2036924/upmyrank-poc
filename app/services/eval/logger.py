"""
Eval logger — writes Judge LLM scores and retrieval metrics back to session_events.

Entry point:
    log_scaffolding_score(session_id, score, rationale, retrieval_similarity,
                          response_latency_ms, db)

Updates the most recent session_event row for the given session_id.
Never raises — all failures are logged as warnings.
"""
from __future__ import annotations

import logging
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)


async def log_scaffolding_score(
    session_id: str,
    score: int,
    rationale: str,
    db: asyncpg.Pool,
    retrieval_similarity: Optional[float] = None,
    response_latency_ms: Optional[int] = None,
) -> None:
    """
    UPDATE the most recent session_event for this session with eval metrics.

    Targets the latest row where event_type IN ('hint_requested', 'solution_revealed').
    Uses a subquery to handle LIMIT inside UPDATE (Postgres-compatible).

    Never raises.
    """
    if score == -1:
        # Judge failed — still log latency and similarity if available
        score_val = None
        rationale_val = "judge_failed"
    else:
        score_val = score
        rationale_val = rationale

    try:
        await db.execute(
            """
            UPDATE session_events
            SET scaffolding_score    = $2,
                retrieval_similarity = COALESCE($3, retrieval_similarity),
                response_latency_ms  = COALESCE($4, response_latency_ms)
            WHERE id = (
                SELECT id FROM session_events
                WHERE session_id = $1
                  AND event_type IN ('question_asked', 'hint_requested', 'solution_revealed')
                ORDER BY created_at DESC
                LIMIT 1
            )
            """,
            session_id,
            score_val,
            retrieval_similarity,
            response_latency_ms,
        )
        logger.debug(
            "Scaffolding score logged: session=%s score=%s latency=%sms similarity=%s",
            session_id, score_val, response_latency_ms, retrieval_similarity,
        )
    except Exception as exc:
        logger.warning("log_scaffolding_score failed (non-fatal): %s", exc)
