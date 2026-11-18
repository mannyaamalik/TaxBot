"""Unit tests for retrieval/store.py  (TASK-018)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

from ingestion.chunker import Chunk, ChunkMetadata
from retrieval.store import VectorStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    text: str,
    doc_id: str = "doc-001",
    embedding: list[float] | None = None,
) -> Chunk:
    """Create a minimal Chunk with a random ID and the given embedding."""
    if embedding is None:
        # Random 4-dim unit vector
        v = np.random.rand(4).astype(np.float32)
        v /= np.linalg.norm(v)
        embedding = v.tolist()

    return Chunk(
        chunk_id=str(uuid4()),
        text=text,
        token_count=len(text.split()),
        embedding=embedding,
        metadata=ChunkMetadata(
            doc_id=doc_id,
            filename="test.pdf",
            doc_title="Test Doc",
            assessment_year="2024-25",
            doc_type="act",
            section_heading="",
            page_number=1,
            chunk_index=0,
            ingested_at="2024-01-01T00:00:00+00:00",
        ),
    )


def _unit_vec(values: list[float]) -> list[float]:
    """Return an L2-normalised version of *values*."""
    arr = np.array(values, dtype=np.float32)
    norm = np.linalg.norm(arr)
    return (arr / norm).tolist()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_upsert_then_count(tmp_path: Path) -> None:
    """upsert([chunk]) followed by count() should return 1."""
    store = VectorStore(
        db_path=str(tmp_path / "db"),
        collection_name="test_upsert",
    )
    assert store.count() == 0

    chunk = _make_chunk("Section 80C deduction limit is ₹1,50,000.")
    store.upsert([chunk])

    assert store.count() == 1


def test_delete_by_doc_id(tmp_path: Path) -> None:
    """delete_by_doc_id removes all chunks for that doc_id."""
    store = VectorStore(
        db_path=str(tmp_path / "db"),
        collection_name="test_delete",
    )

    doc_id = "delete-me-doc"
    chunks = [_make_chunk(f"Chunk {i}", doc_id=doc_id) for i in range(3)]
    # Also add a chunk from a different doc to ensure it is not deleted
    other_chunk = _make_chunk("Unrelated chunk", doc_id="keep-this-doc")
    store.upsert(chunks + [other_chunk])

    assert store.count() == 4

    deleted = store.delete_by_doc_id(doc_id)
    assert deleted == 3
    assert store.count() == 1  # only the other_chunk remains


def test_query_returns_most_similar(tmp_path: Path) -> None:
    """query() must return the semantically closest chunk first."""
    store = VectorStore(
        db_path=str(tmp_path / "db"),
        collection_name="test_query",
    )

    # Three 4-dim unit vectors pointing in very different directions
    vec_a = _unit_vec([1.0, 0.0, 0.0, 0.0])  # points along x-axis
    vec_b = _unit_vec([0.0, 1.0, 0.0, 0.0])  # points along y-axis
    vec_c = _unit_vec([0.0, 0.0, 1.0, 0.0])  # points along z-axis

    chunk_a = _make_chunk("GST registration threshold", embedding=vec_a)
    chunk_b = _make_chunk("Income tax slab rates", embedding=vec_b)
    chunk_c = _make_chunk("TDS deduction rates", embedding=vec_c)

    store.upsert([chunk_a, chunk_b, chunk_c])
    assert store.count() == 3

    # Query with a vector close to vec_b (income tax slabs)
    query_vec = _unit_vec([0.05, 0.98, 0.05, 0.0])
    results = store.query(query_vec, n_results=3)

    assert len(results) > 0
    # The top result must be chunk_b (income tax slabs)
    assert results[0].text == "Income tax slab rates", (
        f"Expected 'Income tax slab rates' as top result, got {results[0].text!r}"
    )


def test_upsert_idempotent(tmp_path: Path) -> None:
    """Upserting the same chunk twice must not create duplicates."""
    store = VectorStore(
        db_path=str(tmp_path / "db"),
        collection_name="test_idempotent",
    )
    chunk = _make_chunk("Capital gains tax on LTCG")
    store.upsert([chunk])
    store.upsert([chunk])  # second upsert of same chunk_id

    assert store.count() == 1


def test_query_empty_store(tmp_path: Path) -> None:
    """Querying an empty store returns an empty list without error."""
    store = VectorStore(
        db_path=str(tmp_path / "db"),
        collection_name="test_empty_query",
    )
    results = store.query(_unit_vec([1.0, 0.0, 0.0, 0.0]), n_results=5)
    assert results == []


def test_list_documents(tmp_path: Path) -> None:
    """list_documents returns one entry per distinct filename."""
    store = VectorStore(
        db_path=str(tmp_path / "db"),
        collection_name="test_list",
    )

    for i in range(3):
        chunk = _make_chunk(f"Text {i}")
        chunk.metadata.filename = "doc_a.pdf"
        store.upsert([chunk])

    for i in range(2):
        chunk = _make_chunk(f"Other text {i}", doc_id="doc-b")
        chunk.metadata.filename = "doc_b.pdf"
        store.upsert([chunk])

    docs = store.list_documents()
    filenames = [d["filename"] for d in docs]
    assert "doc_a.pdf" in filenames
    assert "doc_b.pdf" in filenames
    assert len(filenames) == 2
