"""
Singleton embedding model using sentence-transformers all-MiniLM-L6-v2.
Outputs 384-dimensional vectors, matching the vector(384) columns in Postgres.
"""
from __future__ import annotations

import logging
from typing import List

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None
_MODEL_NAME = "all-MiniLM-L6-v2"


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model %s ...", _MODEL_NAME)
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info("Embedding model loaded (dim=%d)", _model.get_sentence_embedding_dimension())
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts. Returns list of 384-dim float vectors."""
    model = _get_model()
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return embeddings.tolist()


def embed_single(text: str) -> List[float]:
    """Embed a single text string. Returns a 384-dim float vector."""
    return embed_texts([text])[0]


class EmbeddingService:
    """
    Thin dependency-injectable wrapper around the module-level singleton model.
    Passing this object to the Retriever allows easy mocking in tests while
    keeping the singleton semantics (model loads once, ever).
    """

    def embed_single(self, text: str) -> List[float]:
        """Embed one text. Triggers lazy model load on first call."""
        return embed_single(text)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts."""
        return embed_texts(texts)

    def warm_up(self) -> None:
        """Pre-load the model so the first real request isn't slow."""
        embed_single("warm up")
        logger.info("Embedding service warm-up complete.")
