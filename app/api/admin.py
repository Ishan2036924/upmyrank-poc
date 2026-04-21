"""
Admin metrics API — pedagogy quality dashboard.

GET  /admin/is_admin                  — check if authenticated student is admin
GET  /admin/metrics?days=7            — Socratic adherence, retrieval similarity, latency P95
GET  /admin/judge-metrics?days=7      — 4-dimension judge evaluation averages
GET  /admin/platform-health?days=7    — student counts, session counts, retention, subject dist
GET  /admin/conversation-quality?days=7 — per-turn quality scores from conversation_turn_quality
GET  /admin/response-quality?days=7   — judge_evaluations breakdown by subject + trend
GET  /admin/system-performance?days=7 — latency percentiles, agent steps, slow sessions
GET  /admin/user-feedback?days=7      — thumbs up/down from response_feedback
GET  /admin/knowledge-base            — chunk counts + JEE problem counts
GET  /admin/student-insights?days=30  — mastery, stuck students, hint escalation
POST /admin/diagnostics               — run all health checks
POST /admin/quality-digest            — LLM-generated diagnosis from worst turns
GET  /admin/quality-report?days=7     — aggregate + worst turns + thumbs (legacy)
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import uuid
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel

from app.config import settings
from app.db.database import get_pool
from app.middleware.auth import get_current_student_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ── Admin gate ────────────────────────────────────────────────────────────────

@router.get("/is_admin")
async def check_admin(
    student_id: str = Depends(get_current_student_id),
    db=Depends(get_pool),
    authorization: str = Header(None),
):
    """Return whether the authenticated student is a configured admin.

    Checks, in order:
      1. `students.email` column (fast path — populated for new signups)
      2. Supabase JWT `user.email` claim (fallback for pre-email-migration users)
      3. Legacy `admin_student_id` UUID match (backward compat)

    Every decision is logged so Render logs reveal the exact mismatch.
    """
    # Parse allowed admin emails from env
    allowed_emails: list[str] = [
        e.strip().lower()
        for e in settings.admin_emails.split(",")
        if e.strip()
    ]
    logger.info(
        "is_admin: student_id=%s admin_emails_configured=%d (%r)",
        student_id, len(allowed_emails), allowed_emails,
    )

    is_admin = False
    student_email = ""

    # ── 1. Try DB email column ───────────────────────────────────────────────
    if allowed_emails:
        try:
            row = await db.fetchrow(
                "SELECT email FROM students WHERE id = $1",
                uuid.UUID(str(student_id)),
            )
            student_email = (row["email"] or "").lower() if row else ""
            logger.info(
                "is_admin: DB email lookup student=%s email=%r",
                student_id, student_email,
            )
            if student_email and student_email in allowed_emails:
                is_admin = True
        except Exception as exc:
            logger.warning("is_admin: DB email lookup failed: %s", exc)

    # ── 2. Fallback: fetch email from Supabase JWT ───────────────────────────
    # Covers students who signed up before the email-backfill migration —
    # students.email is NULL for them but the Supabase auth record has it.
    if not is_admin and allowed_emails and authorization and authorization.startswith("Bearer "):
        try:
            from app.middleware.auth import _get_supabase
            token = authorization.removeprefix("Bearer ").strip()
            client = _get_supabase()
            jwt_resp = await asyncio.to_thread(client.auth.get_user, token)
            jwt_email = (jwt_resp.user.email or "").lower() if jwt_resp and jwt_resp.user else ""
            logger.info(
                "is_admin: JWT email fallback student=%s jwt_email=%r",
                student_id, jwt_email,
            )
            if jwt_email and jwt_email in allowed_emails:
                is_admin = True
                # Opportunistically backfill the DB so future requests skip the JWT call
                if not student_email:
                    try:
                        await db.execute(
                            "UPDATE students SET email = $1 WHERE id = $2 AND (email IS NULL OR email = '')",
                            jwt_email, uuid.UUID(str(student_id)),
                        )
                        logger.info("is_admin: backfilled email for student=%s", student_id)
                    except Exception as exc:
                        logger.warning("is_admin: email backfill failed (non-fatal): %s", exc)
        except Exception as exc:
            logger.warning("is_admin: JWT email fallback failed: %s", exc)

    # ── 3. Legacy: exact UUID match via ADMIN_STUDENT_ID ─────────────────────
    if not is_admin and settings.admin_student_id:
        if str(student_id) == settings.admin_student_id:
            is_admin = True
            logger.info("is_admin: matched via legacy ADMIN_STUDENT_ID")

    logger.info("is_admin: FINAL decision student=%s is_admin=%s", student_id, is_admin)
    return {"is_admin": is_admin}


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
    socratic_adherence_rate: float
    avg_retrieval_similarity: Optional[float]
    latency_p95_ms: Optional[int]
    topics: List[TopicMetric]


# ── Legacy endpoints (kept for backward compat) ───────────────────────────────

@router.get("/metrics", response_model=AdminMetrics)
async def get_admin_metrics(
    days: int = Query(7, ge=1, le=90),
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    global_row = await db.fetchrow(
        f"""
        SELECT COUNT(*) AS total_scored,
               AVG(se.scaffolding_score)::FLOAT AS avg_score,
               AVG(se.retrieval_similarity)::FLOAT AS avg_retrieval,
               PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY se.response_latency_ms)::INT AS latency_p95
        FROM session_events se
        WHERE se.scaffolding_score IS NOT NULL
          AND se.created_at >= NOW() - INTERVAL '{days} days'
        """
    )
    total_scored = int(global_row["total_scored"] or 0)
    adherence_row = await db.fetchrow(
        f"""
        SELECT COUNT(*) AS adherent
        FROM session_events se
        WHERE se.scaffolding_score IS NOT NULL AND se.scaffolding_score >= 1
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
    topic_rows = await db.fetch(
        f"""
        SELECT COALESCE(ds.topic, 'Unknown') AS topic,
               AVG(se.scaffolding_score)::FLOAT AS avg_score,
               COUNT(*) AS session_count,
               AVG(se.retrieval_similarity)::FLOAT AS avg_retrieval,
               AVG(se.response_latency_ms)::FLOAT AS avg_latency
        FROM session_events se
        JOIN doubt_sessions ds ON ds.id = se.session_id
        WHERE se.scaffolding_score IS NOT NULL
          AND se.created_at >= NOW() - INTERVAL '{days} days'
        GROUP BY ds.topic ORDER BY avg_score ASC
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
                round(float(row["avg_retrieval"]), 4) if row["avg_retrieval"] is not None else None
            ),
            avg_latency_ms=(
                int(math.ceil(float(row["avg_latency"]))) if row["avg_latency"] is not None else None
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


@router.get("/judge-metrics")
async def get_judge_metrics(
    days: int = Query(7, ge=1, le=90),
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    row = await db.fetchrow(
        f"""
        SELECT COUNT(*) AS total_evaluated,
               AVG(pedagogical_score)::FLOAT AS avg_pedagogical,
               AVG(factual_score)::FLOAT AS avg_factual,
               AVG(context_relevance_score)::FLOAT AS avg_context_relevance,
               AVG(hint_appropriateness_score)::FLOAT AS avg_hint_appropriateness,
               AVG(overall_score)::FLOAT AS avg_overall
        FROM judge_evaluations
        WHERE evaluated_at >= NOW() - INTERVAL '{days} days' AND overall_score >= 0
        """
    )
    total = int(row["total_evaluated"] or 0)

    def _sr(val, digits: int = 4) -> Optional[float]:
        return round(float(val), digits) if val is not None else None

    return {
        "period_days":              days,
        "total_evaluated":          total,
        "avg_pedagogical_score":    _sr(row["avg_pedagogical"]),
        "avg_factual_score":        _sr(row["avg_factual"]),
        "avg_context_relevance":    _sr(row["avg_context_relevance"]),
        "avg_hint_appropriateness": _sr(row["avg_hint_appropriateness"]),
        "avg_overall_score":        _sr(row["avg_overall"]),
    }


# ── New dashboard endpoints ───────────────────────────────────────────────────

@router.get("/platform-health")
async def platform_health(
    days: int = Query(7, ge=1, le=90),
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    """Platform-level health metrics: student counts, sessions, retention, subject distribution."""

    # Totals (all time)
    totals = await db.fetchrow(
        """
        SELECT
          (SELECT COUNT(*) FROM students) AS total_students,
          (SELECT COUNT(*) FROM study_sessions) AS total_sessions,
          (SELECT COUNT(*) FROM doubt_blocks) AS total_doubts
        """
    )

    # Activity this period
    activity = await db.fetchrow(
        f"""
        SELECT
          COUNT(DISTINCT student_id) FILTER (WHERE DATE(started_at) = CURRENT_DATE) AS active_today,
          COUNT(DISTINCT student_id) FILTER (WHERE started_at >= NOW() - INTERVAL '7 days') AS active_this_week,
          COUNT(DISTINCT student_id) FILTER (WHERE started_at >= NOW() - INTERVAL '30 days') AS active_this_month,
          COUNT(*) FILTER (WHERE started_at >= NOW() - INTERVAL '{days} days') AS sessions_last_n,
          COUNT(DISTINCT student_id) FILTER (WHERE started_at >= NOW() - INTERVAL '{days} days') AS students_last_n
        FROM study_sessions
        """
    )

    # Doubts last N days
    doubts_n = await db.fetchval(
        f"SELECT COUNT(*) FROM doubt_blocks WHERE started_at >= NOW() - INTERVAL '{days} days'"
    )

    # Sessions per day (last 14 days)
    spd_rows = await db.fetch(
        """
        SELECT DATE(started_at) AS day, COUNT(*) AS cnt
        FROM study_sessions
        WHERE started_at >= NOW() - INTERVAL '14 days'
        GROUP BY day ORDER BY day DESC
        """
    )
    sessions_per_day = [{"date": str(r["day"]), "count": int(r["cnt"])} for r in spd_rows]

    # Subject distribution — use session_metrics which has the subject column
    subj_rows = await db.fetch(
        """
        SELECT subject, COUNT(*) AS cnt
        FROM session_metrics WHERE subject IS NOT NULL
        GROUP BY subject
        """
    )
    total_subj = sum(int(r["cnt"]) for r in subj_rows) or 1
    subject_distribution = {r["subject"]: round(int(r["cnt"]) / total_subj, 4) for r in subj_rows}

    # Avg session length + doubts per session
    perf = await db.fetchrow(
        """
        SELECT
          AVG(EXTRACT(EPOCH FROM (ended_at - started_at)) / 60)::FLOAT AS avg_session_min,
          AVG(doubt_count)::FLOAT AS avg_doubts
        FROM study_sessions
        WHERE ended_at IS NOT NULL
        """
    )

    # Onboarding completion
    onb = await db.fetchrow(
        """
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE onboarding_completed = TRUE) AS completed
        FROM students
        """
    )
    onb_rate = (int(onb["completed"] or 0) / int(onb["total"] or 1))

    # Day-1 retention
    d1 = await db.fetchval(
        """
        SELECT COUNT(DISTINCT s.id) FROM students s
        WHERE EXISTS (
          SELECT 1 FROM study_sessions ss WHERE ss.student_id = s.id
          AND ss.started_at BETWEEN s.created_at + INTERVAL '1 day' AND s.created_at + INTERVAL '2 days'
        )
        """
    )
    d7 = await db.fetchval(
        """
        SELECT COUNT(DISTINCT s.id) FROM students s
        WHERE EXISTS (
          SELECT 1 FROM study_sessions ss WHERE ss.student_id = s.id
          AND ss.started_at >= s.created_at + INTERVAL '7 days'
        )
        """
    )
    total_students = int(totals["total_students"] or 0)

    return {
        "total_students":           total_students,
        "total_sessions":           int(totals["total_sessions"] or 0),
        "total_doubts":             int(totals["total_doubts"] or 0),
        "students_last_n_days":     int(activity["students_last_n"] or 0),
        "sessions_last_n_days":     int(activity["sessions_last_n"] or 0),
        "doubts_last_n_days":       int(doubts_n or 0),
        "active_today":             int(activity["active_today"] or 0),
        "active_this_week":         int(activity["active_this_week"] or 0),
        "active_this_month":        int(activity["active_this_month"] or 0),
        "sessions_per_day":         sessions_per_day,
        "subject_distribution":     subject_distribution,
        "avg_session_length_minutes": round(float(perf["avg_session_min"] or 0), 2),
        "avg_doubts_per_session":   round(float(perf["avg_doubts"] or 0), 2),
        "onboarding_completion_rate": round(onb_rate, 4),
        "retention_day1":           round(int(d1 or 0) / max(total_students, 1), 4),
        "retention_day7":           round(int(d7 or 0) / max(total_students, 1), 4),
        "period_days":              days,
    }


@router.get("/conversation-quality")
async def conversation_quality(
    days: int = Query(7, ge=1, le=90),
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    """Per-turn quality metrics from conversation_turn_quality table."""

    agg = await db.fetchrow(
        f"""
        SELECT
          COUNT(*) AS total_turns,
          ROUND(AVG(validation_score)::NUMERIC, 2) AS avg_validation,
          ROUND(AVG(appropriateness)::NUMERIC, 2) AS avg_appropriateness,
          ROUND(100.0 * SUM(CASE WHEN restart_detected THEN 1 ELSE 0 END)::NUMERIC
                / NULLIF(COUNT(*), 0), 1) AS restart_pct,
          ROUND(100.0 * SUM(CASE WHEN single_question THEN 1 ELSE 0 END)::NUMERIC
                / NULLIF(COUNT(*), 0), 1) AS single_q_pct
        FROM conversation_turn_quality
        WHERE scored_at >= NOW() - INTERVAL '{days} days'
        """
    )

    # Daily trend
    trend_rows = await db.fetch(
        f"""
        SELECT DATE(scored_at) AS day,
               ROUND(AVG(validation_score)::NUMERIC, 2) AS avg_val,
               ROUND(AVG(appropriateness)::NUMERIC, 2) AS avg_app
        FROM conversation_turn_quality
        WHERE scored_at >= NOW() - INTERVAL '{days} days'
        GROUP BY day ORDER BY day ASC
        """
    )
    quality_trend = [
        {"date": str(r["day"]), "avg_validation": float(r["avg_val"] or 0), "avg_appropriateness": float(r["avg_app"] or 0)}
        for r in trend_rows
    ]

    # Worst 10 turns
    worst_rows = await db.fetch(
        f"""
        SELECT ctq.doubt_session_id, ctq.turn_index, ctq.student_message, ctq.ai_response,
               ctq.validation_score, ctq.appropriateness, ctq.restart_detected,
               ctq.single_question, ctq.judge_rationale,
               ds.subject, ds.current_hint_level AS hint_level
        FROM conversation_turn_quality ctq
        LEFT JOIN doubt_sessions ds ON ds.id = ctq.doubt_session_id
        WHERE ctq.scored_at >= NOW() - INTERVAL '{days} days'
          AND (ctq.validation_score = 0 OR ctq.restart_detected = TRUE OR ctq.appropriateness = 0)
        ORDER BY (COALESCE(ctq.validation_score, 0) + COALESCE(ctq.appropriateness, 0)) ASC,
                 ctq.scored_at DESC
        LIMIT 10
        """
    )
    worst_turns = [_turn_row(r) for r in worst_rows]

    # Best 10 turns
    best_rows = await db.fetch(
        f"""
        SELECT ctq.doubt_session_id, ctq.turn_index, ctq.student_message, ctq.ai_response,
               ctq.validation_score, ctq.appropriateness, ctq.restart_detected,
               ctq.single_question, ctq.judge_rationale,
               ds.subject, ds.current_hint_level AS hint_level
        FROM conversation_turn_quality ctq
        LEFT JOIN doubt_sessions ds ON ds.id = ctq.doubt_session_id
        WHERE ctq.scored_at >= NOW() - INTERVAL '{days} days'
          AND ctq.validation_score = 2 AND ctq.appropriateness = 2
          AND ctq.restart_detected = FALSE AND ctq.single_question = TRUE
        ORDER BY ctq.scored_at DESC
        LIMIT 10
        """
    )
    best_turns = [_turn_row(r) for r in best_rows]

    return {
        "period_days":          days,
        "total_turns_scored":   int(agg["total_turns"] or 0),
        "avg_validation_score": float(agg["avg_validation"] or 0),
        "avg_appropriateness":  float(agg["avg_appropriateness"] or 0),
        "restart_rate_pct":     float(agg["restart_pct"] or 0),
        "single_q_compliance_pct": float(agg["single_q_pct"] or 0),
        "quality_trend":        quality_trend,
        "worst_turns":          worst_turns,
        "best_turns":           best_turns,
    }


def _turn_row(r) -> dict:
    return {
        "doubt_session_id": str(r["doubt_session_id"]),
        "turn_index":        int(r["turn_index"]),
        "student_message":   r["student_message"],
        "ai_response":       r["ai_response"],
        "validation_score":  r["validation_score"],
        "appropriateness":   r["appropriateness"],
        "restart_detected":  r["restart_detected"],
        "single_question":   r["single_question"],
        "judge_rationale":   r["judge_rationale"],
        "subject":           r.get("subject"),
        "hint_level":        r.get("hint_level"),
    }


@router.get("/response-quality")
async def response_quality(
    days: int = Query(7, ge=1, le=90),
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    """4-dim judge evaluation breakdown + per-subject analysis + trend."""

    overall = await db.fetchrow(
        f"""
        SELECT COUNT(*) AS total,
               AVG(pedagogical_score)::FLOAT AS avg_ped,
               AVG(factual_score)::FLOAT AS avg_fac,
               AVG(context_relevance_score)::FLOAT AS avg_ctx,
               AVG(hint_appropriateness_score)::FLOAT AS avg_hint,
               AVG(overall_score)::FLOAT AS avg_overall
        FROM judge_evaluations
        WHERE evaluated_at >= NOW() - INTERVAL '{days} days' AND overall_score >= 0
        """
    )

    subj_rows = await db.fetch(
        f"""
        SELECT ds.subject,
               AVG(je.pedagogical_score)::FLOAT AS avg_ped,
               AVG(je.factual_score)::FLOAT AS avg_fac,
               AVG(je.overall_score)::FLOAT AS avg_overall,
               COUNT(*) AS cnt
        FROM judge_evaluations je
        JOIN doubt_sessions ds ON ds.id = je.doubt_session_id
        WHERE je.evaluated_at >= NOW() - INTERVAL '{days} days' AND je.overall_score >= 0
          AND ds.subject IS NOT NULL
        GROUP BY ds.subject
        """
    )
    by_subject: Dict[str, Any] = {}
    for r in subj_rows:
        by_subject[r["subject"]] = {
            "avg_pedagogical": _r(r["avg_ped"]),
            "avg_factual":     _r(r["avg_fac"]),
            "avg_overall":     _r(r["avg_overall"]),
            "count":           int(r["cnt"]),
        }

    trend_rows = await db.fetch(
        f"""
        SELECT DATE(evaluated_at) AS day, AVG(overall_score)::FLOAT AS avg_overall
        FROM judge_evaluations
        WHERE evaluated_at >= NOW() - INTERVAL '{days} days' AND overall_score >= 0
        GROUP BY day ORDER BY day ASC
        """
    )
    score_trend = [{"date": str(r["day"]), "avg_overall": _r(r["avg_overall"])} for r in trend_rows]

    return {
        "period_days":          days,
        "total_evaluated":      int(overall["total"] or 0),
        "avg_pedagogical":      _r(overall["avg_ped"]),
        "avg_factual":          _r(overall["avg_fac"]),
        "avg_context_relevance":_r(overall["avg_ctx"]),
        "avg_hint_appropriateness": _r(overall["avg_hint"]),
        "avg_overall":          _r(overall["avg_overall"]),
        "by_subject":           by_subject,
        "score_trend":          score_trend,
    }


@router.get("/system-performance")
async def system_performance(
    days: int = Query(7, ge=1, le=90),
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    """Latency percentiles, agent steps distribution, slowest sessions."""

    ret_perc = await db.fetchrow(
        f"""
        SELECT
          PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY retrieval_latency_ms)::INT AS p50,
          PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY retrieval_latency_ms)::INT AS p95,
          PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY retrieval_latency_ms)::INT AS p99
        FROM session_metrics
        WHERE created_at >= NOW() - INTERVAL '{days} days'
          AND retrieval_latency_ms IS NOT NULL
        """
    )
    llm_perc = await db.fetchrow(
        f"""
        SELECT
          PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY response_latency_ms)::INT AS p50,
          PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_latency_ms)::INT AS p95,
          PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_latency_ms)::INT AS p99
        FROM session_events
        WHERE created_at >= NOW() - INTERVAL '{days} days'
          AND response_latency_ms IS NOT NULL
        """
    )

    # Agent steps distribution
    steps_rows = await db.fetch(
        f"""
        SELECT agent_steps, COUNT(*) AS cnt
        FROM session_metrics
        WHERE created_at >= NOW() - INTERVAL '{days} days' AND agent_steps IS NOT NULL
        GROUP BY agent_steps ORDER BY agent_steps
        """
    )
    agent_steps_dist = {str(int(r["agent_steps"])): int(r["cnt"]) for r in steps_rows}

    # Slowest 5 sessions
    slow_rows = await db.fetch(
        f"""
        SELECT sm.retrieval_latency_ms, ds.id AS doubt_session_id, ds.subject
        FROM session_metrics sm
        JOIN doubt_sessions ds ON ds.id = sm.doubt_session_id
        WHERE sm.created_at >= NOW() - INTERVAL '{days} days'
          AND sm.retrieval_latency_ms IS NOT NULL
        ORDER BY sm.retrieval_latency_ms DESC
        LIMIT 5
        """
    )
    slowest = [
        {"doubt_session_id": str(r["doubt_session_id"]), "subject": r["subject"],
         "retrieval_latency_ms": int(r["retrieval_latency_ms"])}
        for r in slow_rows
    ]

    # Per-subject latency
    subj_lat_rows = await db.fetch(
        f"""
        SELECT ds.subject,
               AVG(sm.retrieval_latency_ms)::INT AS avg_ret,
               AVG(se.response_latency_ms)::INT AS avg_llm
        FROM session_metrics sm
        JOIN doubt_sessions ds ON ds.id = sm.doubt_session_id
        LEFT JOIN session_events se ON se.session_id = ds.id
        WHERE sm.created_at >= NOW() - INTERVAL '{days} days' AND ds.subject IS NOT NULL
        GROUP BY ds.subject
        """
    )
    latency_by_subject: Dict[str, Any] = {
        r["subject"]: {"avg_retrieval_ms": r["avg_ret"], "avg_llm_ms": r["avg_llm"]}
        for r in subj_lat_rows
    }

    # Daily trend
    trend_rows = await db.fetch(
        f"""
        SELECT DATE(sm.created_at) AS day,
               AVG(sm.retrieval_latency_ms)::FLOAT AS avg_ret,
               AVG(se.response_latency_ms)::FLOAT AS avg_llm
        FROM session_metrics sm
        JOIN doubt_sessions ds ON ds.id = sm.doubt_session_id
        LEFT JOIN session_events se ON se.session_id = ds.id
        WHERE sm.created_at >= NOW() - INTERVAL '{days} days'
        GROUP BY day ORDER BY day ASC
        """
    )
    latency_trend = [
        {"date": str(r["day"]), "avg_retrieval_ms": _r(r["avg_ret"]), "avg_llm_ms": _r(r["avg_llm"])}
        for r in trend_rows
    ]

    def _pi(val) -> Optional[int]:
        return int(val) if val is not None else None

    return {
        "period_days":              days,
        "retrieval_latency_p50":    _pi(ret_perc["p50"]),
        "retrieval_latency_p95":    _pi(ret_perc["p95"]),
        "retrieval_latency_p99":    _pi(ret_perc["p99"]),
        "llm_latency_p50":          _pi(llm_perc["p50"]),
        "llm_latency_p95":          _pi(llm_perc["p95"]),
        "llm_latency_p99":          _pi(llm_perc["p99"]),
        "agent_steps_distribution": agent_steps_dist,
        "slowest_sessions":         slowest,
        "latency_by_subject":       latency_by_subject,
        "latency_trend":            latency_trend,
    }


@router.get("/user-feedback")
async def user_feedback(
    days: int = Query(7, ge=1, le=90),
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    """Thumbs up/down sentiment from response_feedback."""

    agg = await db.fetchrow(
        f"""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE rating = 'thumbs_up') AS thumbs_up,
               COUNT(*) FILTER (WHERE rating = 'thumbs_down') AS thumbs_down
        FROM response_feedback
        WHERE created_at >= NOW() - INTERVAL '{days} days'
        """
    )
    total = int(agg["total"] or 0)
    up = int(agg["thumbs_up"] or 0)
    down = int(agg["thumbs_down"] or 0)

    subj_rows = await db.fetch(
        f"""
        SELECT ds.subject,
               COUNT(*) FILTER (WHERE rf.rating = 'thumbs_up') AS up,
               COUNT(*) FILTER (WHERE rf.rating = 'thumbs_down') AS down
        FROM response_feedback rf
        JOIN doubt_sessions ds ON ds.id = rf.doubt_session_id
        WHERE rf.created_at >= NOW() - INTERVAL '{days} days' AND ds.subject IS NOT NULL
        GROUP BY ds.subject
        """
    )
    by_subject: Dict[str, Any] = {
        r["subject"]: {"thumbs_up": int(r["up"] or 0), "thumbs_down": int(r["down"] or 0)}
        for r in subj_rows
    }

    # Students who had sessions but never gave feedback
    no_feedback_count = await db.fetchval(
        f"""
        SELECT COUNT(DISTINCT ss.student_id)
        FROM study_sessions ss
        WHERE ss.started_at >= NOW() - INTERVAL '{days} days'
          AND NOT EXISTS (
            SELECT 1 FROM response_feedback rf
            WHERE rf.student_id = ss.student_id
              AND rf.created_at >= NOW() - INTERVAL '{days} days'
          )
        """
    )

    # Pearson correlation between judge overall_score and thumbs (1=up, 0=down)
    corr_rows = await db.fetch(
        f"""
        SELECT je.overall_score,
               CASE WHEN rf.rating = 'thumbs_up' THEN 1.0 ELSE 0.0 END AS thumbs_val
        FROM judge_evaluations je
        JOIN response_feedback rf ON rf.doubt_session_id = je.doubt_session_id
        WHERE je.evaluated_at >= NOW() - INTERVAL '{days} days' AND je.overall_score >= 0
        """
    )
    correlation: Optional[float] = None
    if len(corr_rows) >= 5:
        scores = [float(r["overall_score"]) for r in corr_rows]
        thumbs = [float(r["thumbs_val"]) for r in corr_rows]
        try:
            correlation = _pearson(scores, thumbs)
        except Exception:
            pass

    return {
        "period_days":              days,
        "total_feedback":           total,
        "thumbs_up_count":          up,
        "thumbs_down_count":        down,
        "thumbs_up_pct":            round(up / max(total, 1) * 100, 1),
        "by_subject":               by_subject,
        "students_without_feedback": int(no_feedback_count or 0),
        "judge_thumbs_correlation": round(correlation, 4) if correlation is not None else None,
    }


@router.get("/knowledge-base")
async def knowledge_base(
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    """Knowledge chunk counts and JEE problem coverage."""

    # Total + per-subject
    total_chunks = await db.fetchval("SELECT COUNT(*) FROM knowledge_chunks")

    subj_rows = await db.fetch(
        """
        SELECT subject, COUNT(*) AS cnt
        FROM knowledge_chunks GROUP BY subject ORDER BY cnt DESC
        """
    )
    by_subject: Dict[str, Any] = {}
    for r in subj_rows:
        subj = r["subject"] or "Unknown"
        # Per-chapter breakdown
        chap_rows = await db.fetch(
            "SELECT chapter, COUNT(*) AS cnt FROM knowledge_chunks WHERE subject = $1 GROUP BY chapter ORDER BY cnt DESC",
            r["subject"],
        )
        by_subject[subj] = {
            "count": int(r["cnt"]),
            "chapters": [{"chapter": cr["chapter"] or "Unknown", "count": int(cr["cnt"])} for cr in chap_rows],
        }

    # JEE problems
    jee_total = await db.fetchval("SELECT COUNT(*) FROM jee_problems")
    jee_subj_rows = await db.fetch(
        "SELECT subject, COUNT(*) AS cnt FROM jee_problems GROUP BY subject"
    )
    jee_by_subject = {r["subject"]: int(r["cnt"]) for r in jee_subj_rows}

    # Quality checks
    null_embeddings = await db.fetchval(
        "SELECT COUNT(*) FROM knowledge_chunks WHERE embedding IS NULL"
    )

    return {
        "total_chunks":         int(total_chunks or 0),
        "by_subject":           by_subject,
        "jee_problems_count":   int(jee_total or 0),
        "jee_by_subject":       jee_by_subject,
        "null_embeddings_count": int(null_embeddings or 0),
    }


@router.get("/study-path")
async def study_path_usage(
    days: int = Query(7, ge=1, le=90),
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    """v0.20.2: Study Path usage rollup for the admin dashboard.

    Returns:
        - top_cards: top 10 (subject, topic) pairs by view count in last N days
        - daily_views: views per day for sparkline
        - topic_shifts: count of v0.20 topic-shift demotions in last N days
                         (sourced from doubt_blocks closed by drift)
        - override_rate: fraction of card views that hit a hand-curated override
    """
    # Top 10 cards by view count
    top_cards = await db.fetch(
        """
        SELECT
            (payload->>'subject') AS subject,
            (payload->>'topic')   AS topic,
            COUNT(DISTINCT student_id)::int AS unique_students,
            COUNT(*)::int                    AS view_count,
            MAX(created_at)                  AS last_viewed
        FROM session_events
        WHERE event_type = 'study_card_view'
          AND created_at > NOW() - ($1 || ' days')::interval
        GROUP BY 1, 2
        ORDER BY view_count DESC
        LIMIT 10
        """,
        str(days),
    )

    # Daily view sparkline
    daily = await db.fetch(
        """
        SELECT date_trunc('day', created_at)::date AS day,
               COUNT(*)::int AS views
        FROM session_events
        WHERE event_type = 'study_card_view'
          AND created_at > NOW() - ($1 || ' days')::interval
        GROUP BY 1 ORDER BY 1
        """,
        str(days),
    )

    # Override hit-rate (fraction of views that came from hand-polished cards)
    rate_row = await db.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE (payload->>'is_override')::boolean = TRUE)::int AS overrides,
            COUNT(*)::int AS total
        FROM session_events
        WHERE event_type = 'study_card_view'
          AND created_at > NOW() - ($1 || ' days')::interval
        """,
        str(days),
    )

    # Topic-shift count from doubt_blocks (approx: blocks that ended without
    # being solved AND had only the original session_terminal event with no
    # mid-session drift signal). Use the new drift_topic field.
    drift_count = await db.fetchval(
        """
        SELECT COUNT(*)::int
        FROM session_events
        WHERE event_type = 'session_terminal'
          AND payload ? 'drift_topic'
          AND payload->>'drift_topic' IS NOT NULL
          AND payload->>'drift_topic' <> ''
          AND created_at > NOW() - ($1 || ' days')::interval
        """,
        str(days),
    )

    return {
        "days": days,
        "top_cards": [
            {
                "subject":         r["subject"],
                "topic":           r["topic"],
                "unique_students": int(r["unique_students"] or 0),
                "view_count":      int(r["view_count"] or 0),
                "last_viewed":     r["last_viewed"].isoformat() if r["last_viewed"] else None,
            }
            for r in top_cards
        ],
        "daily_views": [
            {"day": r["day"].isoformat(), "views": int(r["views"])}
            for r in daily
        ],
        "override_hit_rate": (
            float(rate_row["overrides"]) / float(rate_row["total"])
            if rate_row and rate_row["total"] else 0.0
        ),
        "total_views": int(rate_row["total"] or 0) if rate_row else 0,
        "topic_shift_drift_count": int(drift_count or 0),
    }


@router.get("/student-insights")
async def student_insights(
    days: int = Query(30, ge=1, le=180),
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    """Mastery averages, stuck students, hint escalation by topic."""

    # Mastery overview
    mastery_agg = await db.fetchrow(
        "SELECT AVG(mastery_score)::FLOAT AS avg_mastery FROM concept_mastery"
    )
    subj_mastery_rows = await db.fetch(
        """
        SELECT ds.subject, AVG(cm.mastery_score)::FLOAT AS avg_mastery
        FROM concept_mastery cm
        JOIN doubt_sessions ds ON ds.student_id = cm.student_id
        WHERE ds.subject IS NOT NULL
        GROUP BY ds.subject
        """
    )
    mastery_by_subject = {r["subject"]: _r(r["avg_mastery"]) for r in subj_mastery_rows}

    total_students = await db.fetchval("SELECT COUNT(*) FROM students")

    # Stuck students: 3+ doubt blocks on same topic
    stuck_rows = await db.fetch(
        f"""
        SELECT db.student_id, db.topic, COUNT(*) AS session_count, MAX(db.started_at) AS last_seen
        FROM doubt_blocks db
        WHERE db.started_at >= NOW() - INTERVAL '{days} days' AND db.topic IS NOT NULL
        GROUP BY db.student_id, db.topic
        HAVING COUNT(*) >= 3
        ORDER BY session_count DESC
        LIMIT 20
        """
    )
    stuck_students = [
        {
            "student_id": str(r["student_id"]),
            "topic": r["topic"],
            "session_count": int(r["session_count"]),
            "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
        }
        for r in stuck_rows
    ]

    # Low-gain students: many sessions but low mastery
    low_gain_rows = await db.fetch(
        f"""
        SELECT ss.student_id, COUNT(DISTINCT ss.study_session_id) AS session_count,
               AVG(cm.mastery_score)::FLOAT AS avg_mastery
        FROM study_sessions ss
        LEFT JOIN concept_mastery cm ON cm.student_id = ss.student_id
        WHERE ss.started_at >= NOW() - INTERVAL '{days} days'
        GROUP BY ss.student_id
        HAVING COUNT(DISTINCT ss.study_session_id) >= 3 AND AVG(cm.mastery_score) < 0.4
        ORDER BY avg_mastery ASC
        LIMIT 10
        """
    )
    low_gain = [
        {
            "student_id": str(r["student_id"]),
            "session_count": int(r["session_count"]),
            "avg_mastery": _r(r["avg_mastery"]),
        }
        for r in low_gain_rows
    ]

    # Hint escalation by topic
    esc_rows = await db.fetch(
        f"""
        SELECT ds.topic, AVG(ds.current_hint_level)::FLOAT AS avg_max_hint, COUNT(*) AS cnt
        FROM doubt_sessions ds
        WHERE ds.created_at >= NOW() - INTERVAL '{days} days'
          AND ds.current_hint_level >= 2 AND ds.topic IS NOT NULL
        GROUP BY ds.topic
        ORDER BY avg_max_hint DESC
        LIMIT 15
        """
    )
    hint_escalation = [
        {"topic": r["topic"], "avg_max_hint_level": _r(r["avg_max_hint"]), "count": int(r["cnt"])}
        for r in esc_rows
    ]

    return {
        "period_days":           days,
        "total_students":        int(total_students or 0),
        "avg_mastery_score":     _r(mastery_agg["avg_mastery"]),
        "mastery_by_subject":    mastery_by_subject,
        "stuck_students":        stuck_students,
        "low_gain_students":     low_gain,
        "hint_escalation_by_topic": hint_escalation,
    }


@router.post("/diagnostics")
async def run_diagnostics(
    request: Request,
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    """Run all system health checks. Never raises."""
    checks = []

    async def _check(name: str, fn) -> dict:
        try:
            result = await fn()
            return {"name": name, "status": result["status"], "detail": result["detail"], "value": result.get("value")}
        except Exception as exc:
            return {"name": name, "status": "error", "detail": str(exc), "value": None}

    # Table accessibility
    async def _tables():
        tables = [
            "students", "study_sessions", "doubt_sessions", "doubt_blocks",
            "session_events", "session_metrics", "knowledge_chunks", "jee_problems",
            "concept_mastery", "student_memory", "judge_evaluations",
            "response_feedback", "conversation_turn_quality",
        ]
        accessible = 0
        for t in tables:
            try:
                await db.fetchval(f"SELECT COUNT(*) FROM {t} LIMIT 1")
                accessible += 1
            except Exception:
                pass
        status = "ok" if accessible == len(tables) else ("warning" if accessible > 10 else "error")
        return {"status": status, "detail": f"{accessible}/{len(tables)} tables accessible", "value": accessible}

    # judge_evaluations recent activity
    async def _judge_recent():
        cnt = await db.fetchval(
            "SELECT COUNT(*) FROM judge_evaluations WHERE evaluated_at >= NOW() - INTERVAL '24 hours'"
        )
        cnt = int(cnt or 0)
        status = "ok" if cnt > 0 else "warning"
        detail = f"{cnt} evaluations in last 24h" + (" — bug suspected if sessions ran" if cnt == 0 else "")
        return {"status": status, "detail": detail, "value": cnt}

    # response_feedback recent
    async def _feedback_recent():
        cnt = await db.fetchval(
            "SELECT COUNT(*) FROM response_feedback WHERE created_at >= NOW() - INTERVAL '24 hours'"
        )
        cnt = int(cnt or 0)
        return {"status": "ok" if cnt > 0 else "warning", "detail": f"{cnt} feedback rows in last 24h", "value": cnt}

    # conversation_turn_quality recent
    async def _ctq_recent():
        cnt = await db.fetchval(
            "SELECT COUNT(*) FROM conversation_turn_quality WHERE scored_at >= NOW() - INTERVAL '24 hours'"
        )
        cnt = int(cnt or 0)
        return {"status": "ok" if cnt > 0 else "warning", "detail": f"{cnt} turn quality rows in last 24h", "value": cnt}

    # Null embeddings
    async def _null_embeddings():
        cnt = int(await db.fetchval("SELECT COUNT(*) FROM knowledge_chunks WHERE embedding IS NULL") or 0)
        status = "error" if cnt > 100 else ("warning" if cnt > 0 else "ok")
        return {"status": status, "detail": f"{cnt} chunks missing embeddings", "value": cnt}

    # Orphaned doubt sessions
    async def _orphaned():
        cnt = int(await db.fetchval(
            "SELECT COUNT(*) FROM doubt_sessions ds WHERE NOT EXISTS (SELECT 1 FROM doubt_blocks db WHERE db.doubt_session_id = ds.id)"
        ) or 0)
        return {"status": "ok" if cnt == 0 else "warning", "detail": f"{cnt} orphaned doubt_sessions", "value": cnt}

    # Slow sessions (>10s retrieval)
    async def _slow():
        cnt = int(await db.fetchval(
            "SELECT COUNT(*) FROM session_metrics WHERE retrieval_latency_ms > 10000 AND created_at >= NOW() - INTERVAL '7 days'"
        ) or 0)
        return {"status": "warning" if cnt > 5 else "ok", "detail": f"{cnt} sessions with retrieval > 10s in last 7d", "value": cnt}

    # Redis connectivity — create a fresh connection (Redis not stored in app.state)
    async def _redis():
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
            await r.ping()
            await r.aclose()
            return {"status": "ok", "detail": "Redis responded to PING", "value": True}
        except Exception as exc:
            return {"status": "error", "detail": f"Redis PING failed: {exc}", "value": False}

    check_fns = [
        ("table_accessibility", _tables),
        ("judge_evaluations_recent", _judge_recent),
        ("response_feedback_recent", _feedback_recent),
        ("conversation_turn_quality_active", _ctq_recent),
        ("null_embeddings", _null_embeddings),
        ("orphaned_doubt_sessions", _orphaned),
        ("slow_sessions", _slow),
        ("redis_connectivity", _redis),
    ]

    for name, fn in check_fns:
        checks.append(await _check(name, fn))

    worst = "ok"
    for c in checks:
        if c["status"] == "error":
            worst = "error"
            break
        if c["status"] == "warning":
            worst = "warning"

    return {"status": worst, "checks": checks, "ran_at": datetime.utcnow().isoformat() + "Z"}


@router.post("/quality-digest")
async def quality_digest(
    request: Request,
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    """LLM-generated diagnosis from worst conversation turns."""
    worst_rows = await db.fetch(
        """
        SELECT student_message, ai_response, validation_score, appropriateness,
               restart_detected, single_question, judge_rationale
        FROM conversation_turn_quality
        WHERE scored_at >= NOW() - INTERVAL '30 days'
          AND (validation_score = 0 OR restart_detected = TRUE OR appropriateness = 0)
        ORDER BY (COALESCE(validation_score, 0) + COALESCE(appropriateness, 0)) ASC
        LIMIT 10
        """
    )
    if not worst_rows:
        return {"diagnosis": "No poor-quality turns found in the last 30 days.", "main_pattern": "", "top_fix": "", "confidence": "low"}

    turns_text = ""
    for i, r in enumerate(worst_rows, 1):
        turns_text += (
            f"\nTurn {i}:\n"
            f"  Student: {r['student_message'][:300]}\n"
            f"  AI: {r['ai_response'][:300]}\n"
            f"  Scores: validation={r['validation_score']}, appropriateness={r['appropriateness']}, "
            f"restart={r['restart_detected']}, single_q={r['single_question']}\n"
            f"  Rationale: {r['judge_rationale']}\n"
        )

    prompt = (
        "You are reviewing AI tutor conversation quality data. "
        "Here are the 10 worst-scored conversation turns:\n"
        f"{turns_text}\n"
        "In 3 paragraphs, diagnose:\n"
        "1. The most common failure pattern (cite a specific example from the data)\n"
        "2. The specific prompt or logic gap causing it\n"
        "3. The single highest-leverage fix\n\n"
        'Return JSON only: {"diagnosis": "...", "main_pattern": "...", "top_fix": "...", "confidence": "high|medium|low"}'
    )

    try:
        client = request.app.state.socratic_engine._client
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        data = json.loads(raw)
        return data
    except Exception as exc:
        return {"diagnosis": f"Digest generation failed: {exc}", "main_pattern": "", "top_fix": "", "confidence": "low"}


@router.get("/quality-report")
async def quality_report(
    days: int = Query(7, ge=1, le=90),
    db=Depends(get_pool),
    _: str = Depends(get_current_student_id),
):
    """Aggregate quality report: per-turn scores + thumbs feedback."""
    agg = await db.fetchrow(
        f"""
        SELECT COUNT(*) AS total_turns,
               ROUND(AVG(validation_score)::NUMERIC, 2) AS avg_validation,
               ROUND(AVG(appropriateness)::NUMERIC, 2) AS avg_appropriateness,
               ROUND(100.0 * SUM(CASE WHEN restart_detected THEN 1 ELSE 0 END)::NUMERIC
                     / NULLIF(COUNT(*), 0), 1) AS restart_pct,
               ROUND(100.0 * SUM(CASE WHEN single_question THEN 1 ELSE 0 END)::NUMERIC
                     / NULLIF(COUNT(*), 0), 1) AS single_q_pct
        FROM conversation_turn_quality
        WHERE scored_at >= NOW() - INTERVAL '{days} days'
        """
    )
    worst = await db.fetch(
        f"""
        SELECT doubt_session_id, turn_index, student_message, ai_response,
               validation_score, appropriateness, restart_detected, single_question, judge_rationale
        FROM conversation_turn_quality
        WHERE scored_at >= NOW() - INTERVAL '{days} days'
          AND (validation_score = 0 OR restart_detected = TRUE OR appropriateness = 0)
        ORDER BY (COALESCE(validation_score, 0) + COALESCE(appropriateness, 0)) ASC, scored_at DESC
        LIMIT 5
        """
    )
    thumbs = await db.fetchrow(
        f"""
        SELECT COUNT(*) FILTER (WHERE rating = 'thumbs_up') AS thumbs_up,
               COUNT(*) FILTER (WHERE rating = 'thumbs_down') AS thumbs_down
        FROM response_feedback
        WHERE created_at >= NOW() - INTERVAL '{days} days'
        """
    )
    return {
        "period_days": days,
        "aggregate": {k: (float(v) if v is not None else None) for k, v in dict(agg).items()},
        "worst_turns": [dict(r) for r in worst],
        "feedback_signals": {"thumbs_up": int(thumbs["thumbs_up"] or 0), "thumbs_down": int(thumbs["thumbs_down"] or 0)},
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _r(val, digits: int = 4) -> Optional[float]:
    """Safe round — returns None for None input."""
    return round(float(val), digits) if val is not None else None


def _pearson(x: list[float], y: list[float]) -> Optional[float]:
    """Compute Pearson r between two equal-length lists."""
    n = len(x)
    if n < 2:
        return None
    mx, my = mean(x), mean(y)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    denom = (sum((xi - mx) ** 2 for xi in x) * sum((yi - my) ** 2 for yi in y)) ** 0.5
    return num / denom if denom != 0 else None
