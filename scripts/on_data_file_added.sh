#!/usr/bin/env bash
# on_data_file_added.sh
#
# Kiro PostFileCreate hook — fires whenever a file is created anywhere
# under the workspace.  The hook JSON constrains it to data/** via the
# matcher, so this script only receives events for the data/ tree.
#
# Flow:
#   1. Parse the new file path from the JSON payload on stdin.
#   2. Reject unsupported extensions and non-document files (YAML sidecars, etc.).
#   3. Ingest the single new file into ChromaDB.
#   4. If a live TaxBot server is reachable, run the evaluation suite.
#   5. Append a timestamped entry to data/ingest.log.
#   6. Exit 0 always — hook failures must never block the user.
#
# Configurable via environment variables (all optional):
#   TAXBOT_ROOT    Project root (default: parent of this script's directory)
#   TAXBOT_SERVER  Server URL for /chat evaluation (default: http://localhost:8000)
#   TAXBOT_PYTHON  Python interpreter (default: python3)
#   TAXBOT_EVAL    Set to "0" to skip evaluation after ingestion (default: "1")
#   TAXBOT_LOG     Ingest log file path (default: $TAXBOT_ROOT/data/ingest.log)

set -uo pipefail

# ── Resolve paths ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAXBOT_ROOT="${TAXBOT_ROOT:-$(dirname "$SCRIPT_DIR")}"
TAXBOT_SERVER="${TAXBOT_SERVER:-http://localhost:8000}"
TAXBOT_PYTHON="${TAXBOT_PYTHON:-python3}"
TAXBOT_EVAL="${TAXBOT_EVAL:-1}"
TAXBOT_LOG="${TAXBOT_LOG:-$TAXBOT_ROOT/data/ingest.log}"

# Supported extensions — must match ingestion/loader.py SUPPORTED_EXTENSIONS
SUPPORTED_EXTS=("pdf" "html" "htm" "txt" "md")

# ── Logging ────────────────────────────────────────────────────────────────
mkdir -p "$(dirname "$TAXBOT_LOG")"

ts() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
log()  { echo "[$(ts)] $*" | tee -a "$TAXBOT_LOG"; }
info() { log "INFO  $*"; }
warn() { log "WARN  $*"; }
err()  { log "ERROR $*" >&2; }

# ── Parse file path from stdin JSON payload ────────────────────────────────
# Kiro delivers: {"filePath": "/abs/path/to/file", ...}
# We write the payload to a temp file so Python can read it cleanly.
PAYLOAD_FILE="$(mktemp)"
cat > "$PAYLOAD_FILE"

NEW_FILE="$("$TAXBOT_PYTHON" - "$PAYLOAD_FILE" <<'PYEOF'
import json, sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    # Accept both camelCase and snake_case key variants
    path = (data.get("filePath")
            or data.get("file_path")
            or "")
    print(path)
except Exception as e:
    import sys as _sys
    print(f"parse error: {e}", file=_sys.stderr)
    print("")
PYEOF
)"
rm -f "$PAYLOAD_FILE"

if [[ -z "$NEW_FILE" ]]; then
    warn "Could not extract filePath from hook payload — skipping."
    exit 0
fi

# Resolve to absolute path if relative
if [[ "$NEW_FILE" != /* ]]; then
    NEW_FILE="$TAXBOT_ROOT/$NEW_FILE"
fi

info "Hook fired for: $NEW_FILE"

# ── Guard: must be under data/ ─────────────────────────────────────────────
DATA_DIR="$TAXBOT_ROOT/data"
# Use Python for portable path normalisation (handles Windows/WSL paths)
IS_UNDER_DATA="$("$TAXBOT_PYTHON" - "$NEW_FILE" "$DATA_DIR" <<'PYEOF'
import sys
from pathlib import Path
try:
    target = Path(sys.argv[1]).resolve()
    data   = Path(sys.argv[2]).resolve()
    print("1" if str(target).startswith(str(data)) else "0")
except Exception:
    print("0")
PYEOF
)"

if [[ "$IS_UNDER_DATA" != "1" ]]; then
    info "File is not under data/ — skipping. ($NEW_FILE)"
    exit 0
fi

# ── Guard: file exists and is non-empty ───────────────────────────────────
if [[ ! -f "$NEW_FILE" ]]; then
    warn "File does not exist: $NEW_FILE — skipping."
    exit 0
fi
if [[ ! -s "$NEW_FILE" ]]; then
    warn "File is empty: $NEW_FILE — skipping."
    exit 0
fi

# ── Guard: supported extension ────────────────────────────────────────────
EXT="${NEW_FILE##*.}"
EXT="${EXT,,}"  # lowercase

IS_SUPPORTED=0
for supported in "${SUPPORTED_EXTS[@]}"; do
    if [[ "$EXT" == "$supported" ]]; then
        IS_SUPPORTED=1
        break
    fi
done

if [[ "$IS_SUPPORTED" -eq 0 ]]; then
    info "Extension .$EXT not supported (${SUPPORTED_EXTS[*]}) — skipping."
    exit 0
fi

# ── Step 1: Ingest the new file ────────────────────────────────────────────
BASENAME="$(basename "$NEW_FILE")"
info "Starting ingestion: $BASENAME"

INGEST_OUTPUT=""
INGEST_EXIT=0
INGEST_OUTPUT="$(
    cd "$TAXBOT_ROOT"
    "$TAXBOT_PYTHON" scripts/ingest_bulk.py --file "$NEW_FILE" 2>&1
)" || INGEST_EXIT=$?

# Log ingestion output line by line
while IFS= read -r line; do
    info "  INGEST | $line"
done <<< "$INGEST_OUTPUT"

if [[ "$INGEST_EXIT" -ne 0 ]]; then
    err "Ingestion FAILED for $BASENAME (exit $INGEST_EXIT)."
    err "Skipping evaluation — KB may be inconsistent."
    err "To retry: cd $TAXBOT_ROOT && $TAXBOT_PYTHON scripts/ingest_bulk.py --file \"$NEW_FILE\""
    exit 0  # exit 0: don't block the user
fi

info "Ingestion OK: $BASENAME"

# ── Step 2: Check server reachability ────────────────────────────────────
if [[ "$TAXBOT_EVAL" != "1" ]]; then
    info "TAXBOT_EVAL=0 — skipping evaluation."
    exit 0
fi

SERVER_UP="$("$TAXBOT_PYTHON" - "$TAXBOT_SERVER" <<'PYEOF'
import sys, urllib.request
try:
    urllib.request.urlopen(sys.argv[1] + "/health", timeout=4)
    print("1")
except Exception:
    print("0")
PYEOF
)"

if [[ "$SERVER_UP" != "1" ]]; then
    info "Server not reachable at $TAXBOT_SERVER — skipping evaluation."
    info "Start the server, then run: cd $TAXBOT_ROOT && $TAXBOT_PYTHON scripts/evaluate.py"
    exit 0
fi

# ── Step 3: Run the evaluation suite ─────────────────────────────────────
TIMESTAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
EVAL_REPORT="$TAXBOT_ROOT/data/eval_${TIMESTAMP}.json"

info "Server reachable. Running evaluation suite…"

EVAL_OUTPUT=""
EVAL_EXIT=0
EVAL_OUTPUT="$(
    cd "$TAXBOT_ROOT"
    "$TAXBOT_PYTHON" scripts/evaluate.py \
        --url "$TAXBOT_SERVER" \
        --no-color \
        --output "$EVAL_REPORT" 2>&1
)" || EVAL_EXIT=$?

# Log evaluation output
while IFS= read -r line; do
    info "  EVAL   | $line"
done <<< "$EVAL_OUTPUT"

if [[ "$EVAL_EXIT" -eq 0 ]]; then
    info "Evaluation PASSED. Full report: $EVAL_REPORT"
else
    warn "Evaluation reported failures (exit $EVAL_EXIT)."
    warn "Full report: $EVAL_REPORT"
    warn "Review failures with:"
    warn "  cd $TAXBOT_ROOT && $TAXBOT_PYTHON scripts/evaluate.py --verbose"
    warn "Common fixes:"
    warn "  • Missing keywords → check that the PDF for this topic is in data/"
    warn "  • No citations    → lower SIMILARITY_THRESHOLD in .env"
    warn "  • Refusal failure → strengthen RULE 4 in generation/prompt.py"
fi

info "Hook complete for: $BASENAME"
exit 0
