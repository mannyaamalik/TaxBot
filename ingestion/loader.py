"""Document loaders for the TaxBot ingestion pipeline.

Supports PDF (via pdfplumber), HTML (via BeautifulSoup + html2text), and
plain-text / Markdown files.  Each loader returns a list of RawPage objects
with cleaned text and page-number metadata.  This module does not perform
chunking or embedding.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import html2text
import pdfplumber
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RawPage:
    """A single page (or logical section) of a parsed document."""

    text: str
    page_number: int  # 1-based; 0 when page concept is not applicable
    source_path: str  # absolute path to the source file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(
    r"^(Section|Chapter|Part|Schedule|Rule|Article)\s+\d+",
    re.IGNORECASE,
)


def _is_likely_header_footer(line: str, all_pages_lines: list[list[str]]) -> bool:
    """Return True if *line* appears on ≥ 80 % of pages (running header/footer)."""
    total = len(all_pages_lines)
    if total == 0:
        return False
    count = sum(1 for page_lines in all_pages_lines if line in page_lines)
    return count / total >= 0.80


def _clean_text(text: str) -> str:
    """Collapse excessive whitespace while preserving paragraph breaks."""
    # Normalise Windows line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse runs of blank lines to a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing spaces on each line
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# PDF loader  (TASK-006)
# ---------------------------------------------------------------------------


def load_pdf(path: str) -> list[RawPage]:
    """Parse a PDF file and return one RawPage per page.

    Tables are extracted and appended as pipe-delimited rows.  Running
    headers and footers (lines present on ≥ 80 % of pages) are stripped.
    """
    abs_path = str(Path(path).resolve())
    raw_pages: list[RawPage] = []

    with pdfplumber.open(abs_path) as pdf:
        # First pass: collect all lines per page to detect headers/footers
        all_page_lines: list[list[str]] = []
        raw_texts: list[str] = []

        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            all_page_lines.append(lines)

            # Append table content
            table_parts: list[str] = []
            for table in page.extract_tables():
                for row in table:
                    cleaned_row = [cell or "" for cell in row]
                    table_parts.append(" | ".join(cleaned_row))
            if table_parts:
                text = text + "\n" + "\n".join(table_parts)

            raw_texts.append(text)

        # Second pass: strip running headers/footers
        # Count line frequencies across all pages
        line_freq: Counter[str] = Counter()
        for page_lines in all_page_lines:
            for ln in set(page_lines):  # deduplicate within a page
                line_freq[ln] += 1

        total_pages = len(all_page_lines)
        header_footer_lines: set[str] = {
            ln
            for ln, cnt in line_freq.items()
            if total_pages > 0 and cnt / total_pages >= 0.80 and ln
        }

        for page_num, text in enumerate(raw_texts, start=1):
            filtered_lines = [
                ln
                for ln in text.splitlines()
                if ln.strip() not in header_footer_lines
            ]
            cleaned = _clean_text("\n".join(filtered_lines))
            if cleaned:
                raw_pages.append(
                    RawPage(
                        text=cleaned,
                        page_number=page_num,
                        source_path=abs_path,
                    )
                )
            else:
                # Keep empty pages as a placeholder so page_number stays accurate
                raw_pages.append(
                    RawPage(text="", page_number=page_num, source_path=abs_path)
                )

    logger.debug("load_pdf: %s → %d pages", path, len(raw_pages))
    return raw_pages


# ---------------------------------------------------------------------------
# HTML loader  (TASK-007)
# ---------------------------------------------------------------------------


def load_html(path: str) -> list[RawPage]:
    """Parse an HTML file and return a single RawPage with body text only.

    Navigation, header, footer, script, and style elements are removed before
    conversion so the resulting text contains only the main body content.
    """
    abs_path = str(Path(path).resolve())

    with open(abs_path, encoding="utf-8", errors="replace") as fh:
        raw_html = fh.read()

    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove boilerplate tags
    for tag in soup.find_all(["nav", "header", "footer", "script", "style", "aside"]):
        tag.decompose()

    # Convert to plain text using html2text (preserves heading hierarchy)
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.body_width = 0  # no line wrapping

    body = soup.find("body")
    html_fragment = str(body) if body else str(soup)
    text = converter.handle(html_fragment)
    cleaned = _clean_text(text)

    logger.debug("load_html: %s → 1 page", path)
    return [RawPage(text=cleaned, page_number=0, source_path=abs_path)]


# ---------------------------------------------------------------------------
# Plain-text / Markdown loader  (TASK-008)
# ---------------------------------------------------------------------------

_PAGE_BREAK_RE = re.compile(r"\f|^---\s*$", re.MULTILINE)


def load_text(path: str) -> list[RawPage]:
    """Parse a plain-text or Markdown file and return one or more RawPages.

    Splits on form-feed characters (\\f) or lines containing only ``---``.
    If neither is present, returns the whole file as a single RawPage.
    """
    abs_path = str(Path(path).resolve())

    with open(abs_path, encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    sections = _PAGE_BREAK_RE.split(content)
    pages: list[RawPage] = []

    for page_num, section in enumerate(sections, start=1):
        cleaned = _clean_text(section)
        if cleaned:
            pages.append(
                RawPage(text=cleaned, page_number=page_num, source_path=abs_path)
            )

    if not pages:
        pages.append(RawPage(text="", page_number=1, source_path=abs_path))

    logger.debug("load_text: %s → %d page(s)", path, len(pages))
    return pages


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_EXTENSION_MAP: dict[str, object] = {
    ".pdf": load_pdf,
    ".html": load_html,
    ".htm": load_html,
    ".txt": load_text,
    ".md": load_text,
}

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(_EXTENSION_MAP.keys())


def load_document(path: str) -> list[RawPage]:
    """Dispatch to the correct loader based on file extension.

    Raises:
        ValueError: if the file extension is not supported.
    """
    ext = Path(path).suffix.lower()
    loader = _EXTENSION_MAP.get(ext)
    if loader is None:
        raise ValueError(
            f"Unsupported file type {ext!r}. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )
    return loader(path)  # type: ignore[operator]
