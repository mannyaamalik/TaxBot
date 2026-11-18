"""Answer generator — the top-level composition point for TaxBot's RAG pipeline.

Combines the prompt builder, LLM client, and citation guard into a single
``generate_answer`` call.  The generator never makes retrieval decisions —
the caller is responsible for passing the right chunks and history.

Not-found path:
  When ``chunks`` is empty (no passage cleared the similarity threshold),
  the generator returns the canonical NOT_FOUND_MSG without calling the LLM.

Clarification path:
  When the LLM's response begins with "To give you the most accurate answer"
  (the clarification prefix defined in the system prompt), the generator
  returns it as-is with ``needs_clarification=True`` so the API layer can
  signal the UI to render it differently.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from exceptions import LLMError
from generation.citation_guard import ensure_citations
from generation.llm import LLMClientProtocol
from generation.prompt import NOT_FOUND_MSG, OUT_OF_SCOPE_MSG, Turn, build_prompt
from retrieval.reranker import RetrievedChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

_CLARIFICATION_RE = re.compile(
    r"^To give you the most accurate answer", re.IGNORECASE
)

_OUT_OF_SCOPE_RE = re.compile(
    r"I can only answer questions about Indian Income Tax", re.IGNORECASE
)


@dataclass
class SourceItem:
    """A single cited source, extracted from the retrieved chunks."""

    doc_title: str
    section_heading: str
    page_number: int
    filename: str
    assessment_year: str


@dataclass
class GenerationResult:
    """Full result returned to the API layer after answer generation."""

    answer: str
    sources: list[SourceItem] = field(default_factory=list)
    not_found: bool = False
    needs_clarification: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunks_to_sources(chunks: list[RetrievedChunk]) -> list[SourceItem]:
    """Convert retrieved chunks to SourceItem list (deduplicating by filename+section)."""
    seen: set[tuple[str, str]] = set()
    items: list[SourceItem] = []
    for chunk in chunks:
        key = (chunk.filename, chunk.section_heading)
        if key not in seen:
            seen.add(key)
            items.append(
                SourceItem(
                    doc_title=chunk.doc_title,
                    section_heading=chunk.section_heading,
                    page_number=chunk.page_number,
                    filename=chunk.filename,
                    assessment_year=chunk.assessment_year,
                )
            )
    return items


# ---------------------------------------------------------------------------
# Public API  (TASK-029)
# ---------------------------------------------------------------------------


def generate_answer(
    question: str,
    chunks: list[RetrievedChunk],
    history: list[Turn],
    llm_client: LLMClientProtocol,
) -> GenerationResult:
    """Generate a grounded, cited answer to *question*.

    Args:
        question:   The user's current question.
        chunks:     Context passages from retrieval + reranking.
        history:    Prior turns in the current session.
        llm_client: An ``LLMClientProtocol`` instance (Ollama or OpenAI).

    Returns:
        A ``GenerationResult`` with answer text, source metadata, and flags
        for not-found and clarification states.
    """
    # ── Not-found path: no chunks cleared the threshold ───────────────────
    if not chunks:
        logger.info("No context chunks — returning not-found response.")
        return GenerationResult(
            answer=NOT_FOUND_MSG,
            sources=[],
            not_found=True,
            needs_clarification=False,
        )

    # ── Build prompt and call LLM ─────────────────────────────────────────
    messages = build_prompt(question, chunks, history)

    try:
        raw_answer = llm_client.complete(messages)
    except LLMError as exc:
        logger.error("LLM call failed: %s", exc)
        return GenerationResult(
            answer=(
                "I encountered a technical issue generating a response. "
                "Please try again in a moment."
            ),
            sources=[],
            not_found=False,
            needs_clarification=False,
        )

    # ── Detect special response types ─────────────────────────────────────
    is_clarification = bool(_CLARIFICATION_RE.search(raw_answer))
    is_out_of_scope = bool(_OUT_OF_SCOPE_RE.search(raw_answer))

    if is_out_of_scope:
        # Out-of-scope: no sources needed
        return GenerationResult(
            answer=raw_answer.strip(),
            sources=[],
            not_found=False,
            needs_clarification=False,
        )

    if is_clarification:
        # Clarification question: return as-is, no sources appended
        return GenerationResult(
            answer=raw_answer.strip(),
            sources=[],
            not_found=False,
            needs_clarification=True,
        )

    # ── Ensure citations present ──────────────────────────────────────────
    final_answer = ensure_citations(raw_answer, chunks)
    sources = _chunks_to_sources(chunks)

    logger.info(
        "Generated answer (%d chars) from %d chunks, %d sources.",
        len(final_answer),
        len(chunks),
        len(sources),
    )
    return GenerationResult(
        answer=final_answer,
        sources=sources,
        not_found=False,
        needs_clarification=False,
    )
