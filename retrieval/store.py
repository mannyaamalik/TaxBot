"""ChromaDB vector store wrapper for TaxBot.

Provides a thin, type-safe interface over the ChromaDB persistent client.
All embedding vectors stored here must be L2-normalised so that cosine
similarity equals dot product.

The ``VectorStore`` instance should be created once at app startup and
injected wherever it is needed (pipeline, retriever, health endpoint).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from config import settings
from exceptions import VectorStoreError
from ingestion.chunker import Chunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model returned by queries
# ---------------------------------------------------------------------------


@dataclass
class RawResult:
    """A single chunk returned by a ChromaDB similarity query."""

    chunk_id: str
    text: str
    distance: float        # ChromaDB cosine distance (0 = identical)
    similarity: float      # 1 - distance (higher = more similar)
    doc_id: str
    doc_title: str
    filename: str
    section_heading: str
    page_number: int
    assessment_year: str
    doc_type: str
    chunk_index: int
    ingested_at: str


# ---------------------------------------------------------------------------
# VectorStore  (TASK-017)
# ---------------------------------------------------------------------------


class VectorStore:
    """Wrapper around a ChromaDB persistent collection."""

    def __init__(
        self,
        db_path: str | None = None,
        collection_name: str | None = None,
    ) -> None:
        path = db_path or settings.chroma_db_path
        name = collection_name or settings.chroma_collection

        # Ensure the directory exists
        Path(path).mkdir(parents=True, exist_ok=True)

        try:
            self._client: ClientAPI = chromadb.PersistentClient(path=path)
            self._collection: Collection = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            raise VectorStoreError(f"Failed to initialise ChromaDB at {path!r}: {exc}") from exc

        logger.info(
            "VectorStore ready: path=%s collection=%s chunks=%d",
            path,
            name,
            self.count(),
        )

    # ── Write operations ──────────────────────────────────────────────────

    def upsert(self, chunks: list[Chunk]) -> None:
        """Add or replace chunks in the collection.

        Each chunk must have a non-empty ``embedding`` list.

        Args:
            chunks: Chunks produced by the ingestion pipeline with embeddings
                    already attached.

        Raises:
            VectorStoreError: on any ChromaDB error.
        """
        if not chunks:
            return

        ids: list[str] = []
        documents: list[str] = []
        embeddings: list[list[float]] = []
        metadatas: list[dict[str, Any]] = []

        for chunk in chunks:
            if not chunk.embedding:
                raise VectorStoreError(
                    f"Chunk {chunk.chunk_id} has no embedding; run embed() first."
                )
            ids.append(chunk.chunk_id)
            documents.append(chunk.text)
            embeddings.append(chunk.embedding)
            metadatas.append(
                {
                    "doc_id": chunk.metadata.doc_id,
                    "filename": chunk.metadata.filename,
                    "doc_title": chunk.metadata.doc_title,
                    "assessment_year": chunk.metadata.assessment_year,
                    "doc_type": chunk.metadata.doc_type,
                    "section_heading": chunk.metadata.section_heading,
                    "page_number": chunk.metadata.page_number,
                    "chunk_index": chunk.metadata.chunk_index,
                    "ingested_at": chunk.metadata.ingested_at,
                }
            )

        try:
            self._collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        except Exception as exc:
            raise VectorStoreError(f"Upsert failed: {exc}") from exc

        logger.debug("Upserted %d chunks into collection.", len(chunks))

    def delete_by_doc_id(self, doc_id: str) -> int:
        """Delete all chunks belonging to a document.

        Args:
            doc_id: SHA-256 of the source document (from ``DocMetadata.doc_id``).

        Returns:
            Number of chunks deleted.

        Raises:
            VectorStoreError: on any ChromaDB error.
        """
        try:
            # ChromaDB where filter
            existing = self._collection.get(
                where={"doc_id": {"$eq": doc_id}},
                include=[],
            )
            ids_to_delete: list[str] = existing.get("ids", [])
            if ids_to_delete:
                self._collection.delete(ids=ids_to_delete)
                logger.debug(
                    "Deleted %d chunks for doc_id=%s", len(ids_to_delete), doc_id
                )
            return len(ids_to_delete)
        except Exception as exc:
            raise VectorStoreError(f"Delete failed for doc_id={doc_id!r}: {exc}") from exc

    # ── Read operations ───────────────────────────────────────────────────

    def query(
        self,
        vector: list[float],
        n_results: int,
        where_filter: dict[str, Any] | None = None,
    ) -> list[RawResult]:
        """Query the collection by embedding similarity.

        Args:
            vector: L2-normalised query embedding.
            n_results: Maximum number of results to return.
            where_filter: Optional ChromaDB metadata filter dict.

        Returns:
            List of ``RawResult`` sorted by similarity (highest first).

        Raises:
            VectorStoreError: on any ChromaDB error.
        """
        if not vector:
            return []

        # ChromaDB requires n_results ≤ collection size
        total = self.count()
        if total == 0:
            return []
        n = min(n_results, total)

        try:
            kwargs: dict[str, Any] = {
                "query_embeddings": [vector],
                "n_results": n,
                "include": ["documents", "metadatas", "distances"],
            }
            if where_filter:
                kwargs["where"] = where_filter

            response = self._collection.query(**kwargs)
        except Exception as exc:
            raise VectorStoreError(f"Query failed: {exc}") from exc

        results: list[RawResult] = []
        ids = response.get("ids", [[]])[0]
        docs = response.get("documents", [[]])[0]
        metas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]

        for chunk_id, doc, meta, dist in zip(ids, docs, metas, distances):
            meta = meta or {}
            results.append(
                RawResult(
                    chunk_id=chunk_id,
                    text=doc,
                    distance=float(dist),
                    similarity=1.0 - float(dist),
                    doc_id=meta.get("doc_id", ""),
                    doc_title=meta.get("doc_title", ""),
                    filename=meta.get("filename", ""),
                    section_heading=meta.get("section_heading", ""),
                    page_number=int(meta.get("page_number", 0)),
                    assessment_year=meta.get("assessment_year", "unknown"),
                    doc_type=meta.get("doc_type", "other"),
                    chunk_index=int(meta.get("chunk_index", 0)),
                    ingested_at=meta.get("ingested_at", ""),
                )
            )

        return results

    def count(self) -> int:
        """Return the total number of chunks in the collection."""
        try:
            return self._collection.count()
        except Exception as exc:
            raise VectorStoreError(f"Count failed: {exc}") from exc

    def list_documents(self) -> list[dict[str, Any]]:
        """Return one summary row per distinct filename in the collection.

        Used by the ``--list`` flag of the update_kb CLI script.
        """
        try:
            # Fetch all metadata (no embeddings, no documents)
            response = self._collection.get(include=["metadatas"])
        except Exception as exc:
            raise VectorStoreError(f"list_documents failed: {exc}") from exc

        metas: list[dict[str, Any]] = response.get("metadatas") or []
        seen: dict[str, dict[str, Any]] = {}

        for meta in metas:
            if not meta:
                continue
            fname = meta.get("filename", "")
            if fname not in seen:
                seen[fname] = {
                    "filename": fname,
                    "doc_title": meta.get("doc_title", ""),
                    "assessment_year": meta.get("assessment_year", "unknown"),
                    "doc_type": meta.get("doc_type", "other"),
                    "chunk_count": 0,
                }
            seen[fname]["chunk_count"] += 1

        return sorted(seen.values(), key=lambda r: r["filename"])
