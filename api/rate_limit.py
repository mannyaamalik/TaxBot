"""slowapi rate-limiter helpers."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from config import settings

limiter = Limiter(key_func=get_remote_address)

# Convenience string — used in route decorators
CHAT_LIMIT = f"{settings.rate_limit_per_minute}/minute"
ANALYTICS_LIMIT = "10/minute"
