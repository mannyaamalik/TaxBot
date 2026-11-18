"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from api.schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["ops"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health(request: Request) -> HealthResponse:
    """Always returns 200 OK with current KB and session counters.

    Suitable for load-balancer health checks that should never fail.
    """
    state = request.app.state
    total_chunks: int = 0
    if hasattr(state, "store"):
        try:
            total_chunks = state.store.count()
        except Exception:
            pass

    active_jobs: int = 0
    if hasattr(state, "ingest_jobs"):
        active_jobs = sum(
            1 for j in state.ingest_jobs.values() if j["status"] == "running"
        )

    active_sessions: int = 0
    if hasattr(state, "session_store"):
        active_sessions = state.session_store.active_count

    return HealthResponse(
        total_chunks=total_chunks,
        active_ingest_jobs=active_jobs,
        active_sessions=active_sessions,
    )


@router.get("/ready", summary="Readiness check")
async def ready(request: Request, response: Response) -> ReadyResponse:
    """Returns 200 when all singletons are initialised; 503 until then.

    Use this endpoint for container HEALTHCHECK and load-balancer readiness.
    """
    state = request.app.state
    if not getattr(state, "_ready", False):
        response.status_code = 503
        return ReadyResponse(ready=False, reason="Application is still starting up.")
    return ReadyResponse(ready=True)
