"""Text embedders for TaxBot.

Two implementations share the ``EmbedderProtocol`` interface:
- ``LocalEmbedder``  — sentence-transformers model running on the local machine.
- ``APIEmbedder``    — OpenAI-compatible embeddings API (any provider).

``get_embedder()`` returns the right one based on current settings and should
be called once at application startup; store the result as a singleton.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

import numpy as np
from sentence_transformers import SentenceTransformer

from config import settings
from exceptions import EmbedderError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EmbedderProtocol(Protocol):
    """Interface that every embedder implementation must satisfy."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one L2-normalised float vector per input text."""
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _l2_normalise(vectors: np.ndarray) -> list[list[float]]:
    """L2-normalise a 2-D NumPy array row-wise and return as nested lists."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    # Avoid division by zero for zero vectors
    norms = np.where(norms == 0, 1.0, norms)
    normalised = vectors / norms
    return normalised.tolist()


# ---------------------------------------------------------------------------
# Local embedder  (TASK-014)
# ---------------------------------------------------------------------------


class LocalEmbedder:
    """Sentence-transformer embedder running entirely on the local machine."""

    def __init__(self) -> None:
        logger.info("Loading local embedding model: %s", settings.embed_model)
        try:
            self._model = SentenceTransformer(settings.embed_model)
        except Exception as exc:
            raise EmbedderError(
                f"Failed to load embedding model {settings.embed_model!r}: {exc}"
            ) from exc
        logger.info("Local embedding model ready.")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Encode texts in batches and return L2-normalised vectors."""
        if not texts:
            return []
        try:
            vectors = self._model.encode(
                texts,
                batch_size=settings.embed_batch_size,
                normalize_embeddings=True,  # sentence-transformers does L2 norm
                show_progress_bar=False,
            )
            return vectors.tolist()
        except Exception as exc:
            raise EmbedderError(f"Local embedding failed: {exc}") from exc


# ---------------------------------------------------------------------------
# API embedder  (TASK-015)
# ---------------------------------------------------------------------------


class APIEmbedder:
    """OpenAI-compatible embeddings API embedder."""

    def __init__(self) -> None:
        import openai  # imported lazily so the class is usable without openai installed

        logger.info(
            "Using API embedder: model=%s base_url=%s",
            settings.openai_embed_model,
            settings.openai_base_url,
        )
        self._client = openai.OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self._model = settings.openai_embed_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Call the embeddings API and return L2-normalised vectors."""
        if not texts:
            return []
        try:
            response = self._client.embeddings.create(
                input=texts,
                model=self._model,
            )
            raw = np.array(
                [item.embedding for item in response.data], dtype=np.float32
            )
            return _l2_normalise(raw)
        except Exception as exc:
            raise EmbedderError(f"API embedding failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Factory  (TASK-016)
# ---------------------------------------------------------------------------


def get_embedder() -> EmbedderProtocol:
    """Return the appropriate embedder based on current settings.

    Uses ``APIEmbedder`` when ``OPENAI_API_KEY`` is set; falls back to
    ``LocalEmbedder`` otherwise.
    """
    if settings.openai_api_key:
        logger.info("OPENAI_API_KEY detected — using APIEmbedder.")
        return APIEmbedder()
    logger.info("No OPENAI_API_KEY — using LocalEmbedder.")
    return LocalEmbedder()
