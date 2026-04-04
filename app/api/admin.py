"""
Admin metrics API — pedagogy quality dashboard.

GET /admin/metrics?days=7
    Returns Socratic adherence rate, avg retrieval similarity, latency P95,
    and per-topic breakdown from session_events.

No student auth required (internal/admin use only).
"""
from __future__ import annotations

import math
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.db.database import get_pool
from app.middleware.auth import get_current_student_id

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Response models ───────────────────────────────────────────────────────────

class TopicMetric(BaseModel):
    topic: str
    avg_score: float
    session_count: int
    avg_retrieval_similarity: Optional[float]
    avg_latency_ms: Optional[int]
    is_drifting: bool   # avg_score < 1.5


class AdminMetrics(BaseModel):
    period_days: int
    total_scored: int
    socratic_adherence_rate: float      # fraction of scored rows with score >= 1.5 intent
    avg_retrieval_similarity: Optional[float]
    latency_p95_ms: Optional[int]
    topics: List[TopicMetric]


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/metrics", response_model=AdminMetrics)
async def get_admin_metrics(
    days: int = Query(7, ge=1, le=90, description="Lookback window in days"),
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    """
    Aggregate eval metrics for the admin dashboard.

    - socratic_adherence_rate: fraction of scored events with scaffolding_score >= 1
      (score 0 = gave full solution; 1 or 2 = some Socratic quality)
    - avg_retrieval_similarity: mean cosine similarity from RAG retrieval
    - latency_p95_ms: 95th-percentile response latency
    - topics: per-topic breakdown, flagged if avg_score < 1.5
    """
    # ── Global aggregates ─────────────────────────────────────────────────────
    global_row = await db.fetchrow(
        f"""
        SELECT
            COUNT(*)                                         AS total_scored,
            AVG(se.scaffolding_score)::FLOAT                AS avg_score,
            AVG(se.retrieval_similarity)::FLOAT             AS avg_retrieval,
            PERCENTILE_CONT(0.95) WITHIN GROUP (
                ORDER BY se.response_latency_ms
            )::INT                                          AS latency_p95
        FROM session_events se
        WHERE se.scaffolding_score IS NOT NULL
          AND se.created_at >= NOW() - INTERVAL '{days} days'
        """
    )

    total_scored = int(global_row["total_scored"] or 0)

    # ── Adherence: fraction of scored rows where score >= 1 ───────────────────
    adherence_row = await db.fetchrow(
        f"""
        SELECT COUNT(*) AS adherent
        FROM session_events se
        WHERE se.scaffolding_score IS NOT NULL
          AND se.scaffolding_score >= 1
          AND se.created_at >= NOW() - INTERVAL '{days} days'
        """
    )
    adherent = int(adherence_row["adherent"] or 0)
    adherence_rate = (adherent / total_scored) if total_scored > 0 else 0.0

    avg_retrieval = (
        round(float(global_row["avg_retrieval"]), 4)
        if global_row["avg_retrieval"] is not None else None
    )
    latency_p95 = (
        int(global_row["latency_p95"])
        if global_row["latency_p95"] is not None else None
    )

    # ── Per-topic breakdown ───────────────────────────────────────────────────
    topic_rows = await db.fetch(
        f"""
        SELECT
            COALESCE(ds.topic, 'Unknown')                   AS topic,
            AVG(se.scaffolding_score)::FLOAT                AS avg_score,
            COUNT(*)                                         AS session_count,
            AVG(se.retrieval_similarity)::FLOAT             AS avg_retrieval,
            AVG(se.response_latency_ms)::FLOAT              AS avg_latency
        FROM session_events se
        JOIN doubt_sessions ds ON ds.id = se.session_id
        WHERE se.scaffolding_score IS NOT NULL
          AND se.created_at >= NOW() - INTERVAL '{days} days'
        GROUP BY ds.topic
        ORDER BY avg_score ASC
        """
    )

    topics: List[TopicMetric] = []
    for row in topic_rows:
        avg_s = float(row["avg_score"])
        topics.append(TopicMetric(
            topic=str(row["topic"]),
            avg_score=round(avg_s, 3),
            session_count=int(row["session_count"]),
            avg_retrieval_similarity=(
                round(float(row["avg_retrieval"]), 4)
                if row["avg_retrieval"] is not None else None
            ),
            avg_latency_ms=(
                int(math.ceil(float(row["avg_latency"])))
                if row["avg_latency"] is not None else None
            ),
            is_drifting=avg_s < 1.5,
        ))

    return AdminMetrics(
        period_days=days,
        total_scored=total_scored,
        socratic_adherence_rate=round(adherence_rate, 4),
        avg_retrieval_similarity=avg_retrieval,
        latency_p95_ms=latency_p95,
        topics=topics,
    )
