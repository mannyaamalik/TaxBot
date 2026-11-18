"""Bearer-token authentication for the /ingest endpoint."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings

_bearer = HTTPBearer(auto_error=True)


def require_ingest_token(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> None:
    """Dependency that rejects requests without the correct ingest API key.

    Uses ``secrets.compare_digest`` to prevent timing attacks.
    Raises HTTP 401 if the key is missing, blank, or incorrect.
    """
    configured_key = settings.ingest_api_key
    if not configured_key or configured_key == "change-me-before-running":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingest API key is not configured on this server.",
        )
    provided = credentials.credentials
    if not secrets.compare_digest(provided, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing ingest API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
