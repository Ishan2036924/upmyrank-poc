"""
Hybrid retrieval service: pgvector similarity search + keyword ILIKE,
fused with Reciprocal Rank Fusion (RRF).

RRF formula:  score(d) = Σ  1 / (rank_i(d) + K)
              where K=60 (standard constant), i ranges over each result list.

Usage:
    retriever = Retriever(db_pool=pool, embedding_service=EmbeddingService())
    results   = await retriever.search("what is an equivalence relation", k=5)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import List, Optional

import asyncpg

from app.services.rag.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

# ── stop-word list for keyword extraction ─────────────────────────────────────
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "in", "on", "at", "to",
    "for", "of", "by", "as", "is", "it", "its", "be", "do", "so", "was",
    "has", "have", "had", "are", "not", "no", "nor", "yet", "from", "into",
    "with", "this", "that", "these", "those", "then", "than", "such", "can",
    "will", "may", "just", "also", "when", "what", "how", "why", "which",
    "who", "more", "each", "any", "all", "get", "set", "use", "used",
    "using", "find", "give", "show", "explain", "describe", "define",
    "example", "examples", "let", "me", "tell", "about", "them", "there",
    "would", "could", "should", "does", "did", "say", "said", "some",
    "like", "same", "very", "only", "even", "other", "one", "two", "three",
})


def _extract_keywords(query: str) -> List[str]:
    """Extract non-trivial keywords from *query*, excluding stop words."""
    words = re.findall(r"\b[a-zA-Z]\w*\b", query.lower())
    seen: set[str] = set()
    result: list[str] = []
    for w in words:
        if w not in _STOP_WORDS and len(w) >= 3 and w not in seen:
            seen.add(w)
            result.append(w)
    return result[:6]  # cap at 6 to keep the ILIKE query lean


def _vec_str(embedding: List[float]) -> str:
    """Serialise a float list to pgvector literal format: '[0.1,0.2,…]'."""
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


def _coerce_json(val) -> dict:
    """
    asyncpg may return JSONB as a raw string in some configurations.
    Safely coerce to dict in either case.
    """
    if val is None:
        return {}
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    return dict(val)  # already a dict


# ─────────────────────────────────────────────────────────────────────────────

class Retriever:
    """
    Hybrid retriever for the UpMyRank knowledge base.

    Vector search is run via the `match_chunks` Postgres function (cosine
    similarity on pgvector embeddings).  Keyword search is run via ILIKE on
    the `content` column.  Results from both lists are fused with RRF.
    """

    RRF_K = 60  # standard RRF constant

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        embedding_service: EmbeddingService,
    ) -> None:
        self._pool = db_pool
        self._embed = embedding_service

    # ── public API ────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        k: int = 5,
        subject: Optional[str] = None,
    ) -> List[dict]:
        """
        Hybrid search over knowledge_chunks.

        1. Embeds *query* with the singleton sentence-transformer.
        2. Runs vector similarity search via `match_chunks()` (fetches 3×k rows).
        3. Runs keyword ILIKE search on `content` (fetches 3×k rows).
        4. Fuses both ranked lists with Reciprocal Rank Fusion.
        5. Deduplicates by chunk id and returns the top-k results.

        Each returned dict has:
            id, content, subject, chapter, metadata,
            similarity_score, rrf_score
        """
        loop = asyncio.get_running_loop()
        q_emb: List[float] = await loop.run_in_executor(
            None, self._embed.embed_single, query
        )
        emb_str = _vec_str(q_emb)
        keywords = _extract_keywords(query)
        fetch_n = max(k * 3, 15)

        # Fire both searches concurrently
        vec_rows, kw_rows = await asyncio.gather(
            self._vector_search(emb_str, subject, fetch_n),
            self._keyword_search(keywords, subject, fetch_n),
        )

        # ── Reciprocal Rank Fusion ────────────────────────────────────────────
        scores: dict[str, dict] = {}

        for rank, row in enumerate(vec_rows, start=1):
            cid = str(row["id"])
            if cid not in scores:
                scores[cid] = {
                    "row": row,
                    "similarity_score": float(row["similarity"]),
                    "rrf_score": 0.0,
                }
            scores[cid]["rrf_score"] += 1.0 / (rank + self.RRF_K)

        for rank, row in enumerate(kw_rows, start=1):
            cid = str(row["id"])
            if cid not in scores:
                scores[cid] = {
                    "row": row,
                    "similarity_score": 0.0,
                    "rrf_score": 0.0,
                }
            scores[cid]["rrf_score"] += 1.0 / (rank + self.RRF_K)

        top_k = sorted(
            scores.values(), key=lambda x: x["rrf_score"], reverse=True
        )[:k]

        return [
            self._format_chunk(r["row"], r["similarity_score"], r["rrf_score"])
            for r in top_k
        ]

    async def search_problems(
        self,
        query: str,
        k: int = 5,
        topic: Optional[str] = None,
        difficulty_range: Optional[tuple] = None,
    ) -> List[dict]:
        """
        Embedding-similarity search over the problems table.

        Optional filters:
            topic            – ILIKE match on the `topic` column
            difficulty_range – (low, high) floats in [0, 1]; filters on `difficulty`

        Each returned dict has:
            id, question_text, verified_answer, topic, subtopic,
            difficulty, source, concepts_tested, similarity_score
        """
        loop = asyncio.get_running_loop()
        q_emb: List[float] = await loop.run_in_executor(
            None, self._embed.embed_single, query
        )
        emb_str = _vec_str(q_emb)

        # Build query dynamically with positional params
        params: list = [emb_str, k * 2]   # $1 = embedding, $2 = LIMIT
        conditions: list[str] = []

        if topic:
            params.append(f"%{topic}%")
            conditions.append(f"p.topic ILIKE ${len(params)}")

        if difficulty_range:
            low, high = difficulty_range
            params.append(float(low))
            params.append(float(high))
            conditions.append(
                f"p.difficulty BETWEEN ${len(params) - 1} AND ${len(params)}"
            )

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        sql = f"""
            SELECT
                p.id,
                p.question_text,
                p.verified_answer,
                p.topic,
                p.subtopic,
                p.difficulty,
                p.source,
                p.concepts_tested,
                1 - (p.embedding <=> $1::vector) AS similarity
            FROM problems p
            {where_clause}
            ORDER BY p.embedding <=> $1::vector
            LIMIT $2
        """

        rows = await self._pool.fetch(sql, *params)

        return [
            {
                "id": str(row["id"]),
                "question_text": row["question_text"],
                "verified_answer": row["verified_answer"],
                "topic": row["topic"],
                "subtopic": row["subtopic"],
                "difficulty": row["difficulty"],
                "source": row["source"],
                "concepts_tested": list(row["concepts_tested"] or []),
                "similarity_score": float(row["similarity"]),
            }
            for row in rows[:k]
        ]

    async def get_related_concepts(self, query: str) -> List[str]:
        """
        Return up to 4 concept IDs most relevant to *query*.

        Algorithm:
        1. Run search() to get top-3 knowledge chunks.
        2. Parse the "Topic: <name>" header from each chunk's content.
        3. Look up matching concept IDs in the `concepts` table via
           ILIKE on `subtopic` and `description`.
        """
        chunks = await self.search(query, k=3)

        # Parse topic names from chunk content (first line = "Topic: <name>")
        topic_texts: set[str] = set()
        for chunk in chunks:
            content: str = chunk.get("content", "")
            first_line = content.split("\n")[0]
            if ":" in first_line:
                topic_texts.add(first_line.split(":", 1)[1].strip())

        if not topic_texts:
            return []

        # Look up concepts whose subtopic / description contains the topic text
        concept_ids: list[str] = []
        seen: set[str] = set()

        for topic_text in topic_texts:
            rows = await self._pool.fetch(
                """
                SELECT id FROM concepts
                WHERE LOWER(subtopic)    ILIKE $1
                   OR LOWER(description) ILIKE $1
                LIMIT 2
                """,
                f"%{topic_text.lower()}%",
            )
            for row in rows:
                cid = row["id"]
                if cid not in seen:
                    seen.add(cid)
                    concept_ids.append(cid)

        return concept_ids[:4]

    # ── private helpers ───────────────────────────────────────────────────────

    async def _vector_search(
        self,
        emb_str: str,
        subject: Optional[str],
        limit: int,
    ) -> list:
        """Call the match_chunks Postgres function."""
        return await self._pool.fetch(
            "SELECT id, content, subject, chapter, metadata, similarity "
            "FROM match_chunks($1::vector, $2, $3)",
            emb_str,
            limit,
            subject,
        )

    async def _keyword_search(
        self,
        keywords: List[str],
        subject: Optional[str],
        limit: int,
    ) -> list:
        """
        Fetch rows whose `content` contains at least one keyword (ILIKE).
        Results are ordered by the number of keyword hits (descending) so that
        chunks matching more keywords rank higher in the RRF fusion.
        """
        if not keywords:
            return []

        params: list = [limit]   # $1
        like_clauses: list[str] = []
        score_parts: list[str] = []

        for kw in keywords:
            params.append(f"%{kw}%")
            idx = len(params)
            like_clauses.append(f"kc.content ILIKE ${idx}")
            # Count each matching keyword as +1 for ordering purposes
            score_parts.append(f"(CASE WHEN kc.content ILIKE ${idx} THEN 1 ELSE 0 END)")

        where = "(" + " OR ".join(like_clauses) + ")"
        score_expr = " + ".join(score_parts)

        if subject:
            params.append(subject)
            where += f" AND kc.subject = ${len(params)}"

        sql = f"""
            SELECT kc.id, kc.content, kc.subject, kc.chapter, kc.metadata
            FROM knowledge_chunks kc
            WHERE {where}
            ORDER BY ({score_expr}) DESC, kc.chunk_index
            LIMIT $1
        """

        return await self._pool.fetch(sql, *params)

    @staticmethod
    def _format_chunk(row, similarity_score: float, rrf_score: float) -> dict:
        return {
            "id": str(row["id"]),
            "content": row["content"],
            "subject": row["subject"],
            "chapter": row["chapter"],
            "metadata": _coerce_json(row["metadata"]),
            "similarity_score": round(similarity_score, 6),
            "rrf_score": round(rrf_score, 6),
        }
