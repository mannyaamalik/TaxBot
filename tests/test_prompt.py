"""Unit tests for generation/prompt.py  (TASK-023)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from generation.prompt import (
    NOT_FOUND_MSG,
    SYSTEM_PROMPT,
    Turn,
    build_prompt,
    _context_block,
    _history_block,
)
from retrieval.reranker import RetrievedChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    text: str = "Tax rule text.",
    doc_title: str = "IT Act 1961",
    section_heading: str = "Section 80C",
    page_number: int = 42,
    assessment_year: str = "2024-25",
) -> RetrievedChunk:
    return RetrievedChunk(
        text=text,
        score=0.9,
        doc_title=doc_title,
        section_heading=section_heading,
        page_number=page_number,
        filename="IT_Act_AY2024-25.pdf",
        assessment_year=assessment_year,
        chunk_index=0,
        doc_id="abc123",
    )


def _make_turn(role: str, content: str) -> Turn:
    return Turn(role=role, content=content)


# ---------------------------------------------------------------------------
# Test 1: System prompt is first message
# ---------------------------------------------------------------------------


def test_system_prompt_is_first_message():
    """build_prompt must return a list whose first element is the system message."""
    messages = build_prompt("What is 80C?", [], [])

    assert len(messages) >= 1
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Test 2: Context block numbering matches chunk count
# ---------------------------------------------------------------------------


def test_context_numbering_matches_chunk_count():
    """The user message must contain [1] through [n] for n chunks."""
    chunks = [_make_chunk(text=f"Chunk {i} about taxes.") for i in range(1, 4)]
    messages = build_prompt("Test question", chunks, [])

    user_content = messages[1]["content"]
    for i in range(1, len(chunks) + 1):
        assert f"[{i}]" in user_content, (
            f"Expected '[{i}]' in user message but it was missing.\n"
            f"User content (first 500 chars):\n{user_content[:500]}"
        )


# ---------------------------------------------------------------------------
# Test 3: History is empty when no history provided
# ---------------------------------------------------------------------------


def test_history_block_absent_when_empty():
    """When history=[], no CONVERSATION HISTORY section should appear."""
    messages = build_prompt("What is TDS?", [_make_chunk()], [])
    user_content = messages[1]["content"]
    assert "CONVERSATION HISTORY" not in user_content


# ---------------------------------------------------------------------------
# Test 4: History is truncated to the last N turns
# ---------------------------------------------------------------------------


def test_history_truncated_to_n_turns():
    """Only the last SESSION_HISTORY_TURNS * 2 turns should appear."""
    from config import settings

    max_turns = settings.session_history_turns * 2  # each Q+A = 2 turns

    # Build more turns than the limit
    history = []
    for i in range(max_turns + 4):
        history.append(_make_turn("user", f"Question {i}"))
        history.append(_make_turn("assistant", f"Answer {i}"))

    messages = build_prompt("New question", [_make_chunk()], history)
    user_content = messages[1]["content"]

    # The oldest question (Question 0) should NOT appear
    assert "Question 0" not in user_content, (
        "Oldest history turn should have been truncated."
    )
    # The most recent question should appear
    last_q_index = max_turns + 3
    assert f"Question {last_q_index}" in user_content, (
        f"Most recent question (Question {last_q_index}) not found in prompt."
    )


# ---------------------------------------------------------------------------
# Test 5: Empty chunks list still produces a valid messages list
# ---------------------------------------------------------------------------


def test_empty_chunks_produces_valid_messages():
    """build_prompt with no chunks must still return a well-formed messages list."""
    messages = build_prompt("What is GST?", [], [])

    assert isinstance(messages, list)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    # Context block must be absent (no --- CONTEXT --- section)
    assert "--- CONTEXT ---" not in messages[1]["content"]
    # Question must still be present
    assert "What is GST?" in messages[1]["content"]


# ---------------------------------------------------------------------------
# Test 6: Source metadata appears in context block
# ---------------------------------------------------------------------------


def test_context_block_contains_source_metadata():
    """Each context entry must include doc_title, section_heading, page, and AY."""
    chunk = _make_chunk(
        doc_title="Income Tax Act 1961",
        section_heading="Section 80C",
        page_number=112,
        assessment_year="2024-25",
    )
    block = _context_block([chunk])

    assert "Income Tax Act 1961" in block
    assert "Section 80C" in block
    assert "112" in block
    assert "2024-25" in block


# ---------------------------------------------------------------------------
# Test 7: System prompt contains all 8 rules
# ---------------------------------------------------------------------------


def test_system_prompt_contains_key_rules():
    """The system prompt must contain the core behavioural rules."""
    checks = [
        ("RULE 1", "answers from context only"),
        ("RULE 2", "not found message"),
        ("RULE 3", "citations"),
        ("RULE 5", "clarifying question"),
        ("RULE 7", "no personalised advice"),
        ("RULE 8", "confidentiality"),
    ]
    for rule_id, description in checks:
        assert rule_id in SYSTEM_PROMPT, (
            f"System prompt missing {rule_id} ({description})."
        )


# ---------------------------------------------------------------------------
# Test 8: NOT_FOUND_MSG contains the official portal URLs
# ---------------------------------------------------------------------------


def test_not_found_msg_contains_portal_urls():
    assert "incometax.gov.in" in NOT_FOUND_MSG
    assert "gst.gov.in" in NOT_FOUND_MSG
