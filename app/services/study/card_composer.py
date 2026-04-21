"""
Concept Card composer — v0.20 dual-loop Mode 1.

Assembles a concept card for (subject, chapter, topic) on demand:

    notes    → top-3 NCERT chunks from hybrid Retriever
    practice → up to 3 problems from `problems` table filtered by topic
    pyqs     → up to 3 JEE past-year questions from `jee_problems`
    mastery  → current EMA mastery + last_reviewed for the student

Never generates LLM content. Everything is free; cost == DB + retriever.
Failures in one section do not poison others — each block is independent.
"""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional

import asyncpg

from app.services.rag.retriever import Retriever

logger = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _topic_query(subject: str, chapter: Optional[str], topic: str) -> str:
    """Build a retrieval query string biased toward the target topic."""
    parts = [topic]
    if chapter:
        parts.append(chapter)
    parts.append(subject)
    return " — ".join(p for p in parts if p)


async def _compose_notes(
    retriever: Retriever,
    subject: str,
    chapter: Optional[str],
    topic: str,
    k: int = 3,
) -> dict:
    """Top-k NCERT chunks as the Notes section. No LLM call."""
    try:
        query = _topic_query(subject, chapter, topic)
        rows = await retriever.search(query=query, k=k, subject=subject)
    except Exception as exc:
        logger.warning("notes retrieval failed: %s", exc)
        return {"chunks": [], "error": "retrieval_failed"}

    chunks: List[dict] = []
    for row in rows:
        md = row.get("metadata") or {}
        chunks.append({
            "heading":    md.get("section") or md.get("title") or chapter or topic,
            "text":       row.get("content", ""),
            "source":     md.get("source") or "NCERT",
            "similarity": float(row.get("similarity_score", 0.0)),
        })
    return {"chunks": chunks}


async def _compose_practice(
    pool: asyncpg.Pool,
    subject: str,
    topic: str,
    limit: int = 3,
) -> dict:
    """Up to `limit` problems from the `problems` table, topic-filtered."""
    try:
        rows = await pool.fetch(
            """
            SELECT id, question_text, question_latex, topic, subtopic,
                   difficulty, verified_answer
            FROM problems
            WHERE subject = $1
              AND ($2::text IS NULL OR topic ILIKE '%' || $2 || '%')
            ORDER BY RANDOM()
            LIMIT $3
            """,
            subject, topic, limit,
        )
    except Exception as exc:
        logger.warning("practice retrieval failed: %s", exc)
        return {"problems": [], "error": "retrieval_failed"}

    return {
        "problems": [
            {
                "problem_id":     str(r["id"]),
                "question_text":  r["question_text"],
                "question_latex": r["question_latex"],
                "topic":          r["topic"],
                "subtopic":       r["subtopic"],
                "difficulty":     r["difficulty"],
            }
            for r in rows
        ]
    }


async def _compose_pyqs(
    pool: asyncpg.Pool,
    subject: str,
    topic: str,
    limit: int = 3,
) -> dict:
    """Up to `limit` JEE PYQs matching subject + topic (ILIKE)."""
    try:
        rows = await pool.fetch(
            """
            SELECT problem_id, subject, topic, year, exam_type, difficulty,
                   problem_text, source_verified
            FROM jee_problems
            WHERE subject = $1
              AND ($2::text IS NULL OR topic ILIKE '%' || $2 || '%')
            ORDER BY year DESC NULLS LAST
            LIMIT $3
            """,
            subject, topic, limit,
        )
    except Exception as exc:
        # jee_problems may not exist in some deployments — non-fatal.
        logger.info("pyq retrieval returned no rows / table missing: %s", exc)
        return {"problems": []}

    return {
        "problems": [
            {
                "problem_id":     str(r["problem_id"]),
                "subject":        r["subject"],
                "topic":          r["topic"],
                "year":           r["year"],
                "exam_type":      r["exam_type"],
                "difficulty":     r["difficulty"],
                "problem_text":   r["problem_text"],
                "verified":       bool(r["source_verified"]),
            }
            for r in rows
        ]
    }


async def _compose_mastery(
    pool: asyncpg.Pool,
    student_id: str,
    topic: str,
) -> dict:
    """
    Current mastery snapshot for this student on this topic.

    Matches `concept_mastery` rows whose `subtopic` ILIKEs the topic. If
    multiple match, returns the average + most-recent last_reviewed.
    """
    try:
        row = await pool.fetchrow(
            """
            SELECT AVG(mastery_score)::float AS avg_score,
                   MAX(updated_at)           AS last_reviewed,
                   SUM(attempt_count)::int   AS attempts
            FROM concept_mastery
            WHERE student_id = $1
              AND EXISTS (
                  SELECT 1
                  FROM concepts c
                  WHERE c.concept_id = concept_mastery.concept_id
                    AND c.subtopic ILIKE '%' || $2 || '%'
              )
            """,
            uuid.UUID(student_id), topic,
        )
    except Exception as exc:
        # concepts table may be named differently in some migrations; fall back.
        logger.info("mastery lookup via concepts JOIN failed (%s), falling back", exc)
        try:
            row = await pool.fetchrow(
                """
                SELECT AVG(mastery_score)::float AS avg_score,
                       MAX(updated_at)           AS last_reviewed,
                       SUM(attempt_count)::int   AS attempts
                FROM concept_mastery
                WHERE student_id = $1
                """,
                uuid.UUID(student_id),
            )
        except Exception as exc2:
            logger.warning("mastery fallback also failed: %s", exc2)
            return {"current": None, "last_reviewed": None, "attempts": 0}

    if not row or row["avg_score"] is None:
        return {"current": None, "last_reviewed": None, "attempts": 0}
    return {
        "current":       round(float(row["avg_score"]), 3),
        "last_reviewed": row["last_reviewed"].isoformat() if row["last_reviewed"] else None,
        "attempts":      int(row["attempts"] or 0),
    }


# ── public entrypoint ────────────────────────────────────────────────────────

async def compose_concept_card(
    pool: asyncpg.Pool,
    retriever: Retriever,
    student_id: str,
    subject: str,
    chapter: Optional[str],
    topic: str,
) -> dict:
    """
    Build the full concept card response.

    Independent error handling per section — a missing jee_problems table
    will NOT block notes or practice from rendering.
    """
    notes    = await _compose_notes(retriever, subject, chapter, topic)
    practice = await _compose_practice(pool, subject, topic)
    pyqs     = await _compose_pyqs(pool, subject, topic)
    mastery  = await _compose_mastery(pool, student_id, topic)

    return {
        "subject":  subject,
        "chapter":  chapter,
        "topic":    topic,
        "notes":    notes,
        "practice": practice,
        "pyqs":     pyqs,
        "mastery":  mastery,
    }
