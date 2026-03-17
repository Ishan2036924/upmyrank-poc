"""
Embedding service using OpenAI text-embedding-3-small.
Outputs 1536-dimensional vectors, matching the vector(1536) columns in Postgres.
Replaces the previous sentence-transformers/all-MiniLM-L6-v2 (384-dim) implementation.
"""
from __future__ import annotations

import logging
from typing import List

import openai

from app.config import settings

logger = logging.getLogger(__name__)

_client: openai.OpenAI | None = None
_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        _client = openai.OpenAI(api_key=settings.openai_api_key)
        logger.info("OpenAI embedding client initialised (model=%s)", _MODEL)
    return _client


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts. Returns list of 1536-dim float vectors."""
    client = _get_client()
    # Replace newlines — OpenAI recommends this for embedding quality
    cleaned = [t.replace("\n", " ") for t in texts]
    response = client.embeddings.create(input=cleaned, model=_MODEL)
    return [item.embedding for item in response.data]


def embed_single(text: str) -> List[float]:
    """Embed a single text string. Returns a 1536-dim float vector."""
    return embed_texts([text])[0]


class EmbeddingService:
    """
    Thin dependency-injectable wrapper around the module-level OpenAI client.
    Interface is identical to the previous SentenceTransformer version so
    no changes are needed in Retriever or main.py.
    """

    def embed_single(self, text: str) -> List[float]:
        return embed_single(text)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return embed_texts(texts)

    def warm_up(self) -> None:
        """No-op: OpenAI client needs no warm-up (no local model to load)."""
        logger.info("EmbeddingService ready (OpenAI %s, dim=%d)", _MODEL, EMBEDDING_DIM)
