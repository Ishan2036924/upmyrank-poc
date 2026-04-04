"""
Semantic response cache backed by Redis.

Caches Socratic opening responses (hint_level=0 only) by query embedding.
On a cache hit, the LLM call is skipped entirely.

Entry points:
    get_cached_response(query_embedding, threshold=0.92) → dict | None
    cache_response(query_embedding, response, ttl_seconds=86400)

Redis failures are ALWAYS silent — a cache miss is returned so the normal
pipeline runs. Never raises. Never crashes a student-facing request.

Key format: semantic_cache:{uuid4()}
TTL:        86 400 seconds (24 hours)
"""
from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "semantic_cache:"


# ── Pure math helper ──────────────────────────────────────────────────────────

def cosine_similarity(a: list, b: list) -> float:
    """
    Pure-Python cosine similarity between two equal-length float vectors.

    Returns a value in [-1.0, 1.0].  Returns 0.0 if either vector is all-zeros
    or the lengths differ.
    """
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


# ── Cache read ────────────────────────────────────────────────────────────────

async def get_cached_response(
    query_embedding: list,
    threshold: float = 0.92,
) -> Optional[dict]:
    """
    Scan all semantic_cache:* keys and return the best matching cached response.

    Returns the stored response dict if any key's cosine similarity with
    query_embedding meets or exceeds threshold.  Returns None on miss or error.

    Redis failures are always silent — returns None so the normal pipeline runs.
    """
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            best_score: float = -1.0
            best_response: Optional[dict] = None

            async for key in r.scan_iter(f"{_CACHE_PREFIX}*"):
                try:
                    raw = await r.get(key)
                    if raw is None:
                        continue
                    entry = json.loads(raw)
                    cached_emb = entry.get("embedding")
                    if not cached_emb:
                        continue
                    score = cosine_similarity(query_embedding, cached_emb)
                    if score >= threshold and score > best_score:
                        best_score = score
                        best_response = entry.get("response")
                except Exception as inner_exc:
                    logger.debug("Cache entry parse failed (skipping): %s", inner_exc)
                    continue

            if best_response is not None:
                logger.info(
                    "Semantic cache HIT (similarity=%.4f, threshold=%.2f)",
                    best_score, threshold,
                )
                return best_response

            logger.debug(
                "Semantic cache MISS (best_similarity=%.4f, threshold=%.2f)",
                best_score if best_score >= 0 else 0.0,
                threshold,
            )
            return None
        finally:
            await r.aclose()

    except Exception as exc:
        logger.warning("get_cached_response: Redis error (non-fatal): %s", exc)
        return None


# ── Cache write ───────────────────────────────────────────────────────────────

async def cache_response(
    query_embedding: list,
    response: dict,
    ttl_seconds: int = 86400,
) -> None:
    """
    Store a response dict keyed by a fresh UUID with a 24-hour TTL.

    Stores: {"embedding": [...], "response": {...}, "cached_at": ISO-8601}
    Redis failures are always silent.
    """
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            key = f"{_CACHE_PREFIX}{uuid.uuid4()}"
            payload = json.dumps({
                "embedding":  query_embedding,
                "response":   response,
                "cached_at":  datetime.now(timezone.utc).isoformat(),
            })
            await r.set(key, payload, ex=ttl_seconds)
            logger.debug("Semantic cache WRITE: key=%s ttl=%ds", key, ttl_seconds)
        finally:
            await r.aclose()

    except Exception as exc:
        logger.warning("cache_response: Redis error (non-fatal): %s", exc)
