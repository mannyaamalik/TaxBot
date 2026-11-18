"""Input sanitisation and prompt-injection guard for TaxBot.

Sanitisation is applied before the question reaches the RAG pipeline.
Any question that triggers the injection guard is rejected with HTTP 400
before the embedder or LLM are invoked.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Prompt-injection patterns
# ---------------------------------------------------------------------------
# These phrases commonly appear in attempts to override system prompts or
# exfiltrate instructions.  The guard is intentionally conservative — a
# legitimate tax question will never contain these exact phrases.

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions?", re.I),
    re.compile(r"you\s+are\s+now", re.I),
    re.compile(r"new\s+instructions?:", re.I),
    re.compile(r"system\s+prompt", re.I),
    re.compile(r"---\s*CONTEXT\s*---", re.I),
    re.compile(r"---\s*END\s+CONTEXT\s*---", re.I),
    re.compile(r"<\s*/?system\s*>", re.I),         # XML/HTML system tags
    re.compile(r"\bREVEAL\s+(?:YOUR\s+)?(?:RULES|INSTRUCTIONS|PROMPT)\b", re.I),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior)", re.I),
    re.compile(r"act\s+as\s+(?:a|an)\s+\w+\s+without\s+restrictions?", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"DAN\s+mode", re.I),
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sanitize_question(raw: str) -> str:
    """Clean and return the question, or raise ValueError if it is unsafe.

    Steps:
    1. Strip leading/trailing whitespace.
    2. Collapse internal runs of whitespace to single spaces.
    3. Check against injection patterns — raise ValueError if matched.

    Args:
        raw: The raw question string from the API request.

    Returns:
        The cleaned question string.

    Raises:
        ValueError: If an injection pattern is detected.
    """
    cleaned = raw.strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(cleaned):
            raise ValueError(
                f"Question contains a disallowed pattern: {pattern.pattern!r}"
            )

    return cleaned
