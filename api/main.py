"""TaxBot FastAPI application.

Lifespan:
  On startup: initialise embedder, vector store, LLM client singletons,
              start session-eviction background task, mark app as ready.
  On shutdown: cancel background task.

Middleware stack (request order):
  1. CORS
  2. Request-ID injection
  3. slowapi rate-limit state
  4. Request body size limit (64 KB)

Routers:
  /health, /ready   — ops
  /chat             — main RAG endpoint
  /ingest, /ingest/{id} — document ingestion (authenticated)
  /analytics, /feedback — usage counters
  /                 — serves ui/index.html
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from slowapi import _rate_limit_exceeded_handler  # type: ignore[attr-defined]
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.analytics import analytics  # noqa: F401 — imported to initialise
from api.rate_limit import limiter
from api.routers import analytics as analytics_router
from api.routers import chat as chat_router
from api.routers import health as health_router
from api.routers import ingest as ingest_router
from config import settings
from exceptions import TaxBotError
from session.store import SessionStore, start_cleanup_task

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional: JSON structured logging via python-json-logger
# ---------------------------------------------------------------------------

def _configure_json_logging() -> None:
    """Switch root logger to JSON format if python-json-logger is installed."""
    try:
        from pythonjsonlogger import jsonlogger  # type: ignore[import]

        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        handler.setFormatter(formatter)
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
        logger.info("JSON logging enabled.")
    except ImportError:
        logger.debug("python-json-logger not installed — using text logging.")


# ---------------------------------------------------------------------------
# Optional: Sentry
# ---------------------------------------------------------------------------

def _init_sentry() -> None:
    sentry_dsn = os.getenv("SENTRY_DSN", "")
    if not sentry_dsn:
        return
    try:
        import sentry_sdk  # type: ignore[import]
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=sentry_dsn,
            traces_sample_rate=0.1,
            integrations=[StarletteIntegration(), FastApiIntegration()],
            send_default_pii=False,  # never send PII
        )
        logger.info("Sentry initialised.")
    except ImportError:
        logger.warning("sentry-sdk not installed — error tracking disabled.")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise and tear down long-lived resources."""
    # ── Logging and monitoring ────────────────────────────────────────────
    _configure_json_logging()
    _init_sentry()

    # ── Singletons ────────────────────────────────────────────────────────
    logger.info("Initialising embedder…")
    from retrieval.embedder import get_embedder
    app.state.embedder = get_embedder()

    logger.info("Initialising vector store at %s…", settings.chroma_db_path)
    from retrieval.store import VectorStore
    app.state.store = VectorStore()

    logger.info("Initialising LLM client (provider=%s)…", settings.llm_provider)
    from generation.llm import get_llm_client
    app.state.llm_client = get_llm_client()

    # ── Session store ─────────────────────────────────────────────────────
    app.state.session_store = SessionStore()
    app.state._cleanup_task = await start_cleanup_task()

    # ── Ingest job registry ───────────────────────────────────────────────
    app.state.ingest_jobs: dict = {}

    # ── Mark ready ────────────────────────────────────────────────────────
    app.state._ready = True
    logger.info(
        "TaxBot ready: %d chunks in KB.",
        app.state.store.count(),
    )

    yield  # ── Application runs ──────────────────────────────────────────

    # ── Shutdown ──────────────────────────────────────────────────────────
    app.state._cleanup_task.cancel()
    logger.info("TaxBot shut down cleanly.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="TaxBot API",
        description="RAG-powered Indian Income Tax & GST assistant.",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── Rate limiter ──────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # ── CORS ──────────────────────────────────────────────────────────────
    allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
    allowed_origins = (
        ["*"] if allowed_origins_raw == "*"
        else [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # ── Request-ID middleware ─────────────────────────────────────────────
    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # ── Request body size limit (64 KB for /chat; /ingest has its own check) ──
    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        # Skip size limit for /ingest (it checks file size itself)
        if request.url.path.startswith("/ingest"):
            return await call_next(request)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 64 * 1024:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large (max 64 KB)."},
            )
        return await call_next(request)

    # ── Global domain error handler ───────────────────────────────────────
    @app.exception_handler(TaxBotError)
    async def taxbot_error_handler(request: Request, exc: TaxBotError):
        logger.error("TaxBotError: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal error: {type(exc).__name__}"},
        )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(health_router.router)
    app.include_router(chat_router.router)
    app.include_router(ingest_router.router)
    app.include_router(analytics_router.router)

    # ── Serve legacy vanilla UI at / ─────────────────────────────────────
    _ui_path = Path(__file__).parent.parent / "ui" / "index.html"

    @app.get("/", include_in_schema=False)
    async def serve_ui():
        if _ui_path.exists():
            return FileResponse(str(_ui_path))
        return JSONResponse({"message": "TaxBot API — see /docs"})

    return app


# ── WSGI/ASGI entrypoint ──────────────────────────────────────────────────
app = create_app()
