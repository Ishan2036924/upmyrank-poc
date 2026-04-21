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

import hashlib
import json
import logging
import re
import uuid
from pathlib import Path
from typing import List, Optional

import asyncpg

from app.services.rag.retriever import Retriever

logger = logging.getLogger(__name__)

# v0.21: editorial overrides for hand-polished concept cards.
# Loaded once at import; file is checked into the repo.
# Path: this module is at app/services/study/card_composer.py.
# parents[0]=study/, [1]=services/, [2]=app/, [3]=<repo root>.
_OVERRIDES_FILE = Path(__file__).resolve().parents[3] / "scripts" / "concept_card_overrides.json"


def _load_overrides() -> dict:
    try:
        if _OVERRIDES_FILE.is_file():
            with _OVERRIDES_FILE.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, dict):
                    return data
    except Exception as exc:
        logger.warning("concept_card_overrides load failed (non-fatal): %s", exc)
    return {}


_OVERRIDES = _load_overrides()


def _override_key(subject: str, topic: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")
    t = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return f"{s}__{t}"


# ── helpers ──────────────────────────────────────────────────────────────────

def _topic_query(subject: str, chapter: Optional[str], topic: str) -> str:
    """Build a retrieval query string biased toward the target topic."""
    parts = [topic]
    if chapter:
        parts.append(chapter)
    parts.append(subject)
    return " — ".join(p for p in parts if p)


def _normalise_for_dedup(text: str) -> str:
    """Lowercase + collapse whitespace + strip; first 200 chars are the key."""
    s = re.sub(r"\s+", " ", text or "").strip().lower()
    return s[:200]


async def _compose_notes(
    retriever: Retriever,
    subject: str,
    chapter: Optional[str],
    topic: str,
    k: int = 3,
) -> dict:
    """Top-k NCERT chunks as the Notes section. No LLM call.

    v0.21: prefers a hand-polished override from
    `scripts/concept_card_overrides.json` if one exists for this
    (subject, topic). Otherwise dedupes near-duplicate retriever results
    by hashed-prefix and prefers chunks with distinct section headings.
    """
    # ── Override path ─────────────────────────────────────────────────────
    override = _OVERRIDES.get(_override_key(subject, topic))
    if override and isinstance(override.get("notes_markdown"), str):
        return {
            "chunks": [{
                "heading":    override.get("heading") or topic,
                "text":       override["notes_markdown"],
                "source":     override.get("source") or "Editorial",
                "similarity": 1.0,
            }],
            "is_override": True,
        }

    # ── Auto path ─────────────────────────────────────────────────────────
    try:
        query = _topic_query(subject, chapter, topic)
        # Fetch wider, dedupe, return top-k unique.
        fetch_k = max(k * 3, 9)
        rows = await retriever.search(query=query, k=fetch_k, subject=subject)
    except Exception as exc:
        logger.warning("notes retrieval failed: %s", exc)
        return {"chunks": [], "error": "retrieval_failed"}

    seen_hashes: set[str] = set()
    seen_headings: set[str] = set()
    chunks: List[dict] = []

    for row in rows:
        if len(chunks) >= k:
            break
        text = row.get("content") or ""
        if not text.strip():
            continue
        digest = hashlib.sha1(_normalise_for_dedup(text).encode()).hexdigest()
        if digest in seen_hashes:
            continue
        md = row.get("metadata") or {}
        heading = md.get("section") or md.get("title") or chapter or topic
        # Prefer heading diversity — but allow a repeat if we're running low.
        if heading in seen_headings and len(chunks) < (k - 1):
            continue
        seen_hashes.add(digest)
        seen_headings.add(heading)
        chunks.append({
            "heading":    heading,
            "text":       text,
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
    # v0.20.4: the v0.20 first pass used `c.concept_id` which doesn't exist —
    # the column is just `id` on `concepts` (verifiable in app/api/student.py
    # line 79: `JOIN concepts c ON c.id = cm.concept_id`). Prod log on
    # 2026-04-21 caught the silent fallback to global-average mastery.
    try:
        row = await pool.fetchrow(
            """
            SELECT AVG(mastery_score)::float AS avg_score,
                   MAX(updated_at)           AS last_reviewed,
                   SUM(attempt_count)::int   AS attempts
            FROM concept_mastery cm
            JOIN concepts c ON c.id = cm.concept_id
            WHERE cm.student_id = $1
              AND (c.subtopic ILIKE '%' || $2 || '%'
                   OR c.topic ILIKE '%' || $2 || '%')
            """,
            uuid.UUID(student_id), topic,
        )
    except Exception as exc:
        # concepts schema variation — fall back to overall average + log a
        # warning (NOT info) so this isn't silently masking a real schema drift.
        logger.warning(
            "mastery lookup via concepts JOIN failed (%s), falling back to "
            "OVERALL average — value shown will not be topic-specific", exc,
        )
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
