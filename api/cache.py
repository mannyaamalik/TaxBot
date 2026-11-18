"""Response cache for repeated /chat questions.

A simple in-memory LRU cache keyed by SHA-256(normalised_question).
TTL eviction is handled per-entry on access rather than by a background task,
keeping the implementation dependency-free.

Usage::

    from api.cache import response_cache
    hit = response_cache.get(question)
    if hit:
        return hit
    # ... generate answer ...
    response_cache.set(question, response)
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 300       # 5 minutes
_DEFAULT_MAX = 256       # maximum cached responses


@dataclass
class _Entry:
    value: Any
    expires_at: float


class ResponseCache:
    """Thread-safe (GIL-protected) LRU cache with per-entry TTL."""

    def __init__(self, maxsize: int = _DEFAULT_MAX, ttl_seconds: int = _DEFAULT_TTL) -> None:
        self._cache: OrderedDict[str, _Entry] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _key(question: str) -> str:
        normalised = question.strip().lower()
        return hashlib.sha256(normalised.encode()).hexdigest()

    def get(self, question: str) -> Any | None:
        key = self._key(question)
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        if time.monotonic() > entry.expires_at:
            del self._cache[key]
            self._misses += 1
            return None
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        logger.debug("Cache hit for question hash %s…", key[:12])
        return entry.value

    def set(self, question: str, value: Any) -> None:
        key = self._key(question)
        expires_at = time.monotonic() + self._ttl
        self._cache[key] = _Entry(value=value, expires_at=expires_at)
        self._cache.move_to_end(key)
        # Evict oldest if over capacity
        while len(self._cache) > self._maxsize:
            oldest_key, _ = next(iter(self._cache.items()))
            del self._cache[oldest_key]

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    def clear(self) -> None:
        self._cache.clear()


# ── Singleton ─────────────────────────────────────────────────────────────
response_cache = ResponseCache()
