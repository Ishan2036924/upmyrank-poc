"""
Retrieval tools for the Agentic RAG loop.

Four tools the LLM agent can call during its retrieval reasoning loop:

  1. search_ncert        — NCERT knowledge_chunks (all subjects)
  2. search_jee_problems — 30-year JEE PYQ database (jee_problems table)
  3. search_concepts     — concepts table (definitions, prerequisites)
  4. rerank_and_select   — consolidate + deduplicate an accumulated chunk pool

Each tool returns a list[dict] with a consistent 'source' field so the
agent can distinguish where each chunk came from.

These are plain async functions — the agent loop in agent.py calls them
by name based on what the LLM requests via function calling.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

import asyncpg

from app.services.rag.embeddings import EmbeddingService
from app.services.rag.retriever import Retriever, _extract_keywords, _vec_str

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1 — search_ncert
# ─────────────────────────────────────────────────────────────────────────────

async def search_ncert(
    retriever: Retriever,
    query: str,
    subject: Optional[str] = None,
    chapter: Optional[str] = None,
    top_k: int = 3,
    precomputed_embedding: Optional[List[float]] = None,
) -> List[dict]:
    """
    Hybrid RRF search over knowledge_chunks (NCERT textbook content).

    Args:
        retriever:             the shared Retriever instance (holds pool + embed service)
        query:                 free-text search query
        subject:               filter by 'Physics', 'Chemistry', or 'Maths' (optional)
        chapter:               further filter by chapter ILIKE match (optional)
        top_k:                 number of results to return (default 3)
        precomputed_embedding: optional pre-computed query embedding — avoids a
                               redundant OpenAI embed call when agent already has it

    Returns list of dicts with keys:
        id, content, subject, chapter, metadata,
        similarity_score, rrf_score, source ('ncert')
    """
    top_k = max(1, min(top_k, 10))  # clamp 1–10

    if chapter:
        # Chapter filtering: run standard hybrid search, then post-filter by chapter
        results = await retriever.search(
            query, k=top_k * 3, subject=subject,
            precomputed_embedding=precomputed_embedding,
        )
        filtered = [
            r for r in results
            if chapter.lower() in (r.get("chapter") or "").lower()
        ]
        results = (filtered or results)[:top_k]
    else:
        results = await retriever.search(
            query, k=top_k, subject=subject,
            precomputed_embedding=precomputed_embedding,
        )

    # Tag source so the agent knows where this chunk came from
    for r in results:
        r["source"] = "ncert"

    logger.debug("search_ncert query=%r subject=%r → %d results", query, subject, len(results))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2 — search_jee_problems
# ─────────────────────────────────────────────────────────────────────────────

async def search_jee_problems(
    pool: asyncpg.Pool,
    embed_service: EmbeddingService,
    query: str,
    subject: Optional[str] = None,
    exam_type: Optional[str] = None,
    difficulty_min: Optional[int] = None,
    difficulty_max: Optional[int] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    top_k: int = 3,
    precomputed_embedding: Optional[List[float]] = None,
) -> List[dict]:
    """
    Embedding-similarity search over jee_problems (30-year JEE PYQ database).

    Calls match_jee_problems() Postgres function added in migrate_v11.
    Falls back gracefully if the table doesn't exist yet (empty list).

    Args:
        precomputed_embedding: optional pre-computed query embedding — avoids a
                               redundant OpenAI embed call when agent already has it.

    Returns list of dicts with keys:
        problem_id, subject, topic, year, exam_type, difficulty,
        problem_text, solution_text, solution_steps, source_verified,
        similarity, source ('jee_pyq')
    """
    top_k = max(1, min(top_k, 10))

    import asyncio
    if precomputed_embedding is not None:
        q_emb: List[float] = precomputed_embedding
    else:
        loop = asyncio.get_running_loop()
        try:
            q_emb = await loop.run_in_executor(
                None, embed_service.embed_single, query
            )
        except Exception as exc:
            logger.warning("search_jee_problems: embedding failed: %s", exc)
            return []

    emb_str = _vec_str(q_emb)

    try:
        rows = await pool.fetch(
            """
            SELECT
                problem_id, subject, topic, year, exam_type, difficulty,
                problem_text, solution_text, solution_steps, source_verified,
                1 - (embedding <=> $1::vector) AS similarity
            FROM jee_problems
            WHERE
                ($2::text  IS NULL OR subject   = $2)
                AND ($3::text  IS NULL OR exam_type = $3)
                AND ($4::int   IS NULL OR difficulty >= $4)
                AND ($5::int   IS NULL OR difficulty <= $5)
                AND ($6::int   IS NULL OR year       >= $6)
                AND ($7::int   IS NULL OR year       <= $7)
                AND embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $8
            """,
            emb_str,
            subject,
            exam_type,
            difficulty_min,
            difficulty_max,
            year_min,
            year_max,
            top_k,
        )
    except Exception as exc:
        # Table may not exist yet (migration not run)
        logger.warning("search_jee_problems DB query failed (non-fatal): %s", exc)
        return []

    results = []
    for row in rows:
        sol_steps = row["solution_steps"]
        if isinstance(sol_steps, str):
            try:
                sol_steps = json.loads(sol_steps)
            except Exception:
                sol_steps = []

        results.append({
            "problem_id":    str(row["problem_id"]),
            "subject":       row["subject"],
            "topic":         row["topic"],
            "year":          row["year"],
            "exam_type":     row["exam_type"],
            "difficulty":    row["difficulty"],
            "problem_text":  row["problem_text"],
            "solution_text": row["solution_text"],
            "solution_steps": sol_steps,
            "source_verified": row["source_verified"],
            "similarity":    float(row["similarity"]),
            "source":        "jee_pyq",
            # Provide a 'content' key for uniform handling in the agent loop
            "content": (
                f"[JEE {row['exam_type']} {row['year'] or ''}] "
                f"Topic: {row['topic']}\n\n"
                f"{row['problem_text']}"
                + (
                    f"\n\nVerified Answer: {row['solution_text'][:300]}"
                    if row.get("solution_text") and row.get("source_verified")
                    else ""
                )
            ),
        })

    logger.debug(
        "search_jee_problems query=%r subject=%r → %d results",
        query, subject, len(results),
    )
    return results


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3 — search_concepts
# ─────────────────────────────────────────────────────────────────────────────

async def search_concepts(
    pool: asyncpg.Pool,
    query: str,
    top_k: int = 4,
) -> List[dict]:
    """
    Keyword-based concept lookup from the concepts table.

    Returns concept definitions, prerequisites, and subtopic info.
    Useful when the agent needs to verify concept relationships or
    surface prerequisite knowledge for the student.

    Uses 3-layer keyword matching (same strategy as Retriever.get_related_concepts):
      Layer 1: Full phrase ILIKE on subtopic + description
      Layer 2: Individual keywords ILIKE on subtopic + description
      Layer 3: Keyword ILIKE on concept ID

    Returns list of dicts:
        id, subject, topic, subtopic, description, prerequisite_ids, source ('concept')
    """
    top_k = max(1, min(top_k, 10))

    # Extract meaningful keywords
    keywords = _extract_keywords(query)
    if not keywords:
        return []

    query_lower = query.lower()[:200]

    try:
        # Layer 1: phrase match on subtopic / description
        rows = await pool.fetch(
            """
            SELECT id, subject, topic, subtopic, description, prerequisite_ids
            FROM concepts
            WHERE LOWER(subtopic)    ILIKE $1
               OR LOWER(description) ILIKE $1
               OR $2 LIKE '%' || LOWER(subtopic) || '%'
            LIMIT $3
            """,
            f"%{query_lower}%",
            query_lower,
            top_k * 2,
        )

        # Layer 2: individual keyword ILIKE if layer 1 insufficient
        if len(rows) < top_k and keywords:
            conditions = " OR ".join(
                f"LOWER(subtopic) ILIKE ${i + 1} OR LOWER(description) ILIKE ${i + 1}"
                for i in range(len(keywords))
            )
            extra = await pool.fetch(
                f"""
                SELECT id, subject, topic, subtopic, description, prerequisite_ids
                FROM concepts
                WHERE {conditions}
                LIMIT ${ len(keywords) + 1}
                """,
                *[f"%{kw}%" for kw in keywords],
                top_k * 2,
            )
            # Merge, dedup by id
            seen = {r["id"] for r in rows}
            rows = list(rows) + [r for r in extra if r["id"] not in seen]

    except Exception as exc:
        logger.warning("search_concepts DB query failed (non-fatal): %s", exc)
        return []

    results = []
    seen_ids: set[str] = set()
    for row in rows[:top_k]:
        cid = row["id"]
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        prereqs = list(row["prerequisite_ids"] or [])
        description = row["description"] or ""
        results.append({
            "id":              cid,
            "subject":         row["subject"],
            "topic":           row["topic"],
            "subtopic":        row["subtopic"],
            "description":     description,
            "prerequisite_ids": prereqs,
            "source":          "concept",
            # Uniform content key for agent assembly
            "content": (
                f"Concept: {row['subtopic']}\n"
                f"Topic: {row['topic']}\n\n"
                f"{description}"
                + (f"\n\nPrerequisites: {', '.join(prereqs)}" if prereqs else "")
            ),
        })

    logger.debug("search_concepts query=%r → %d results", query, len(results))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4 — rerank_and_select
# ─────────────────────────────────────────────────────────────────────────────

def rerank_and_select(
    accumulated_chunks: List[dict],
    query: str,
    embed_service: EmbeddingService,
    max_chunks: int = 5,
    precomputed_embedding: Optional[List[float]] = None,
) -> List[dict]:
    """
    Consolidate chunks from multiple tool calls, deduplicate, and select
    the top-max_chunks most relevant to the original query.

    Scoring strategy:
      1. Compute cosine similarity between query embedding and each chunk's
         embedding (if the embedding is present).
      2. Fall back to keyword overlap score for chunks without embeddings
         (concepts, jee_pyq results may not carry raw embeddings).
      3. Deduplicate by content prefix (first 120 chars).
      4. Return top-max_chunks by score, preserving source diversity.

    Args:
        precomputed_embedding: optional pre-computed query embedding — avoids a
                               redundant synchronous OpenAI call inside the executor.

    This is a synchronous function — called within the async agent loop via
    asyncio.get_running_loop().run_in_executor() or directly (it's fast).
    """
    if not accumulated_chunks:
        return []

    max_chunks = max(1, min(max_chunks, 10))

    # ── Embed query (skip if already computed) ────────────────────────────────
    if precomputed_embedding is not None:
        q_emb = precomputed_embedding
    else:
        try:
            q_emb = embed_service.embed_single(query)
        except Exception as exc:
            logger.warning("rerank_and_select: embedding failed, using keyword fallback: %s", exc)
            q_emb = None

    # ── Deduplicate by content prefix ─────────────────────────────────────────
    seen_prefixes: set[str] = set()
    unique_chunks: List[dict] = []
    for chunk in accumulated_chunks:
        content = chunk.get("content", "")
        prefix = re.sub(r"\s+", " ", content[:120]).strip().lower()
        if prefix not in seen_prefixes:
            seen_prefixes.add(prefix)
            unique_chunks.append(chunk)

    # ── Score each chunk ──────────────────────────────────────────────────────
    def _cosine(a: List[float], b: List[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot / (norm_a * norm_b + 1e-9)

    query_keywords = set(_extract_keywords(query))

    def _keyword_score(chunk: dict) -> float:
        content_lower = (chunk.get("content", "")).lower()
        if not query_keywords:
            return 0.0
        hits = sum(1 for kw in query_keywords if kw in content_lower)
        return hits / len(query_keywords)

    scored: List[tuple[float, dict]] = []
    for chunk in unique_chunks:
        # Prefer existing similarity scores already returned by vector search
        existing_sim = chunk.get("similarity_score") or chunk.get("similarity") or 0.0

        if q_emb and chunk.get("embedding"):
            # Re-rank with fresh cosine against actual query embedding
            cos_sim = _cosine(q_emb, chunk["embedding"])
            score = 0.7 * cos_sim + 0.3 * existing_sim
        elif existing_sim > 0:
            # Trust the pre-computed similarity from vector search
            score = 0.6 * existing_sim + 0.4 * _keyword_score(chunk)
        else:
            # Keyword-only for chunks without any embedding score (e.g. concept rows)
            score = _keyword_score(chunk)

        scored.append((score, chunk))

    # ── Sort descending ───────────────────────────────────────────────────────
    scored.sort(key=lambda x: x[0], reverse=True)

    # ── Enforce source diversity: at most ceil(max_chunks/2) from any one source ─
    source_counts: dict[str, int] = {}
    max_per_source = max(2, (max_chunks + 1) // 2)
    selected: List[dict] = []

    for _score, chunk in scored:
        src = chunk.get("source", "unknown")
        if source_counts.get(src, 0) < max_per_source:
            source_counts[src] = source_counts.get(src, 0) + 1
            selected.append(chunk)
        if len(selected) >= max_chunks:
            break

    # If diversity filter left us short, fill remaining slots without constraint
    if len(selected) < max_chunks:
        already_selected = set(id(c) for c in selected)
        for _score, chunk in scored:
            if id(chunk) not in already_selected:
                selected.append(chunk)
            if len(selected) >= max_chunks:
                break

    logger.debug(
        "rerank_and_select: %d → %d chunks (sources: %s)",
        len(unique_chunks), len(selected), source_counts,
    )
    return selected


# ─────────────────────────────────────────────────────────────────────────────
# Tool schema definitions (OpenAI function calling format)
# Used by agent.py to send to the LLM.
# ─────────────────────────────────────────────────────────────────────────────

TOOL_SCHEMAS: List[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_ncert",
            "description": (
                "Search NCERT textbook content (Physics, Chemistry, Maths Classes 11+12) "
                "for theory, derivations, concepts, and worked examples. "
                "Use this first for any conceptual or derivation-based question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Specific search query — be precise about the concept or formula needed",
                    },
                    "subject": {
                        "type": "string",
                        "enum": ["Physics", "Chemistry", "Maths"],
                        "description": "Subject to search in",
                    },
                    "chapter": {
                        "type": "string",
                        "description": "Optional: narrow to a specific chapter name (e.g. 'Rotational Motion')",
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 3,
                        "description": "Number of results to return (1–10, default 3)",
                    },
                },
                "required": ["query", "subject"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_jee_problems",
            "description": (
                "Search 30 years of JEE Past Year Questions. "
                "Use this for numerical problems, problem-solving patterns, "
                "and to find similar JEE problems for calibration. "
                "Especially useful to retrieve verified solution approaches."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Problem description or concept to search for",
                    },
                    "subject": {
                        "type": "string",
                        "enum": ["Physics", "Chemistry", "Maths"],
                    },
                    "exam_type": {
                        "type": "string",
                        "enum": ["JEE Mains", "JEE Advanced"],
                        "description": "Filter by exam type (optional)",
                    },
                    "difficulty_min": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "Minimum difficulty level (1=easiest)",
                    },
                    "difficulty_max": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "Maximum difficulty level (5=hardest)",
                    },
                    "year_min": {
                        "type": "integer",
                        "description": "Earliest year to include (e.g. 1995)",
                    },
                    "year_max": {
                        "type": "integer",
                        "description": "Latest year to include (e.g. 2024)",
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 3,
                        "description": "Number of results (1–10, default 3)",
                    },
                },
                "required": ["query", "subject"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_concepts",
            "description": (
                "Look up concept definitions, prerequisites, and related concept IDs "
                "from the concepts knowledge graph. "
                "Use this when you need to verify prerequisite chains or find the "
                "exact concept taxonomy for a topic."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Concept name or description to look up",
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 4,
                        "description": "Number of concept entries to return (1–10, default 4)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rerank_and_select",
            "description": (
                "Consolidate all retrieved chunks from previous tool calls, "
                "remove duplicates, and select the most relevant subset. "
                "Call this as your FINAL retrieval step before signalling you are "
                "ready to generate the Socratic response."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The original student question (used for relevance scoring)",
                    },
                    "max_chunks": {
                        "type": "integer",
                        "default": 5,
                        "description": "Maximum chunks to keep after reranking (default 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
]
