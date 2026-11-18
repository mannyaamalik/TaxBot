"""POST /ingest — document ingestion endpoint (authenticated)."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, status

from api.auth import require_ingest_token
from api.schemas import IngestResponse
from exceptions import UnsupportedFileTypeError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])

_SUPPORTED_EXTENSIONS = frozenset({".pdf", ".html", ".htm", ".txt", ".md"})
_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB


def _run_ingest(
    job_id: str,
    tmp_path: str,
    filename: str,
    jobs: dict,
    app_state,
) -> None:
    """Background task: run the ingestion pipeline and update job registry."""
    jobs[job_id]["status"] = "running"
    try:
        from ingestion.pipeline import ingest_file

        result = ingest_file(tmp_path, app_state.embedder, app_state.store)
        jobs[job_id].update(
            status="done",
            chunks_added=result.chunks_added,
        )
        logger.info(
            "Ingestion done job_id=%s filename=%s chunks=%d",
            job_id,
            filename,
            result.chunks_added,
        )
    except Exception as exc:
        jobs[job_id].update(status="failed", error=str(exc))
        logger.error("Ingestion failed job_id=%s error=%s", job_id, exc)
    finally:
        # Clean up the temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a document into the knowledge base",
    dependencies=[Depends(require_ingest_token)],
)
async def ingest(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile,
) -> IngestResponse:
    """Upload and ingest a document (PDF, HTML, TXT, MD).

    Requires ``Authorization: Bearer <INGEST_API_KEY>`` header.
    The ingestion runs asynchronously; poll ``GET /ingest/{job_id}`` for status.
    """
    state = request.app.state

    # ── Validate extension ────────────────────────────────────────────────
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type {ext!r} is not supported. Supported: {sorted(_SUPPORTED_EXTENSIONS)}",
        )

    # ── Read and size-check ───────────────────────────────────────────────
    content = await file.read()
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the 50 MB limit ({len(content) // (1024*1024)} MB uploaded).",
        )

    # ── Write to temp file ────────────────────────────────────────────────
    suffix = ext
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    # ── Register job ──────────────────────────────────────────────────────
    job_id = str(uuid.uuid4())
    state.ingest_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "filename": filename,
        "chunks_added": None,
        "error": None,
    }

    # ── Enqueue background task ───────────────────────────────────────────
    background_tasks.add_task(
        _run_ingest, job_id, tmp_path, filename, state.ingest_jobs, state
    )

    logger.info("Queued ingestion job_id=%s filename=%s", job_id, filename)

    return IngestResponse(
        job_id=job_id,
        status="queued",
        filename=filename,
    )


@router.get(
    "/ingest/{job_id}",
    response_model=IngestResponse,
    summary="Check ingestion job status",
    dependencies=[Depends(require_ingest_token)],
)
async def ingest_status(request: Request, job_id: str) -> IngestResponse:
    """Return the current status of an ingestion job."""
    state = request.app.state
    job = state.ingest_jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id!r} not found.",
        )
    return IngestResponse(**job)
