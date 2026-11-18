#!/usr/bin/env python3
"""Scheduled knowledge-base update script.

Intended to run as a cron job (Render Cron Job, GitHub Actions scheduled
workflow, or any task scheduler) after each Union Budget or financial-year
change.

Usage:
    python3 scripts/scheduled_kb_update.py \\
        --dir docs/raw/AY2025-26/ \\
        --server http://localhost:8000

Environment variables:
    KB_UPDATE_DIR       — directory of new/updated documents (overrides --dir)
    TAXBOT_SERVER       — backend server URL for smoke test and /chat calls
    NOTIFY_WEBHOOK_URL  — Slack/Discord webhook URL for notifications
    PYTHONPATH          — must include the project root

Exit codes:
    0 — all documents ingested and smoke test passed
    1 — one or more documents failed, or smoke test failed
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Paths / defaults
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SERVER = os.getenv("TAXBOT_SERVER", "http://localhost:8000")
DEFAULT_UPDATE_DIR = os.getenv("KB_UPDATE_DIR", str(PROJECT_ROOT / "docs" / "raw"))
NOTIFY_URL = os.getenv("NOTIFY_WEBHOOK_URL", "")
INGEST_API_KEY = os.getenv("INGEST_API_KEY", "")

SUPPORTED_EXTENSIONS = frozenset({".pdf", ".html", ".htm", ".txt", ".md"})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _notify(message: str) -> None:
    """POST a plain-text message to a Slack/Discord webhook (best-effort)."""
    if not NOTIFY_URL:
        return
    try:
        httpx.post(NOTIFY_URL, json={"text": message}, timeout=10)
    except Exception as exc:
        logger.warning("Failed to send notification: %s", exc)


def _ingest_via_api(server: str, file_path: Path) -> dict:
    """Upload a file to POST /ingest and poll until done.

    Returns the final job status dict.
    Raises RuntimeError if ingestion fails or takes too long.
    """
    if not INGEST_API_KEY:
        raise RuntimeError("INGEST_API_KEY is not set — cannot call /ingest.")

    with file_path.open("rb") as fh:
        response = httpx.post(
            f"{server}/ingest",
            headers={"Authorization": f"Bearer {INGEST_API_KEY}"},
            files={"file": (file_path.name, fh)},
            timeout=30,
        )
    response.raise_for_status()
    job = response.json()
    job_id: str = job["job_id"]

    # Poll for completion
    for _ in range(60):  # up to 5 minutes
        time.sleep(5)
        status_resp = httpx.get(
            f"{server}/ingest/{job_id}",
            headers={"Authorization": f"Bearer {INGEST_API_KEY}"},
            timeout=10,
        )
        status_resp.raise_for_status()
        status = status_resp.json()
        if status["status"] == "done":
            return status
        if status["status"] == "failed":
            raise RuntimeError(f"Ingestion failed: {status.get('error', 'unknown error')}")

    raise RuntimeError(f"Ingestion timed out for {file_path.name}")


def _run_smoke_test(server: str) -> bool:
    """Run a minimal smoke test against the live server.

    Returns True if the server responds correctly, False otherwise.
    """
    smoke_questions = [
        "What is the Section 80C deduction limit?",
        "What is the GST registration threshold for services?",
    ]
    all_ok = True
    for question in smoke_questions:
        try:
            resp = httpx.post(
                f"{server}/chat",
                json={"question": question, "session_id": None},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("answer"):
                logger.warning("Smoke test: empty answer for %r", question)
                all_ok = False
            else:
                logger.info("Smoke test OK: %r → %d chars", question, len(data["answer"]))
        except Exception as exc:
            logger.error("Smoke test failed for %r: %s", question, exc)
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Scheduled TaxBot KB update")
    parser.add_argument("--dir",    default=DEFAULT_UPDATE_DIR, help="Directory of documents to ingest")
    parser.add_argument("--server", default=DEFAULT_SERVER,     help="Backend server URL")
    parser.add_argument("--dry-run", action="store_true",       help="Print actions without ingesting")
    parser.add_argument("--skip-smoke", action="store_true",    help="Skip smoke test after ingestion")
    args = parser.parse_args()

    update_dir = Path(args.dir)
    server: str = args.server.rstrip("/")

    if not update_dir.exists():
        logger.error("Update directory does not exist: %s", update_dir)
        return 1

    # Discover documents
    files = [
        f for f in update_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        logger.warning("No supported documents found in %s — nothing to do.", update_dir)
        return 0

    logger.info("Found %d document(s) to ingest from %s", len(files), update_dir)

    if args.dry_run:
        for f in files:
            logger.info("  [dry-run] Would ingest: %s", f.name)
        return 0

    # Ingest each file
    results: list[dict] = []
    failures: list[str] = []

    for file_path in sorted(files):
        logger.info("Ingesting %s …", file_path.name)
        try:
            job = _ingest_via_api(server, file_path)
            logger.info("  ✓ %s — %d chunks added", file_path.name, job.get("chunks_added", "?"))
            results.append({"file": file_path.name, "status": "done", "chunks": job.get("chunks_added")})
        except Exception as exc:
            logger.error("  ✗ %s — %s", file_path.name, exc)
            failures.append(file_path.name)
            results.append({"file": file_path.name, "status": "failed", "error": str(exc)})

    # Smoke test
    smoke_ok = True
    if not args.skip_smoke:
        logger.info("Running smoke test against %s …", server)
        smoke_ok = _run_smoke_test(server)

    # Summary
    total   = len(files)
    success = total - len(failures)
    summary = (
        f"TaxBot KB update: {success}/{total} documents ingested successfully. "
        f"Smoke test: {'PASS' if smoke_ok else 'FAIL'}. "
        f"Failures: {failures or 'none'}."
    )
    logger.info(summary)
    _notify(("✅ " if not failures and smoke_ok else "❌ ") + summary)

    # Write JSON report
    report_path = Path("kb_update_report.json")
    report_path.write_text(json.dumps({"results": results, "smoke_ok": smoke_ok}, indent=2))
    logger.info("Report written to %s", report_path)

    return 0 if (not failures and smoke_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
