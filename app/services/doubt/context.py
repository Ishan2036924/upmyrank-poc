"""
5-Part LLM payload helpers — RAG retrieval and targeted genome injection.

The five parts of every Socratic LLM call:
  Part 1 — System prompt    : TUTOR_SYSTEM_PROMPT (prompts.py, unchanged per call)
  Part 2 — RAG context      : get_rag_context()        → top-3 NCERT chunks + 1 similar problem
  Part 3 — Genome injection : get_student_mastery_str() → targeted per-topic mastery string
  Part 4 — Session memory   : engine.get_session_memory() (last 3 doubt summaries)
  Part 5 — Current history  : conversation_history from doubt_session row

Usage in engine.py:
    from app.services.doubt.context import get_rag_context, get_student_mastery_str
    rag              = await get_rag_context(retriever, question, subject, topic)
    genome_injection = await get_student_mastery_str(pool, student_id, topic)
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

import asyncpg

from app.services.rag.retriever import Retriever

logger = logging.getLogger(__name__)


# ── Part 2: RAG context ───────────────────────────────────────────────────────

async def get_rag_context(
    retriever: Retriever,
    question: str,
    subject: str,
    topic: str = "",
) -> dict:
    """
    Retrieve the RAG context for an LLM call.

    Fetches:
        • Top 3 NCERT knowledge chunks (hybrid RRF: vector + keyword)
        • 1 similar verified problem from the problems table (pgvector cosine)

    Returns a dict:
        {
            "chunks":         list[dict],   # top-3 knowledge chunks
            "similar_problem": dict | None,  # most similar verified problem
            "context_text":   str,          # ready-to-inject context block
            "chunk_count":    int,          # number of chunks retrieved
        }
    """
    # ── 3 NCERT chunks via hybrid RRF ────────────────────────────────────────
    chunks = await retriever.search(question, k=3, subject=subject)

    # ── 1 similar verified problem via embedding similarity ──────────────────
    similar_problem: Optional[dict] = None
    try:
        results = await retriever.search_problems(
            question, k=1, topic=topic or None,
        )
        similar_problem = results[0] if results else None
    except Exception as exc:
        logger.warning("Similar-problem lookup failed (non-fatal): %s", exc)

    # ── Assemble context text ─────────────────────────────────────────────────
    ncert_text = "\n\n---\n\n".join(c["content"] for c in chunks)

    if similar_problem:
        similar_block = (
            "\n\n── SIMILAR VERIFIED PROBLEM ─────────────────────────────────\n"
            f"Q: {similar_problem['question_text']}\n"
            f"Verified answer: {similar_problem.get('verified_answer') or 'N/A'}"
        )
    else:
        similar_block = ""

    return {
        "chunks":          chunks,
        "similar_problem": similar_problem,
        "context_text":    ncert_text + similar_block,
        "chunk_count":     len(chunks),
    }


# ── Part 3: Targeted genome injection ────────────────────────────────────────

async def get_student_mastery_str(
    pool: asyncpg.Pool,
    student_id: str,
    topic: str,
) -> str:
    """
    Return a targeted mastery injection string for one topic.

    Output format (injected verbatim into the system/user prompt):
        "Student's current mastery in [Topic] is [X]%. Frequent errors: [Y]."

    Falls back gracefully:
        - Unknown topic    → "0% (New Topic). Frequent errors: none recorded."
        - DB error         → "unknown."
        - Invalid UUID     → "unknown (invalid ID)."

    Args:
        pool:       asyncpg connection pool
        student_id: student UUID string
        topic:      topic name to query (ILIKE match on concepts.topic)
    """
    if not topic:
        return "Student's current mastery in this topic is unknown (new topic)."

    try:
        student_uuid = uuid.UUID(student_id)
    except ValueError:
        return f"Student's current mastery in {topic} is unknown (invalid ID)."

    try:
        rows = await pool.fetch(
            """
            SELECT cm.mastery_score, cm.error_pattern_array, c.subtopic
            FROM   concept_mastery cm
            JOIN   concepts c ON c.id = cm.concept_id
            WHERE  cm.student_id = $1
              AND  c.topic ILIKE $2
            ORDER  BY cm.mastery_score ASC
            """,
            student_uuid,
            f"%{topic}%",
        )
    except Exception as exc:
        logger.warning("get_student_mastery_str DB query failed: %s", exc)
        return f"Student's current mastery in {topic} is unknown."

    if not rows:
        return (
            f"Student's current mastery in {topic} is 0% (New Topic). "
            "Frequent errors: none recorded."
        )

    avg_mastery = sum(float(r["mastery_score"]) for r in rows) / len(rows)

    # Aggregate error frequency counts from the JSONB error_pattern_array
    all_errors: dict[str, int] = {}
    for r in rows:
        pattern = r["error_pattern_array"] or {}
        if isinstance(pattern, str):
            try:
                pattern = json.loads(pattern)
            except (json.JSONDecodeError, TypeError):
                pattern = {}
        if isinstance(pattern, dict):
            for tag, count in pattern.items():
                try:
                    all_errors[tag] = all_errors.get(tag, 0) + int(count)
                except (TypeError, ValueError):
                    pass

    top_errors = sorted(all_errors.items(), key=lambda x: -x[1])[:3]
    errors_str = (
        ", ".join(tag for tag, _ in top_errors) if top_errors else "none recorded"
    )

    return (
        f"Student's current mastery in {topic} is {int(avg_mastery * 100)}%. "
        f"Frequent errors: {errors_str}."
    )
