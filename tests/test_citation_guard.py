"""Unit tests for generation/citation_guard.py  (TASK-028)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from generation.citation_guard import ensure_citations, _format_sources
from retrieval.reranker import RetrievedChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    doc_title: str = "IT Act 1961",
    section_heading: str = "Section 80C",
    page_number: int = 42,
    assessment_year: str = "2024-25",
    filename: str = "IT_Act.pdf",
) -> RetrievedChunk:
    return RetrievedChunk(
        text="The deduction limit is ₹1,50,000.",
        score=0.9,
        doc_title=doc_title,
        section_heading=section_heading,
        page_number=page_number,
        filename=filename,
        assessment_year=assessment_year,
        chunk_index=0,
        doc_id="abc123",
    )


# ---------------------------------------------------------------------------
# Test 1: Answer that already has Sources is returned unchanged
# ---------------------------------------------------------------------------


def test_answer_with_sources_unchanged():
    """If the LLM included a Sources section, the guard must not modify the answer."""
    answer = (
        "The deduction limit under Section 80C is ₹1,50,000 [1].\n\n"
        "Sources:\n"
        "- [1] IT Act 1961, Section 80C, Page 42, AY 2024-25"
    )
    result = ensure_citations(answer, [_make_chunk()])
    assert result == answer


def test_answer_with_sources_case_insensitive():
    """Sources detection must be case-insensitive (SOURCES:, sources:, etc.)."""
    answer = "Some answer.\n\nSOURCES:\n- [1] Some doc"
    result = ensure_citations(answer, [_make_chunk()])
    assert result == answer


# ---------------------------------------------------------------------------
# Test 2: Answer missing Sources gets a correctly formatted block appended
# ---------------------------------------------------------------------------


def test_missing_sources_appended():
    """When Sources is absent, the guard appends a formatted Sources section."""
    answer = "The 80C limit is ₹1,50,000."
    chunk = _make_chunk(
        doc_title="Income Tax Act 1961",
        section_heading="Section 80C",
        page_number=112,
        assessment_year="2024-25",
    )

    result = ensure_citations(answer, [chunk])

    assert "Sources:" in result
    assert "Income Tax Act 1961" in result
    assert "Section 80C" in result
    assert "112" in result
    assert "2024-25" in result
    # Original answer text must still be present
    assert "₹1,50,000" in result


def test_missing_sources_has_correct_numbering():
    """Appended Sources entries must be numbered [1], [2], [3]…"""
    answer = "Some tax answer without citations."
    chunks = [
        _make_chunk(doc_title="IT Act", section_heading="Sec 80C"),
        _make_chunk(doc_title="GST Act", section_heading="Reg 10"),
        _make_chunk(doc_title="CBDT Circular", section_heading="Para 3"),
    ]

    result = ensure_citations(answer, chunks)

    for i in range(1, len(chunks) + 1):
        assert f"[{i}]" in result, f"Entry [{i}] not found in appended sources."


# ---------------------------------------------------------------------------
# Test 3: Empty chunks list produces "(none retrieved)"
# ---------------------------------------------------------------------------


def test_empty_chunks_produces_none_retrieved():
    """With no chunks, the guard appends 'Sources:\\n- (none retrieved)'."""
    answer = "Here is a generated answer."
    result = ensure_citations(answer, [])

    assert "Sources:" in result
    assert "(none retrieved)" in result


# ---------------------------------------------------------------------------
# Test 4: _format_sources directly
# ---------------------------------------------------------------------------


def test_format_sources_multiple_chunks():
    """_format_sources must produce one numbered entry per chunk."""
    chunks = [_make_chunk(doc_title=f"Doc {i}") for i in range(3)]
    block = _format_sources(chunks)

    assert block.startswith("Sources:")
    for i in range(1, 4):
        assert f"[{i}]" in block


def test_format_sources_empty():
    """_format_sources with empty list must produce the none-retrieved line."""
    block = _format_sources([])
    assert "(none retrieved)" in block


def test_format_sources_unknown_ay_omitted():
    """assessment_year 'unknown' should not appear in the formatted source line."""
    chunk = _make_chunk(assessment_year="unknown")
    block = _format_sources([chunk])
    assert "unknown" not in block
