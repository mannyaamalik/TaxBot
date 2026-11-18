"""Ingestion pipeline orchestrator for TaxBot.

Coordinates the full ingestion flow:
  load_document → extract_metadata → chunk_document → embed → upsert

The ``ingest_file`` function is the single entry point for both the
``POST /ingest`` API route and the ``ingest_bulk.py`` CLI script.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from exceptions import IngestError, UnsupportedFileTypeError
from ingestion.chunker import Chunk, chunk_document
from ingestion.loader import SUPPORTED_EXTENSIONS, load_document
from ingestion.metadata import extract_metadata
from retrieval.embedder import EmbedderProtocol
from retrieval.store import VectorStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class IngestResult:
    """Summary produced after successfully ingesting one document."""

    doc_id: str
    filename: str
    chunks_added: int


# ---------------------------------------------------------------------------
# Pipeline  (TASK-012)
# ---------------------------------------------------------------------------


def ingest_file(
    path: str,
    embedder: EmbedderProtocol,
    store: VectorStore,
) -> IngestResult:
    """Ingest a single document into the vector store.

    Steps:
    1. Validate the file extension.
    2. Load the document into ``RawPage`` objects.
    3. Extract document-level metadata (with optional YAML sidecar).
    4. Delete any existing chunks for the same ``doc_id`` (idempotent upsert).
    5. Chunk the document using the sliding-window chunker.
    6. Embed chunks in batches using the provided embedder.
    7. Upsert chunks into ChromaDB.

    Args:
        path:     Path to the source document (PDF, HTML, .txt, .md).
        embedder: An ``EmbedderProtocol`` instance (local or API).
        store:    A ``VectorStore`` instance backed by ChromaDB.

    Returns:
        ``IngestResult`` with doc_id, filename, and chunk count.

    Raises:
        UnsupportedFileTypeError: if the file extension is not supported.
        IngestError: if any pipeline step fails.
    """
    abs_path = str(Path(path).resolve())
    ext = Path(abs_path).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"File extension {ext!r} is not supported. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    logger.info("Ingesting: %s", abs_path)

    try:
        # ── Step 1: Load ──────────────────────────────────────────────────
        raw_pages = load_document(abs_path)
        if not raw_pages:
            raise IngestError(f"Loader returned no pages for {abs_path!r}")

        # ── Step 2: Metadata ──────────────────────────────────────────────
        meta = extract_metadata(raw_pages, abs_path)

        # ── Step 3: Deduplication — delete old chunks for this doc ────────
        deleted = store.delete_by_doc_id(meta.doc_id)
        if deleted:
            logger.info(
                "Replaced %d existing chunk(s) for %s (doc_id=%s)",
                deleted,
                meta.filename,
                meta.doc_id[:12],
            )

        # ── Step 4: Chunk ─────────────────────────────────────────────────
        chunks: list[Chunk] = chunk_document(raw_pages, meta)
        if not chunks:
            raise IngestError(f"Chunker produced no chunks for {abs_path!r}")

        # ── Step 5: Embed in batches ──────────────────────────────────────
        _embed_chunks(chunks, embedder)

        # ── Step 6: Store ─────────────────────────────────────────────────
        store.upsert(chunks)

    except (UnsupportedFileTypeError, IngestError):
        raise
    except Exception as exc:
        raise IngestError(f"Ingestion failed for {abs_path!r}: {exc}") from exc

    logger.info(
        "Ingested %s → %d chunks (doc_id=%s)",
        meta.filename,
        len(chunks),
        meta.doc_id[:12],
    )
    return IngestResult(
        doc_id=meta.doc_id,
        filename=meta.filename,
        chunks_added=len(chunks),
    )


def _embed_chunks(chunks: list[Chunk], embedder: EmbedderProtocol) -> None:
    """Embed all chunks in-place using the provided embedder.

    Chunks are processed in batches sized by ``settings.embed_batch_size``.
    The ``embedding`` field of each chunk is populated directly.
    """
    from config import settings  # local import to avoid circular at module level

    batch_size = settings.embed_batch_size
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        texts = [c.text for c in batch]
        vectors = embedder.embed(texts)
        for chunk, vector in zip(batch, vectors):
            chunk.embedding = vector

    logger.debug("Embedded %d chunks.", len(chunks))
