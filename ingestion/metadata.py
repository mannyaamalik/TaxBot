"""Metadata extraction for ingested documents.

Heuristically derives document-level metadata (title, assessment year,
document type) from raw page content, then overlays values from an optional
YAML sidecar file with the same stem as the source document.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ingestion.loader import RawPage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DocMetadata:
    """Document-level metadata attached to every chunk produced from this file."""

    doc_id: str           # SHA-256 hex of file bytes
    filename: str         # basename of source file
    doc_title: str        # human-readable title
    assessment_year: str  # e.g. "2024-25" or "unknown"
    doc_type: str         # act | circular | notification | faq | form | other
    ingested_at: str      # ISO-8601 UTC timestamp
    source_url: str = ""  # optional; populated from sidecar


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

# Matches patterns like "2024-25", "2024-2025" near AY / Assessment Year
_AY_RE = re.compile(
    r"(?:assessment\s+year|a\.?y\.?)[^\d]{0,10}(\d{4}[-–]\d{2,4})",
    re.IGNORECASE,
)

# Fallback: bare four-digit-dash-two-digit pattern anywhere in the first 500 chars
_AY_BARE_RE = re.compile(r"\b(\d{4}[-–]\d{2})\b")

_DOC_TYPE_KEYWORDS: dict[str, list[str]] = {
    "act": ["income tax act", "cgst act", "igst act", "finance act", "gst act"],
    "circular": ["circular no", "circular no.", "cbdt circular", "cbic circular"],
    "notification": ["notification no", "s.o.", "g.s.r.", "gazette notification"],
    "faq": ["frequently asked questions", "faqs", "faq"],
    "form": ["form itr", "form 16", "form 26as", "form gstr", "instruction booklet"],
}


def _infer_assessment_year(text: str) -> str:
    """Extract assessment year from text, normalising the separator to '-'."""
    sample = text[:500]
    m = _AY_RE.search(sample)
    if m:
        return m.group(1).replace("–", "-")
    m = _AY_BARE_RE.search(sample)
    if m:
        return m.group(1)
    return "unknown"


def _infer_doc_type(text: str) -> str:
    """Classify document type by keyword matching against the first 1,000 chars."""
    lower = text[:1000].lower()
    for doc_type, keywords in _DOC_TYPE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return doc_type
    return "other"


def _infer_title(raw_pages: list[RawPage]) -> str:
    """Return the first non-blank, non-trivially-short line of page 1."""
    if not raw_pages:
        return ""
    for line in raw_pages[0].text.splitlines():
        stripped = line.strip()
        if len(stripped) >= 5:
            return stripped
    return ""


def _sha256_of_file(path: str) -> str:
    """Compute SHA-256 hex digest of a file's raw bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Sidecar loader
# ---------------------------------------------------------------------------


def _load_sidecar(source_path: str) -> dict[str, Any]:
    """Read a YAML sidecar file (same stem, .yaml extension) if it exists."""
    sidecar_path = Path(source_path).with_suffix(".yaml")
    if not sidecar_path.exists():
        return {}
    try:
        with open(sidecar_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if isinstance(data, dict):
            logger.debug("Loaded sidecar: %s", sidecar_path)
            return data
    except Exception as exc:
        logger.warning("Failed to parse sidecar %s: %s", sidecar_path, exc)
    return {}


# ---------------------------------------------------------------------------
# Public API  (TASK-009)
# ---------------------------------------------------------------------------


def extract_metadata(raw_pages: list[RawPage], source_path: str) -> DocMetadata:
    """Extract document-level metadata from raw pages and optional sidecar.

    Heuristic values are computed first; a YAML sidecar with the same stem
    as *source_path* (e.g. ``IT_Act_AY2024-25.yaml``) can override any field.

    Args:
        raw_pages: Pages returned by one of the loaders in ``ingestion.loader``.
        source_path: Absolute path to the source document.

    Returns:
        A ``DocMetadata`` instance populated with all available metadata.
    """
    full_text = "\n".join(p.text for p in raw_pages)

    doc_id = _sha256_of_file(source_path)
    filename = os.path.basename(source_path)
    doc_title = _infer_title(raw_pages) or Path(source_path).stem
    assessment_year = _infer_assessment_year(full_text)
    doc_type = _infer_doc_type(full_text)
    ingested_at = datetime.now(tz=timezone.utc).isoformat()

    # Overlay with sidecar values
    sidecar = _load_sidecar(source_path)
    if sidecar.get("doc_title"):
        doc_title = str(sidecar["doc_title"])
    if sidecar.get("assessment_year"):
        assessment_year = str(sidecar["assessment_year"])
    if sidecar.get("doc_type"):
        doc_type = str(sidecar["doc_type"])
    source_url = str(sidecar.get("source_url", ""))

    meta = DocMetadata(
        doc_id=doc_id,
        filename=filename,
        doc_title=doc_title,
        assessment_year=assessment_year,
        doc_type=doc_type,
        ingested_at=ingested_at,
        source_url=source_url,
    )
    logger.debug(
        "Metadata for %s: title=%r ay=%s type=%s",
        filename,
        meta.doc_title,
        meta.assessment_year,
        meta.doc_type,
    )
    return meta
