"""Citation guard for TaxBot answer generation.

After the LLM returns its response, this module ensures a "Sources:" section
is always present.  If the model omitted citations, the guard appends them
from the retrieved chunk list — not from the model's output — so citations
are always grounded in real retrieved data.
"""

from __future__ import annotations

import re

from retrieval.reranker import RetrievedChunk

# Matches a "Sources:" block anywhere in the answer (case-insensitive,
# handles "Sources:", "Sources :", "SOURCES:", etc.)
_SOURCES_RE = re.compile(r"sources\s*:", re.IGNORECASE)


def _format_sources(chunks: list[RetrievedChunk]) -> str:
    """Render a Sources block from a list of retrieved chunks."""
    if not chunks:
        return "Sources:\n- (none retrieved)"

    lines = ["Sources:"]
    for i, chunk in enumerate(chunks, start=1):
        heading = f", {chunk.section_heading}" if chunk.section_heading else ""
        page = f", Page {chunk.page_number}" if chunk.page_number else ""
        ay = f", AY {chunk.assessment_year}" if chunk.assessment_year != "unknown" else ""
        lines.append(f"- [{i}] {chunk.doc_title}{heading}{page}{ay}")

    return "\n".join(lines)


def ensure_citations(answer: str, chunks: list[RetrievedChunk]) -> str:
    """Guarantee that *answer* contains a Sources section.

    If ``answer`` already contains a sources block (detected by a
    case-insensitive ``"Sources:"`` marker), it is returned unchanged.
    Otherwise a formatted sources block is appended, derived from *chunks*.

    Args:
        answer: Raw text returned by the LLM.
        chunks: The retrieved chunks that were passed to the LLM as context.

    Returns:
        The answer string, guaranteed to contain a Sources section.
    """
    if _SOURCES_RE.search(answer):
        return answer  # model included citations — trust them

    sources_block = _format_sources(chunks)
    return f"{answer.rstrip()}\n\n{sources_block}"
