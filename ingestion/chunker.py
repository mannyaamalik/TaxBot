"""Sliding-window sentence-boundary chunker for the TaxBot ingestion pipeline.

Splits document pages into overlapping text chunks while respecting sentence
boundaries — critical for tax documents where statutory qualifiers ("provided
that the aggregate shall not exceed ₹1,50,000") always appear at the end of
a sentence.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from uuid import uuid4

import nltk

from config import settings
from ingestion.loader import RawPage
from ingestion.metadata import DocMetadata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ChunkMetadata:
    """Per-chunk metadata stored alongside chunk text in ChromaDB."""

    doc_id: str
    filename: str
    doc_title: str
    assessment_year: str
    doc_type: str
    section_heading: str
    page_number: int
    chunk_index: int   # 0-based index within the whole document
    ingested_at: str


@dataclass
class Chunk:
    """A single text chunk ready for embedding and storage."""

    chunk_id: str       # UUID4
    text: str
    token_count: int    # whitespace-split approximation
    embedding: list[float]  # populated later by the pipeline
    metadata: ChunkMetadata


# ---------------------------------------------------------------------------
# Heading detection heuristic
# ---------------------------------------------------------------------------

_HEADING_PATTERNS = (
    re.compile(r"^(SECTION|CHAPTER|PART|SCHEDULE|RULE|ARTICLE)\s+\d+", re.IGNORECASE),
    re.compile(r"^[A-Z][A-Z\s\-–]{8,}$"),   # ALL-CAPS lines ≥ 8 chars
    re.compile(r"^\d+\.\s+[A-Z]"),           # "1. Capital Gains"
)


def _is_heading(sentence: str) -> bool:
    """Return True if the sentence looks like a section heading."""
    stripped = sentence.strip()
    # Must be short enough to be a heading (not a full paragraph)
    if len(stripped.split()) > 15:
        return False
    return any(p.match(stripped) for p in _HEADING_PATTERNS)


# ---------------------------------------------------------------------------
# Token-count approximation
# ---------------------------------------------------------------------------


def _token_count(text: str) -> int:
    """Fast whitespace-split token count approximation."""
    return len(text.split())


# ---------------------------------------------------------------------------
# Core chunker  (TASK-010)
# ---------------------------------------------------------------------------


def _split_oversized_sentence(sentence: str, max_tokens: int) -> list[str]:
    """Split a sentence that exceeds max_tokens at whitespace boundaries."""
    words = sentence.split()
    parts: list[str] = []
    current: list[str] = []
    current_count = 0

    for word in words:
        if current_count + 1 > max_tokens and current:
            parts.append(" ".join(current))
            current = []
            current_count = 0
        current.append(word)
        current_count += 1

    if current:
        parts.append(" ".join(current))
    return parts


def chunk_document(
    raw_pages: list[RawPage],
    meta: DocMetadata,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    """Split a document's pages into overlapping sentence-boundary chunks.

    Args:
        raw_pages: Output of a document loader.
        meta: Document-level metadata from ``extract_metadata``.
        chunk_size: Override ``settings.chunk_size`` (tokens).
        chunk_overlap: Override ``settings.chunk_overlap`` (tokens).

    Returns:
        A list of ``Chunk`` objects with ``embedding=[]`` (populated later).
    """
    max_tokens: int = chunk_size if chunk_size is not None else settings.chunk_size
    overlap_tokens: int = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap

    chunks: list[Chunk] = []
    chunk_index = 0
    current_heading = ""

    for raw_page in raw_pages:
        if not raw_page.text.strip():
            continue

        # Sentence tokenise the page
        try:
            sentences: list[str] = nltk.sent_tokenize(raw_page.text)
        except Exception:
            # Fall back to splitting on newlines if NLTK fails
            sentences = [ln for ln in raw_page.text.splitlines() if ln.strip()]

        # Expand any sentence that exceeds max_tokens
        expanded: list[str] = []
        for sent in sentences:
            if _token_count(sent) > max_tokens:
                expanded.extend(_split_oversized_sentence(sent, max_tokens))
            else:
                expanded.append(sent)
        sentences = expanded

        # Sliding window over sentences
        window: list[str] = []
        window_tokens = 0
        sent_idx = 0

        while sent_idx < len(sentences):
            sent = sentences[sent_idx]

            # Track section heading
            if _is_heading(sent):
                current_heading = sent.strip()

            sent_tokens = _token_count(sent)
            window.append(sent)
            window_tokens += sent_tokens
            sent_idx += 1

            # Emit chunk when window is full (or last sentence of the page)
            is_last = sent_idx == len(sentences)
            if window_tokens >= max_tokens or is_last:
                chunk_text = " ".join(window).strip()
                if chunk_text:
                    chunks.append(
                        Chunk(
                            chunk_id=str(uuid4()),
                            text=chunk_text,
                            token_count=_token_count(chunk_text),
                            embedding=[],
                            metadata=ChunkMetadata(
                                doc_id=meta.doc_id,
                                filename=meta.filename,
                                doc_title=meta.doc_title,
                                assessment_year=meta.assessment_year,
                                doc_type=meta.doc_type,
                                section_heading=current_heading,
                                page_number=raw_page.page_number,
                                chunk_index=chunk_index,
                                ingested_at=meta.ingested_at,
                            ),
                        )
                    )
                    chunk_index += 1

                if is_last:
                    break

                # Step back overlap_tokens worth of sentences for the next window
                overlap_window: list[str] = []
                overlap_count = 0
                for prev_sent in reversed(window):
                    prev_tokens = _token_count(prev_sent)
                    if overlap_count + prev_tokens > overlap_tokens:
                        break
                    overlap_window.insert(0, prev_sent)
                    overlap_count += prev_tokens

                window = overlap_window
                window_tokens = overlap_count

    logger.debug(
        "chunk_document: %s → %d chunks (chunk_size=%d, overlap=%d)",
        meta.filename,
        len(chunks),
        max_tokens,
        overlap_tokens,
    )
    return chunks
