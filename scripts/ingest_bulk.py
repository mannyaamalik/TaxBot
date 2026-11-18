"""Bulk document ingestion CLI script.

Recursively walks a directory (or ingests a single file) into ChromaDB.
Unsupported file types are warned about but do not stop the run.

Usage::

    python scripts/ingest_bulk.py --dir docs/raw/
    python scripts/ingest_bulk.py --dir docs/raw/AY2024-25/ --verbose
    python scripts/ingest_bulk.py --file docs/raw/AY2024-25/IT_Act.pdf

Exit codes:
    0 — all files processed (skipped files are not failures).
    1 — one or more files failed to ingest.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure the project root is on sys.path so imports resolve correctly
# when the script is run from any working directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import settings  # noqa: E402  (must come after sys.path setup)
from exceptions import IngestError, UnsupportedFileTypeError  # noqa: E402
from ingestion.loader import SUPPORTED_EXTENSIONS  # noqa: E402
from ingestion.pipeline import ingest_file  # noqa: E402
from retrieval.embedder import get_embedder  # noqa: E402
from retrieval.store import VectorStore  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_files(directory: Path) -> list[Path]:
    """Return all files with supported extensions under *directory*, sorted."""
    files: list[Path] = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(directory.rglob(f"*{ext}"))
    return sorted(set(files))  # deduplicate (rglob may return duplicates on some FS)


def _fmt_duration(seconds: float) -> str:
    """Format a duration in seconds as a human-readable string."""
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    return f"{seconds:.1f} s"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bulk-ingest documents from a directory (or a single file) into TaxBot's ChromaDB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--dir",
        metavar="PATH",
        help="Directory to scan recursively for supported documents.",
    )
    source.add_argument(
        "--file",
        metavar="PATH",
        help="Single file to ingest.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show DEBUG-level output.",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ── Initialise shared singletons ─────────────────────────────────────
    print(f"Loading embedding model ({settings.embed_model}) …")
    embedder = get_embedder()

    print(f"Opening vector store at {settings.chroma_db_path} …")
    store = VectorStore()

    # ── Single-file mode ──────────────────────────────────────────────────
    if args.file:
        file_path = Path(args.file).resolve()
        if not file_path.exists():
            print(f"ERROR: file not found: {file_path}", file=sys.stderr)
            return 1

        col = 50
        display = str(file_path)
        truncated = (display[:col - 1] + "…") if len(display) > col else display
        print(f"\n{'File':<{col}}  {'Chunks':>7}  {'Time':>8}  Status")
        print("-" * (col + 25))

        t0 = time.perf_counter()
        try:
            result = ingest_file(str(file_path), embedder, store)
            elapsed = time.perf_counter() - t0
            print(f"{truncated:<{col}}  {result.chunks_added:>7}  {_fmt_duration(elapsed):>8}  OK")
            print(f"\nKnowledge base now contains {store.count()} chunks.")
            return 0
        except UnsupportedFileTypeError as exc:
            elapsed = time.perf_counter() - t0
            print(f"{truncated:<{col}}  {'—':>7}  {_fmt_duration(elapsed):>8}  SKIP ({exc})")
            return 0
        except (IngestError, Exception) as exc:
            elapsed = time.perf_counter() - t0
            print(f"{truncated:<{col}}  {'—':>7}  {_fmt_duration(elapsed):>8}  FAIL", file=sys.stderr)
            logger.error("Ingestion error for %s: %s", file_path, exc)
            return 1

    # ── Directory mode ────────────────────────────────────────────────────
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        print(f"ERROR: {directory} is not a directory.", file=sys.stderr)
        return 1

    print(f"\nScanning: {directory}\n")
    all_files = _collect_files(directory)

    if not all_files:
        print("No supported files found.")
        return 0

    # ── Process files ─────────────────────────────────────────────────────
    total = len(all_files)
    succeeded = 0
    failed = 0
    skipped = 0

    # Header row
    col = 50
    print(f"{'File':<{col}}  {'Chunks':>7}  {'Time':>8}  Status")
    print("-" * (col + 25))

    for file_path in all_files:
        display = str(file_path.relative_to(directory))
        truncated = (display[:col - 1] + "…") if len(display) > col else display

        # Skip YAML sidecars — they are metadata, not documents
        if file_path.suffix.lower() == ".yaml":
            skipped += 1
            continue

        ext = file_path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            print(f"{truncated:<{col}}  {'—':>7}  {'—':>8}  SKIP (unsupported: {ext})")
            skipped += 1
            continue

        t0 = time.perf_counter()
        try:
            result = ingest_file(str(file_path), embedder, store)
            elapsed = time.perf_counter() - t0
            print(
                f"{truncated:<{col}}  {result.chunks_added:>7}  "
                f"{_fmt_duration(elapsed):>8}  OK"
            )
            succeeded += 1
        except UnsupportedFileTypeError as exc:
            elapsed = time.perf_counter() - t0
            print(f"{truncated:<{col}}  {'—':>7}  {_fmt_duration(elapsed):>8}  SKIP ({exc})")
            skipped += 1
        except IngestError as exc:
            elapsed = time.perf_counter() - t0
            print(
                f"{truncated:<{col}}  {'—':>7}  {_fmt_duration(elapsed):>8}  FAIL",
                file=sys.stderr,
            )
            logger.error("Ingestion error for %s: %s", file_path, exc)
            failed += 1
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(
                f"{truncated:<{col}}  {'—':>7}  {_fmt_duration(elapsed):>8}  FAIL",
                file=sys.stderr,
            )
            logger.exception("Unexpected error for %s: %s", file_path, exc)
            failed += 1

    # ── Summary ───────────────────────────────────────────────────────────
    print("-" * (col + 25))
    print(
        f"\nTotal: {total}   "
        f"OK: {succeeded}   "
        f"Skipped: {skipped}   "
        f"Failed: {failed}"
    )
    print(f"Knowledge base now contains {store.count()} chunks.")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
