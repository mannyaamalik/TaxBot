"""Unit tests for generation/generator.py  (TASK-029)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from generation.generator import GenerationResult, generate_answer
from generation.prompt import NOT_FOUND_MSG, Turn
from retrieval.reranker import RetrievedChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(text: str = "Section 80C limit is ₹1,50,000.") -> RetrievedChunk:
    return RetrievedChunk(
        text=text,
        score=0.9,
        doc_title="IT Act 1961",
        section_heading="Section 80C",
        page_number=42,
        filename="IT_Act.pdf",
        assessment_year="2024-25",
        chunk_index=0,
        doc_id="abc",
    )


def _mock_llm(reply: str) -> MagicMock:
    client = MagicMock()
    client.complete.return_value = reply
    return client


# ---------------------------------------------------------------------------
# Test 1: Empty chunks → not_found=True, NOT_FOUND_MSG, no LLM call
# ---------------------------------------------------------------------------


def test_empty_chunks_returns_not_found():
    llm = _mock_llm("Should not be called")
    result = generate_answer("What is 80C?", [], [], llm)

    assert result.not_found is True
    assert result.answer == NOT_FOUND_MSG
    assert result.sources == []
    llm.complete.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: Non-empty chunks → not_found=False, LLM is called
# ---------------------------------------------------------------------------


def test_non_empty_chunks_calls_llm():
    reply = (
        "The Section 80C limit is ₹1,50,000 [1].\n\n"
        "Sources:\n- [1] IT Act 1961, Section 80C, Page 42, AY 2024-25"
    )
    llm = _mock_llm(reply)
    result = generate_answer("What is the 80C limit?", [_make_chunk()], [], llm)

    llm.complete.assert_called_once()
    assert result.not_found is False
    assert "₹1,50,000" in result.answer


# ---------------------------------------------------------------------------
# Test 3: sources list is populated from chunks
# ---------------------------------------------------------------------------


def test_sources_populated_from_chunks():
    reply = "The limit is ₹1,50,000.\n\nSources:\n- [1] IT Act 1961, Section 80C, Page 42"
    llm = _mock_llm(reply)
    result = generate_answer("80C limit?", [_make_chunk()], [], llm)

    assert len(result.sources) >= 1
    assert result.sources[0].doc_title == "IT Act 1961"


# ---------------------------------------------------------------------------
# Test 4: Citation guard fires when LLM omits Sources
# ---------------------------------------------------------------------------


def test_citation_guard_fires_when_llm_omits_sources():
    # LLM returns an answer with no Sources section
    llm = _mock_llm("The deduction limit is ₹1,50,000.")
    result = generate_answer("80C limit?", [_make_chunk()], [], llm)

    assert "Sources:" in result.answer, (
        "Citation guard did not append Sources section.\n"
        f"Answer: {result.answer}"
    )


# ---------------------------------------------------------------------------
# Test 5: Clarification response detected
# ---------------------------------------------------------------------------


def test_clarification_response_detected():
    reply = (
        "To give you the most accurate answer, could you tell me: "
        "Are you filing under the old or new tax regime?"
    )
    llm = _mock_llm(reply)
    result = generate_answer("What is my tax?", [_make_chunk()], [], llm)

    assert result.needs_clarification is True
    assert result.not_found is False


# ---------------------------------------------------------------------------
# Test 6: Out-of-scope response detected
# ---------------------------------------------------------------------------


def test_out_of_scope_response():
    reply = "I can only answer questions about Indian Income Tax and GST."
    llm = _mock_llm(reply)
    result = generate_answer("What is the weather today?", [_make_chunk()], [], llm)

    assert result.not_found is False
    assert result.needs_clarification is False
    assert result.sources == []


# ---------------------------------------------------------------------------
# Test 7: LLM failure returns a graceful error message
# ---------------------------------------------------------------------------


def test_llm_failure_returns_error_message():
    from exceptions import LLMError

    llm = MagicMock()
    llm.complete.side_effect = LLMError("Connection refused")

    result = generate_answer("What is TDS?", [_make_chunk()], [], llm)

    assert result.not_found is False
    assert "technical issue" in result.answer.lower()
    assert result.sources == []


# ---------------------------------------------------------------------------
# Test 8: History is passed through to build_prompt
# ---------------------------------------------------------------------------


def test_history_included_in_prompt():
    """The LLM must receive a prompt containing the conversation history."""
    reply = "Answer text.\n\nSources:\n- [1] IT Act 1961, Section 80C, Page 42"
    llm = _mock_llm(reply)

    history = [
        Turn("user", "What is Section 80C?"),
        Turn("assistant", "80C allows deductions up to ₹1,50,000."),
    ]

    generate_answer("What about 80D?", [_make_chunk()], history, llm)

    # Inspect what was actually passed to the LLM
    call_args = llm.complete.call_args
    messages = call_args[0][0]  # positional first argument
    user_msg = next(m["content"] for m in messages if m["role"] == "user")

    assert "What is Section 80C?" in user_msg, (
        "History turn not found in prompt sent to LLM."
    )


# ---------------------------------------------------------------------------
# Test 9: Duplicate sources deduplicated
# ---------------------------------------------------------------------------


def test_duplicate_sources_deduplicated():
    """Two chunks from the same filename+section should produce one SourceItem."""
    chunks = [_make_chunk(), _make_chunk()]  # identical metadata
    reply = "Answer.\n\nSources:\n- [1] IT Act 1961, Section 80C, Page 42"
    llm = _mock_llm(reply)

    result = generate_answer("Question", chunks, [], llm)

    assert len(result.sources) == 1, (
        f"Expected 1 deduplicated source, got {len(result.sources)}"
    )
