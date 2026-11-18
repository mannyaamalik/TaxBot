"""Stage-2 cross-encoder reranker for TaxBot.

Takes the candidate list produced by the bi-encoder retriever and rescores
each (question, chunk) pair with a cross-encoder model for higher precision.
The reranker is optional and can be disabled via RERANKER_ENABLED=false to
reduce memory usage on small machines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

from config import settings
from retrieval.store import RawResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RetrievedChunk:
    """A chunk that has survived both retrieval stages, ready for the LLM prompt."""

    text: str
    score: float            # cross-encoder score (or cosine similarity if reranker off)
    doc_title: str
    section_heading: str
    page_number: int
    filename: str
    assessment_year: str
    chunk_index: int
    doc_id: str             # kept for downstream audit / deduplication


# ---------------------------------------------------------------------------
# Lazy model loader  (loaded once, reused across requests)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_cross_encoder():  # type: ignore[return]
    """Load the cross-encoder model exactly once and cache it."""
    from sentence_transformers import CrossEncoder  # lazy import

    model_name = settings.reranker_model
    logger.info("Loading cross-encoder model: %s", model_name)
    model = CrossEncoder(model_name, max_length=512)
    logger.info("Cross-encoder ready.")
    return model


# ---------------------------------------------------------------------------
# Reranker  (TASK-020)
# ---------------------------------------------------------------------------


def rerank(
    question: str,
    results: list[RawResult],
) -> list[RetrievedChunk]:
    """Rerank *results* using a cross-encoder and return the top-k chunks.

    When ``settings.reranker_enabled`` is ``False``, the candidates are
    converted to ``RetrievedChunk`` objects using their Stage-1 cosine scores
    without any additional scoring.

    Args:
        question: The user's question (same string passed to ``retrieve``).
        results: Candidate chunks from Stage-1 bi-encoder retrieval.

    Returns:
        Up to ``settings.retrieval_top_k`` ``RetrievedChunk`` objects, sorted
        by relevance score descending.
    """
    if not results:
        return []

    top_k = settings.retrieval_top_k

    if not settings.reranker_enabled:
        # Passthrough: use cosine similarity as the score, truncate to top_k
        logger.debug("Reranker disabled — using cosine scores directly.")
        converted = [_to_retrieved_chunk(r, r.similarity) for r in results]
        return sorted(converted, key=lambda c: c.score, reverse=True)[:top_k]

    # Score every (question, chunk_text) pair with the cross-encoder
    cross_encoder = _get_cross_encoder()
    pairs = [[question, r.text] for r in results]

    try:
        scores: list[float] = cross_encoder.predict(pairs).tolist()
    except Exception as exc:
        logger.warning(
            "Cross-encoder scoring failed (%s); falling back to cosine scores.", exc
        )
        converted = [_to_retrieved_chunk(r, r.similarity) for r in results]
        return sorted(converted, key=lambda c: c.score, reverse=True)[:top_k]

    # Pair results with scores, filter by rerank_threshold, sort, take top_k
    scored = [
        (result, score)
        for result, score in zip(results, scores)
        if score >= settings.rerank_threshold
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    scored = scored[:top_k]

    logger.debug(
        "rerank: %d candidates → %d after cross-encoder (threshold=%.2f)",
        len(results),
        len(scored),
        settings.rerank_threshold,
    )
    return [_to_retrieved_chunk(r, s) for r, s in scored]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _to_retrieved_chunk(raw: RawResult, score: float) -> RetrievedChunk:
    """Convert a ``RawResult`` to a ``RetrievedChunk`` with the given score."""
    return RetrievedChunk(
        text=raw.text,
        score=score,
        doc_title=raw.doc_title,
        section_heading=raw.section_heading,
        page_number=raw.page_number,
        filename=raw.filename,
        assessment_year=raw.assessment_year,
        chunk_index=raw.chunk_index,
        doc_id=raw.doc_id,
    )
