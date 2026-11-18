"""Stage-1 bi-encoder retriever for TaxBot.

Embeds the user's question with the same model used at ingestion time, runs
an approximate nearest-neighbour search against ChromaDB, and filters results
by cosine-similarity threshold before passing them to the cross-encoder
reranker.
"""

from __future__ import annotations

import logging

from config import settings
from retrieval.embedder import EmbedderProtocol
from retrieval.store import RawResult, VectorStore

logger = logging.getLogger(__name__)


def retrieve(
    question: str,
    embedder: EmbedderProtocol,
    store: VectorStore,
    assessment_year: str | None = None,
) -> list[RawResult]:
    """Embed *question* and return top-k candidate chunks above the similarity threshold.

    Retrieves ``settings.retrieval_top_k * 3`` candidates from ChromaDB so the
    cross-encoder reranker (Stage 2) has enough material to work with, then
    discards any chunk whose cosine similarity is below
    ``settings.similarity_threshold``.

    Args:
        question: The user's natural-language question.
        embedder: Embedder used to encode the question (must match ingestion).
        store: ChromaDB vector store wrapper.
        assessment_year: Optional AY filter (e.g. ``"2024-25"``). When provided,
            only chunks from that assessment year are searched.

    Returns:
        A list of ``RawResult`` objects, possibly empty.  Results are ordered by
        cosine similarity descending (ChromaDB order).
    """
    if not question.strip():
        return []

    # Embed the question
    vectors = embedder.embed([question])
    if not vectors:
        logger.warning("Embedder returned no vector for question.")
        return []
    query_vector = vectors[0]

    # Build optional metadata filter
    where_filter = None
    if assessment_year:
        where_filter = {"assessment_year": {"$eq": assessment_year}}

    n_candidates = settings.retrieval_top_k * 3
    raw_results = store.query(
        vector=query_vector,
        n_results=n_candidates,
        where_filter=where_filter,
    )

    # Filter by similarity threshold (similarity = 1 - distance, already on RawResult)
    threshold = settings.similarity_threshold
    surviving = [r for r in raw_results if r.similarity >= threshold]

    logger.debug(
        "retrieve: %d candidates → %d above threshold %.2f",
        len(raw_results),
        len(surviving),
        threshold,
    )
    return surviving
