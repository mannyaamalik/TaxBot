"""Unit tests for ingestion/chunker.py  (TASK-011)."""

from __future__ import annotations

import pytest

from ingestion.chunker import Chunk, chunk_document, _is_heading
from ingestion.loader import RawPage
from ingestion.metadata import DocMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_meta(**kwargs) -> DocMetadata:
    defaults = dict(
        doc_id="test-doc-id",
        filename="test.pdf",
        doc_title="Test Document",
        assessment_year="2024-25",
        doc_type="act",
        ingested_at="2024-01-01T00:00:00+00:00",
        source_url="",
    )
    defaults.update(kwargs)
    return DocMetadata(**defaults)


def _pages(texts: list[str]) -> list[RawPage]:
    return [
        RawPage(text=t, page_number=i + 1, source_path="/fake/path.pdf")
        for i, t in enumerate(texts)
    ]


# ---------------------------------------------------------------------------
# Test 1: Consecutive chunks share at least one sentence of overlap
# ---------------------------------------------------------------------------


def test_overlap_between_consecutive_chunks():
    """The last sentence of chunk N must appear as the first sentence(s) of chunk N+1."""
    # Build a page with many short sentences so the chunker produces multiple chunks
    sentences = [f"This is sentence number {i} about Indian tax law." for i in range(50)]
    page_text = " ".join(sentences)

    meta = _make_meta()
    pages = _pages([page_text])

    # Use small chunk_size so we definitely get multiple chunks
    chunks = chunk_document(pages, meta, chunk_size=50, chunk_overlap=15)

    assert len(chunks) >= 2, "Expected multiple chunks from a long page"

    for i in range(len(chunks) - 1):
        chunk_a: Chunk = chunks[i]
        chunk_b: Chunk = chunks[i + 1]

        # The overlap means chunk B should start with text that also ended chunk A.
        # We check that at least one sentence from the tail of A appears in B.
        a_sentences = chunk_a.text.split(". ")
        b_text = chunk_b.text

        overlap_found = any(sent.strip() in b_text for sent in a_sentences[-3:] if sent.strip())
        assert overlap_found, (
            f"No overlap sentence found between chunk {i} and chunk {i + 1}.\n"
            f"Chunk {i} tail: {a_sentences[-3:]}\n"
            f"Chunk {i + 1} start: {b_text[:200]}"
        )


# ---------------------------------------------------------------------------
# Test 2: Section heading propagation
# ---------------------------------------------------------------------------


def test_heading_propagation():
    """A heading line mid-page sets section_heading on subsequent chunks."""
    text = (
        "Some introductory text about the Income Tax Act. "
        "This covers the basics of taxation in India. "
        "Background information is provided here.\n"
        "SECTION 80C\n"  # heading
        "Under section 80C you can claim deductions for investments. "
        "The maximum limit is one lakh fifty thousand rupees per year. "
        "Eligible instruments include ELSS, PPF, and NSC. "
        "The deduction is available to individuals and HUFs. "
    )

    meta = _make_meta()
    pages = _pages([text])
    chunks = chunk_document(pages, meta, chunk_size=30, chunk_overlap=5)

    assert len(chunks) >= 2, "Expected at least 2 chunks"

    # Find the first chunk that follows the SECTION 80C heading
    post_heading_chunks = [
        c for c in chunks if "SECTION 80C" in c.metadata.section_heading.upper()
    ]
    assert post_heading_chunks, (
        "No chunk has 'SECTION 80C' as its section_heading. "
        f"Headings found: {[c.metadata.section_heading for c in chunks]}"
    )


# ---------------------------------------------------------------------------
# Test 3: Oversized sentence is not dropped
# ---------------------------------------------------------------------------


def test_oversized_sentence_not_dropped():
    """A single sentence longer than chunk_size must still appear in the output."""
    # Create a sentence that is definitely longer than chunk_size=10 tokens
    long_sentence = " ".join([f"word{i}" for i in range(30)])
    text = f"Short intro. {long_sentence}. Short outro."

    meta = _make_meta()
    pages = _pages([text])
    chunks = chunk_document(pages, meta, chunk_size=10, chunk_overlap=2)

    all_text = " ".join(c.text for c in chunks)

    # The long sentence's words must all appear somewhere in the output
    for word in long_sentence.split():
        assert word in all_text, (
            f"Word {word!r} from oversized sentence not found in any chunk."
        )


# ---------------------------------------------------------------------------
# Test 4: Empty input returns empty list without error
# ---------------------------------------------------------------------------


def test_empty_input_returns_empty_list():
    """chunk_document with an empty page list must return [] cleanly."""
    meta = _make_meta()
    result = chunk_document([], meta)
    assert result == []


# ---------------------------------------------------------------------------
# Test 5: No chunk has zero-length text
# ---------------------------------------------------------------------------


def test_no_empty_chunks():
    """Every emitted chunk must have non-empty text."""
    text = "\n".join(
        f"Sentence {i} about GST registration and filing requirements." for i in range(20)
    )
    meta = _make_meta()
    pages = _pages([text])
    chunks = chunk_document(pages, meta, chunk_size=40, chunk_overlap=10)

    for chunk in chunks:
        assert chunk.text.strip(), f"Found empty chunk: {chunk!r}"


# ---------------------------------------------------------------------------
# Test 6: chunk_index is monotonically increasing across the document
# ---------------------------------------------------------------------------


def test_chunk_index_monotonic():
    """chunk_index must increment by 1 for each successive chunk."""
    text = " ".join(f"Sentence {i}." for i in range(60))
    meta = _make_meta()
    pages = _pages([text, text])  # two pages
    chunks = chunk_document(pages, meta, chunk_size=40, chunk_overlap=8)

    for expected, chunk in enumerate(chunks):
        assert chunk.metadata.chunk_index == expected, (
            f"Expected chunk_index {expected}, got {chunk.metadata.chunk_index}"
        )
