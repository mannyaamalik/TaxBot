"""Shared pytest fixtures for TaxBot tests."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is importable regardless of where pytest is invoked from
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_chroma_store(tmp_path: Path):
    """A VectorStore backed by a temporary ChromaDB directory."""
    # Import here so the fixture only loads ChromaDB when actually needed
    from retrieval.store import VectorStore

    store = VectorStore(
        db_path=str(tmp_path / "chromadb"),
        collection_name="test_collection",
    )
    yield store


@pytest.fixture()
def mock_embedder():
    """A mock embedder that returns deterministic 4-dimensional vectors."""
    embedder = MagicMock()

    def _embed(texts: list[str]) -> list[list[float]]:
        # Return a simple deterministic vector based on text length
        return [[float(len(t) % 10), 0.1, 0.2, 0.3] for t in texts]

    embedder.embed.side_effect = _embed
    return embedder


@pytest.fixture()
def sample_doc_metadata():
    """A minimal DocMetadata instance for use in chunker tests."""
    from ingestion.metadata import DocMetadata

    return DocMetadata(
        doc_id="abc123",
        filename="test_doc.pdf",
        doc_title="Test Tax Document",
        assessment_year="2024-25",
        doc_type="act",
        ingested_at="2024-01-01T00:00:00+00:00",
        source_url="",
    )
