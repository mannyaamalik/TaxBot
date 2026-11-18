"""In-process analytics counters for TaxBot.

Counters reset on process restart. For persistent analytics, forward to an
external sink (Sentry, Datadog, etc.) — see docs/monitoring.md.

Usage::

    from api.analytics import analytics
    analytics.record_question(latency_ms=320, not_found=False)
    analytics.record_feedback("up")
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


@dataclass
class Analytics:
    questions_total: int = 0
    not_found_total: int = 0
    out_of_scope_total: int = 0
    cache_hits: int = 0
    feedback_up: int = 0
    feedback_down: int = 0
    _latencies: list[float] = field(default_factory=list)

    def record_question(
        self,
        latency_ms: float,
        not_found: bool = False,
        out_of_scope: bool = False,
        cache_hit: bool = False,
    ) -> None:
        self.questions_total += 1
        if not_found:
            self.not_found_total += 1
        if out_of_scope:
            self.out_of_scope_total += 1
        if cache_hit:
            self.cache_hits += 1
        # Keep at most 10 000 latency samples to bound memory
        if len(self._latencies) < 10_000:
            self._latencies.append(latency_ms)

    def record_feedback(self, fb: str) -> None:
        if fb == "up":
            self.feedback_up += 1
        elif fb == "down":
            self.feedback_down += 1

    @property
    def avg_latency_ms(self) -> float:
        return statistics.mean(self._latencies) if self._latencies else 0.0

    @property
    def p95_latency_ms(self) -> float:
        if not self._latencies:
            return 0.0
        sorted_lats = sorted(self._latencies)
        idx = int(len(sorted_lats) * 0.95)
        return sorted_lats[min(idx, len(sorted_lats) - 1)]


# ── Singleton ─────────────────────────────────────────────────────────────
analytics = Analytics()
