"""In-memory session store for TaxBot.

Keeps conversation history per session in a process-level dict.
Sessions are evicted after ``settings.session_ttl_minutes`` of inactivity.
History is capped at ``settings.session_history_turns * 2`` turn objects
(each question+answer pair = 2 turns).

Usage::

    from session.store import session_store
    session = session_store.get_or_create(session_id)
    session_store.add_turn(session.session_id, "user", question)
    history = session_store.get_history(session.session_id)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Turn:
    """One message turn (user or assistant)."""

    role: str    # "user" | "assistant"
    content: str


@dataclass
class Session:
    session_id: str
    history: list[Turn] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    last_active: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class SessionStore:
    """Thread-safe (asyncio-safe) in-memory session store."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._max_turns: int = settings.session_history_turns * 2
        self._ttl: timedelta = timedelta(minutes=settings.session_ttl_minutes)

    # ── CRUD ─────────────────────────────────────────────────────────────

    def get_or_create(self, session_id: str | None) -> Session:
        """Return an existing session or create a new one.

        If *session_id* is ``None`` or unknown, a fresh session is created
        with a new UUID.
        """
        sid = session_id or str(uuid.uuid4())
        if sid not in self._sessions:
            self._sessions[sid] = Session(session_id=sid)
            logger.debug("Created session %s", sid)
        session = self._sessions[sid]
        session.last_active = datetime.now(tz=timezone.utc)
        return session

    def add_turn(self, session_id: str, role: str, content: str) -> None:
        """Append a turn to the session, pruning to the history cap."""
        session = self._sessions.get(session_id)
        if session is None:
            logger.warning("add_turn called for unknown session %s", session_id)
            return
        session.history.append(Turn(role=role, content=content))
        # Keep only the most recent cap turns
        if len(session.history) > self._max_turns:
            session.history = session.history[-self._max_turns:]
        session.last_active = datetime.now(tz=timezone.utc)

    def get_history(self, session_id: str) -> list[Turn]:
        """Return the conversation history for *session_id* (empty list if unknown)."""
        session = self._sessions.get(session_id)
        if session is None:
            return []
        session.last_active = datetime.now(tz=timezone.utc)
        return list(session.history)

    # ── Eviction ─────────────────────────────────────────────────────────

    def cleanup_expired(self) -> int:
        """Remove sessions idle longer than the TTL. Returns count removed."""
        now = datetime.now(tz=timezone.utc)
        expired = [
            sid
            for sid, s in self._sessions.items()
            if (now - s.last_active) > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info("Evicted %d expired session(s).", len(expired))
        return len(expired)

    @property
    def active_count(self) -> int:
        return len(self._sessions)


# ── Singleton ──────────────────────────────────────────────────────────────
session_store = SessionStore()


# ── Background cleanup task ───────────────────────────────────────────────

async def _cleanup_loop() -> None:
    """Run session eviction every 5 minutes indefinitely."""
    while True:
        await asyncio.sleep(300)
        try:
            session_store.cleanup_expired()
        except Exception:
            logger.exception("Error during session cleanup")


async def start_cleanup_task() -> asyncio.Task[None]:  # type: ignore[type-arg]
    """Schedule the background cleanup loop and return the task handle."""
    return asyncio.create_task(_cleanup_loop(), name="session-cleanup")
