# TaxBot – Implementation Task List

> **References:** `requirements.md` · `design.md`
> **Convention:** Each task has a unique ID, a clear done-condition, and the
> file(s) it touches. Tasks within a phase are ordered so each one builds on
> the previous. Cross-phase dependencies are noted where they exist.

---

## Phase 1 — Project Setup

### TASK-001 · Initialise repository structure
**What:** Create the full directory skeleton from `design.md §2`.
**Files created:**
```
taxbot/
  ingestion/   retrieval/   generation/   api/routers/
  session/     ui/          scripts/      data/chromadb/   docs/raw/
  __init__.py files in every package directory
```
**Done when:** `find taxbot -name __init__.py | wc -l` returns ≥ 7 (one per package).

---

### TASK-002 · Create `requirements.txt`
**What:** Pin all direct dependencies with minimum versions.
```
fastapi>=0.111
uvicorn[standard]>=0.29
pydantic>=2.7
python-dotenv>=1.0
pdfplumber>=0.11
beautifulsoup4>=4.12
html2text>=2024.2
nltk>=3.8
sentence-transformers>=3.0
chromadb>=0.5
openai>=1.30          # used for both LLM and embedding API path
httpx>=0.27
slowapi>=0.1.9
python-multipart>=0.0.9
```
Dev/test extras (separate `requirements-dev.txt`):
```
pytest>=8.2
pytest-asyncio>=0.23
httpx>=0.27           # AsyncClient for API tests
```
**Done when:** `pip install -r requirements.txt` completes without error in a fresh virtualenv.

---

### TASK-003 · Create `.env.example`
**What:** Document every config variable from `design.md §10` with its default value and a one-line comment.
**File:** `taxbot/.env.example`
**Done when:** The file contains all 28 variables listed in the config reference table; no secrets are present (placeholder values only).

---

### TASK-004 · Implement `config.py`
**What:** A single `Settings` dataclass (or Pydantic `BaseSettings`) that reads all env vars, applies defaults, and is importable as a singleton.
**File:** `taxbot/config.py`
**Done when:** `from config import settings; assert settings.chunk_size == 512` passes when no `.env` is present.

---

### TASK-005 · Download NLTK punkt tokeniser data
**What:** Add a startup check in `config.py` (or a `setup.py` script) that calls `nltk.download("punkt", quiet=True)` so the chunker works without manual setup.
**Done when:** Running `python -c "import nltk; nltk.data.find('tokenizers/punkt')"` succeeds after project install.

---

## Phase 2 — Ingestion Pipeline

### TASK-006 · Implement PDF loader (`ingestion/loader.py`)
**What:** `load_pdf(path: str) -> list[RawPage]`
- Open with `pdfplumber`.
- Per page: extract text; extract tables as pipe-delimited rows appended to text.
- Strip running headers/footers (lines present on ≥ 80 % of pages).
- Return one `RawPage` per PDF page.
**Done when:** Running against a 10-page PDF returns exactly 10 `RawPage` objects, each with non-empty `text` and correct `page_number` (1-based).

---

### TASK-007 · Implement HTML loader (`ingestion/loader.py`)
**What:** `load_html(path: str) -> list[RawPage]`
- Parse with BeautifulSoup; remove `nav`, `header`, `footer`, `script`, `style`.
- Convert body to plain text via `html2text`.
- Return a single `RawPage` with `page_number=0`.
**Done when:** Loading a sample CBIC HTML page returns a `RawPage` whose text contains the main body content and no nav link text.

---

### TASK-008 · Implement plain-text / Markdown loader (`ingestion/loader.py`)
**What:** `load_text(path: str) -> list[RawPage]`
- Read file as UTF-8.
- Split on form-feed characters (`\f`) or `---` page-break markers if present; otherwise return as one page.
- Return `list[RawPage]` with incrementing `page_number`.
**Done when:** A `.md` file with no page-break markers returns exactly one `RawPage` containing the full file text.

---

### TASK-009 · Implement metadata extraction (`ingestion/metadata.py`)
**What:** `extract_metadata(raw_pages: list[RawPage], source_path: str) -> DocMetadata`
- Compute `doc_id` as SHA-256 of file bytes.
- Extract `doc_title` from first non-blank line of page 1 (or `<title>` tag for HTML).
- Extract `assessment_year` via regex on the first 500 characters.
- Classify `doc_type` via keyword matching.
- Read YAML sidecar file (`<same_stem>.yaml`) if present and override heuristic values.
**Done when:** Given a PDF whose first page starts with "Income Tax Act 1961" and whose sidecar sets `assessment_year: "2024-25"`, the returned `DocMetadata.assessment_year` equals `"2024-25"` and `doc_title` equals `"Income Tax Act 1961"`.

---

### TASK-010 · Implement chunker (`ingestion/chunker.py`)
**What:** `chunk_document(raw_pages: list[RawPage], meta: DocMetadata) -> list[Chunk]`
- Sentence-tokenise each page with `nltk.sent_tokenize`.
- Sliding window: accumulate sentences until `CHUNK_SIZE` tokens reached; emit chunk; step back `CHUNK_OVERLAP` tokens of sentences.
- Carry `section_heading` forward: if a sentence matches the heading heuristic, update the tracked heading.
- Assign `chunk_id = str(uuid4())`.
**Done when:**
  - A 1,000-token page with `CHUNK_SIZE=512, CHUNK_OVERLAP=64` produces 2–3 chunks.
  - Consecutive chunks share at least one sentence of overlap.
  - No chunk has zero-length text.

---

### TASK-011 · Write unit tests for chunker
**What:** `tests/test_chunker.py`
- Test overlap: last sentence of chunk N appears in chunk N+1.
- Test heading propagation: a heading line in the middle of a page sets `section_heading` on subsequent chunks.
- Test oversized sentence: a single sentence longer than `CHUNK_SIZE` is not dropped.
- Test empty input: `chunk_document([], meta)` returns `[]` without error.
**Done when:** `pytest tests/test_chunker.py` passes all 4 tests.

---

### TASK-012 · Implement ingestion pipeline orchestrator (`ingestion/pipeline.py`)
**What:** `ingest_file(path: str, embedder, collection) -> IngestResult`
- Dispatch to the correct loader based on file extension.
- Call `extract_metadata`, `chunk_document`.
- Delete existing chunks for the same `doc_id` from ChromaDB before adding new ones (upsert behaviour).
- Embed chunks in batches; add to collection.
- Return `IngestResult(doc_id, filename, chunks_added)`.
**Done when:** Ingesting the same PDF twice results in the same number of chunks in ChromaDB (not doubled).

---

### TASK-013 · Implement bulk ingest CLI script (`scripts/ingest_bulk.py`)
**What:** CLI that accepts `--dir PATH` and ingests every supported file found recursively.
- Print a per-file summary: filename, chunks added, time taken.
- Skip unsupported extensions with a warning (not an error).
**Done when:** Running against a directory of 3 PDFs prints 3 summary lines and exits 0.

---

## Phase 3 — Embedding and Vector Store

### TASK-014 · Implement local sentence-transformer embedder (`retrieval/embedder.py`)
**What:** `LocalEmbedder` class implementing `EmbedderProtocol`.
- Load model at construction time from `settings.embed_model`.
- `embed(texts: list[str]) -> list[list[float]]`: encode in batches of `settings.embed_batch_size`; L2-normalise each vector before returning.
**Done when:**
  - `len(embedder.embed(["test"])[0]) == 384` for the default model.
  - Two identical texts produce identical vectors.
  - Two semantically similar texts produce cosine similarity > 0.8.

---

### TASK-015 · Implement API embedder (`retrieval/embedder.py`)
**What:** `APIEmbedder` class implementing `EmbedderProtocol`.
- Call `POST /v1/embeddings` on `settings.openai_base_url` with the configured model.
- L2-normalise returned vectors.
- Raise `EmbedderError` on HTTP error; caller falls back to `LocalEmbedder`.
**Done when:** With `OPENAI_API_KEY` set and a valid endpoint, `APIEmbedder().embed(["hello"])` returns a non-empty vector list.

---

### TASK-016 · Implement embedder factory (`retrieval/embedder.py`)
**What:** `get_embedder() -> EmbedderProtocol`
- Return `APIEmbedder` if `settings.openai_api_key` is set, else `LocalEmbedder`.
- Instantiated once at app startup; stored as a module-level singleton.
**Done when:** Setting / unsetting `OPENAI_API_KEY` changes which class is returned, confirmed by `type(get_embedder()).__name__`.

---

### TASK-017 · Implement ChromaDB store wrapper (`retrieval/store.py`)
**What:** `VectorStore` class wrapping `chromadb.PersistentClient`.
- `upsert(chunks: list[Chunk])`: add documents with embeddings and metadata.
- `delete_by_doc_id(doc_id: str)`: delete all chunks whose metadata `doc_id` matches.
- `query(vector, n_results, where_filter) -> list[RawResult]`: return matching chunks with distances.
- `count() -> int`: return total number of stored chunks.
**Done when:**
  - `store.upsert([chunk])` followed by `store.count()` returns 1.
  - `store.delete_by_doc_id(chunk.metadata.doc_id)` followed by `store.count()` returns 0.
  - `store.query(vector, n_results=1)` returns a list with one `RawResult`.

---

### TASK-018 · Write unit tests for vector store
**What:** `tests/test_store.py`
- Use a temporary ChromaDB path (pytest `tmp_path` fixture).
- Test upsert → count.
- Test delete → count.
- Test query returns most-similar chunk from a set of 3 semantically distinct chunks.
**Done when:** `pytest tests/test_store.py` passes all 3 tests.

---

## Phase 4 — Retrieval

### TASK-019 · Implement bi-encoder retriever (`retrieval/retriever.py`)
**What:** `retrieve(question: str, embedder, store) -> list[RawResult]`
- Embed the question.
- Call `store.query(vector, n_results=settings.retrieval_top_k * 3)`.
- Convert ChromaDB distance to cosine similarity (`sim = 1 - distance`).
- Discard results with `sim < settings.similarity_threshold`.
- Return surviving `RawResult` list (may be empty).
**Done when:**
  - A question semantically matching an ingested chunk returns that chunk in results.
  - A gibberish question returns an empty list (assuming threshold is not met).

---

### TASK-020 · Implement cross-encoder reranker (`retrieval/reranker.py`)
**What:** `rerank(question: str, results: list[RawResult]) -> list[RetrievedChunk]`
- If `settings.reranker_enabled` is false, convert `RawResult` → `RetrievedChunk` using cosine score and return.
- Load `cross-encoder/ms-marco-MiniLM-L-6-v2` once at module level.
- Score each `(question, chunk_text)` pair.
- Sort descending by score; keep top `settings.retrieval_top_k`.
- Discard any with score < `settings.rerank_threshold`.
- Return `list[RetrievedChunk]`.
**Done when:**
  - Given 3 candidates, the most relevant one (verified manually) ranks first.
  - Setting `RERANKER_ENABLED=false` returns the same candidates unsorted by cross-encoder.

---

### TASK-021 · Write integration test for end-to-end retrieval
**What:** `tests/test_retrieval.py`
- Ingest a small synthetic document (3 paragraphs on distinct topics).
- Query with a question relevant to paragraph 2.
- Assert the top result's `text` contains content from paragraph 2.
- Assert the result's `doc_title` matches the ingested document's title.
**Done when:** `pytest tests/test_retrieval.py` passes.

---

## Phase 5 — Answer Generation with Citations

### TASK-022 · Implement prompt builder (`generation/prompt.py`)
**What:** `build_prompt(question, chunks, history) -> list[dict]`
- Render system prompt (exact text from `design.md §6.1`).
- Render context block: numbered `[1]`, `[2]`… entries with source metadata header per chunk.
- Render history block: last `settings.session_history_turns` turns only.
- Append user turn with `"Question: {question}"`.
- Return messages list in OpenAI chat-completion format.
**Done when:**
  - Returned list starts with `{"role": "system", ...}`.
  - Context block contains `[1]` through `[n]` entries equal to `len(chunks)`.
  - History block is empty when `history=[]`.
  - History block contains only the last N turns when history is longer than N.

---

### TASK-023 · Write unit tests for prompt builder
**What:** `tests/test_prompt.py`
- Test system prompt is first message.
- Test context numbering matches chunk count.
- Test history truncation to N turns.
- Test that an empty chunks list still produces a valid messages list (for the "not found" path, even though LLM is not called there).
**Done when:** `pytest tests/test_prompt.py` passes all 4 tests.

---

### TASK-024 · Implement Ollama LLM client (`generation/llm.py`)
**What:** `OllamaClient` implementing `LLMClientProtocol`.
- `complete(messages: list[dict]) -> str`: POST to `{settings.ollama_base_url}/api/chat` with model, messages, `temperature`, `max_tokens`.
- Raise `LLMError` on connection failure or non-200 response.
**Done when:** With Ollama running locally and `llama3` pulled, `OllamaClient().complete([{"role":"user","content":"Say hello"}])` returns a non-empty string.

---

### TASK-025 · Implement OpenAI-compatible LLM client (`generation/llm.py`)
**What:** `OpenAIClient` implementing `LLMClientProtocol`.
- Use the `openai` library's `ChatCompletion.create` (or async equivalent).
- Configurable `base_url`, `api_key`, `model`, `temperature`, `max_tokens`.
**Done when:** With a valid API key and endpoint, `OpenAIClient().complete([{"role":"user","content":"Say hello"}])` returns a non-empty string.

---

### TASK-026 · Implement LLM client factory (`generation/llm.py`)
**What:** `get_llm_client() -> LLMClientProtocol`
- Return `OpenAIClient` if `settings.llm_provider == "openai"`, else `OllamaClient`.
**Done when:** Switching `LLM_PROVIDER` env var between `"ollama"` and `"openai"` changes the returned type.

---

### TASK-027 · Implement citation guard (`generation/citation_guard.py`)
**What:** `ensure_citations(answer: str, chunks: list[RetrievedChunk]) -> str`
- If `"Sources:"` is present in `answer`, return `answer` unchanged.
- Otherwise, append a `"\n\nSources:\n"` block with one line per chunk formatted as `"- [n] {doc_title}, {section_heading}, Page {page_number}"`.
**Done when:**
  - An answer containing `"Sources:"` is returned unchanged.
  - An answer without `"Sources:"` gains a correctly formatted Sources section with one entry per chunk.
  - An answer with 0 chunks appends `"Sources:\n- (none retrieved)"`.

---

### TASK-028 · Write unit tests for citation guard
**What:** `tests/test_citation_guard.py`
- Test: answer already has Sources → unchanged.
- Test: answer missing Sources → appended correctly.
- Test: empty chunks list → appended with "(none retrieved)".
**Done when:** `pytest tests/test_citation_guard.py` passes all 3 tests.

---

### TASK-029 · Implement answer generator (`generation/generator.py`)
**What:** `generate_answer(question, chunks, history, llm_client) -> GenerationResult`
- If `chunks` is empty, return `GenerationResult(answer=NOT_FOUND_MSG, sources=[], not_found=True)` without calling the LLM.
- Otherwise: build prompt → call LLM → run citation guard → parse `sources` list from the answer text.
- Return `GenerationResult(answer, sources, not_found=False)`.
**Done when:**
  - Empty chunks path returns `not_found=True` and the exact `NOT_FOUND_MSG` string.
  - Non-empty chunks path calls the LLM and returns `not_found=False`.
  - `sources` list in the result is non-empty when LLM returns a valid answer.

---

## Phase 6 — API

### TASK-030 · Implement Pydantic schemas (`api/schemas.py`)
**What:** Define all request/response models from `design.md §7.1`:
`ChatRequest`, `ChatResponse`, `SourceItem`, `IngestResponse`, `HealthResponse`.
**Done when:** `from api.schemas import ChatRequest; ChatRequest(question="hello")` works; `ChatRequest(question="")` raises a `ValidationError`.

---

### TASK-031 · Implement session store (`session/store.py`)
**What:**
- `get_or_create_session(session_id: str | None) -> Session`: create new UUID session if `None`.
- `add_turn(session_id, role, content)`: append turn; prune to `settings.session_history_turns * 2` turns.
- `get_history(session_id) -> list[Turn]`.
- Background cleanup: remove sessions idle > `settings.session_ttl_minutes` (run every 5 min via `asyncio` task).
**Done when:**
  - Adding `settings.session_history_turns + 2` turns and reading history returns exactly `settings.session_history_turns * 2` turns.
  - A `None` session_id returns a new session with a valid UUID.

---

### TASK-032 · Implement `/health` router (`api/routers/health.py`)
**What:** `GET /health` → `HealthResponse`
- Query `store.count()` for total chunks.
- Report count of active ingest jobs from a shared job registry.
**Done when:** `GET /health` returns `{"status": "ok", "total_chunks": <int>, "active_ingest_jobs": <int>}` with HTTP 200.

---

### TASK-033 · Implement bearer-token auth dependency (`api/auth.py`)
**What:** `require_ingest_token(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()))`
- Compare `credentials.credentials` to `settings.ingest_api_key` using `secrets.compare_digest`.
- Raise `HTTP 401` if mismatch or key is unset.
**Done when:**
  - A request with the correct token passes without error.
  - A request with a wrong token raises HTTP 401.
  - A request with no `Authorization` header raises HTTP 401.

---

### TASK-034 · Implement `/ingest` router (`api/routers/ingest.py`)
**What:** `POST /ingest` (authenticated)
- Accept `UploadFile`; validate extension (`.pdf`, `.html`, `.htm`, `.txt`, `.md`).
- Save to a temp file; enqueue `ingest_file(...)` as a `BackgroundTask`.
- Register job in shared job registry dict; update status when done/failed.
- Return HTTP 202 with `IngestResponse(job_id=..., status="queued", filename=...)`.
**Done when:**
  - Uploading a valid PDF returns HTTP 202 with a job_id.
  - Uploading a `.docx` file returns HTTP 415.
  - Uploading without a token returns HTTP 401.
  - After background task completes, job status in registry changes to `"done"`.

---

### TASK-035 · Implement `/chat` router (`api/routers/chat.py`)
**What:** `POST /chat`
- Validate `ChatRequest`.
- Load session history.
- Retrieve chunks → rerank.
- Generate answer.
- Save turns to session.
- Return `ChatResponse`.
**Done when:**
  - A valid question returns HTTP 200 with `answer`, `sources`, `session_id`.
  - An empty question body returns HTTP 422.
  - `not_found` is `true` in the response when no chunks are retrieved.
  - Sending a follow-up question with the same `session_id` includes prior history in the prompt (verify by checking that the answer references context from the previous turn when appropriate).

---

### TASK-036 · Wire up FastAPI app and middleware (`api/main.py`)
**What:**
- Register all three routers.
- Add CORS middleware (all origins in dev).
- Add `slowapi` rate limiter (30 req/min/IP on `/chat`).
- Serve `ui/index.html` at `GET /`.
- Run startup events: initialise embedder, LLM client, vector store singletons; start session cleanup task.
**Done when:**
  - `uvicorn api.main:app --reload` starts without error.
  - `GET /` returns the HTML UI with HTTP 200.
  - Sending 31 `/chat` requests in under 60 seconds from the same IP causes the 31st to return HTTP 429.

---

### TASK-037 · Write API integration tests (`tests/test_api.py`)
**What:** Use `httpx.AsyncClient` with `app` as the ASGI transport.
- Test `GET /health` returns 200.
- Test `POST /chat` with valid question returns 200 and `session_id`.
- Test `POST /chat` with empty question returns 422.
- Test `POST /ingest` without token returns 401.
- Test `POST /ingest` with valid token and PDF file returns 202.
**Done when:** `pytest tests/test_api.py` passes all 5 tests.

---

## Phase 7 — Chat UI

### TASK-038 · Create UI skeleton (`ui/index.html`)
**What:** Static single-file HTML page with:
- Header bar with app name and brief tagline.
- Scrollable chat thread `<div id="chat-thread">`.
- Text `<textarea id="question-input">` and `<button id="send-btn">`.
- `<link>` to inline CSS (within same file).
No JavaScript yet.
**Done when:** Opening the file in a browser shows the layout matching `design.md §8.1` without console errors.

---

### TASK-039 · Implement session initialisation and question submission (UI JS)
**What:**
- On page load: `sessionId = crypto.randomUUID()`, stored in `sessionStorage`.
- On send button click (or Enter key): read textarea, POST to `/chat`, append user bubble immediately.
- Disable textarea and button while request is in flight; re-enable after response.
**Done when:** Submitting a question appends a user bubble and re-enables the form after the fetch completes (even if the response is an error).

---

### TASK-040 · Implement answer rendering and sources accordion (UI JS)
**What:**
- On successful response: render answer text via `marked.parse()` (CDN or inline).
- Append `<details><summary>Sources (n)</summary>…</details>` block listing each source item.
- Auto-scroll chat thread to bottom.
**Done when:** The bot bubble shows formatted Markdown and a collapsed Sources block; clicking Sources expands it.

---

### TASK-041 · Implement "not found" and error states (UI JS)
**What:**
- If `response.not_found === true`: render bubble with amber left border and ⚠ icon prefix.
- If `fetch` throws or HTTP status ≥ 500: render red error bubble "Service unavailable. Please try again."
- If HTTP 429: render amber bubble "Too many requests. Please wait a moment."
**Done when:** Mocking the API to return `not_found: true` shows an amber bubble; mocking a 500 shows a red bubble; mocking a 429 shows the rate-limit message.

---

### TASK-042 · Implement loading indicator (UI JS)
**What:**
- Append an animated ellipsis "thinking" bubble while fetch is in progress.
- Remove it once the response arrives.
**Done when:** There is a visible "…" (or spinner) bubble between question submission and answer display that disappears cleanly.

---

### TASK-043 · Apply styling (UI CSS)
**What:** Inline CSS covering:
- Light/dark mode via `prefers-color-scheme` media query.
- Blue left border for normal bot bubbles; amber for `not_found`; red for errors.
- Monospace smaller-font source items on grey background.
- Mobile-friendly layout (max-width 800px, responsive textarea).
**Done when:** The UI renders correctly in Chrome on a 1280px desktop and a simulated 390px mobile viewport.

---

## Phase 8 — Evaluation

### TASK-044 · Build evaluation dataset (`scripts/eval_dataset.json`)
**What:** A JSON array of at least 20 question–answer pairs covering:
- Income tax slab questions (old and new regime, at least 2 AYs).
- Section 80C, 80D, 80E deduction limits.
- ITR form selection (at least 3 scenarios).
- GST registration threshold.
- TDS rate under section 194C.
- Capital gains tax rate for listed equities (LTCG).
- 2 questions outside scope (should trigger refusal).
- 2 questions with no KB match (should trigger "not found").

Each entry:
```json
{
  "id": "Q001",
  "question": "...",
  "expected_answer_contains": ["₹1,50,000", "80C"],
  "expected_source_doc": "Income Tax Act 1961",
  "expect_not_found": false,
  "expect_refusal": false
}
```
**Done when:** File exists with ≥ 20 entries covering all 8 categories above.

---

### TASK-045 · Implement evaluation runner (`scripts/evaluate.py`)
**What:** Script that:
- Loads `eval_dataset.json`.
- For each entry, calls `POST /chat` and checks:
  - `not_found` flag matches `expect_not_found`.
  - If `expect_refusal`, answer contains the out-of-scope refusal phrase.
  - If not not_found and not refusal, all strings in `expected_answer_contains` appear in the answer (case-insensitive).
  - At least one source's `doc_title` matches `expected_source_doc` (when applicable).
- Prints a per-question PASS/FAIL table and a summary: total, passed, failed, pass-rate %.
**Done when:** Running the script against a live server prints the table and exits 0 if pass-rate ≥ 80 %, exits 1 otherwise.

---

### TASK-046 · Add hallucination check to evaluator
**What:** For every non-`not_found` answer, assert that at least one source is cited (`sources` list is non-empty). Log any answer that cites zero sources as a FAIL regardless of content match.
**Done when:** Modifying the citation guard to strip sources causes evaluation failures on those entries.

---

### TASK-047 · Add retrieval latency benchmark
**What:** In `scripts/evaluate.py`, record wall-clock time for each `/chat` call. Report: mean, p95, max latency. Assert p95 < 15,000 ms (REQ-NFP-01).
**Done when:** The script prints a latency summary table after the accuracy table; it fails with a message if p95 exceeds the threshold.

---

## Phase 9 — Deployment

### TASK-048 · Create `Dockerfile`
**What:** Multi-stage build.
- Stage 1 (`builder`): install Python deps into a venv.
- Stage 2 (`runtime`): copy venv; copy source; expose port 8000; set `CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]`.
- Use `python:3.11-slim` as base.
- Run as non-root user `appuser`.
**Done when:** `docker build -t taxbot .` succeeds; `docker run --env-file .env -p 8000:8000 taxbot` starts and `GET /health` returns 200.

---

### TASK-049 · Create `docker-compose.yml`
**What:** Single-service compose file for TaxBot.
- Mount `./data/chromadb` as a named volume so the vector store persists across container restarts.
- Mount `./docs` as a read-only volume so bulk ingest can access source documents.
- Load env vars from `.env` file.
- Expose port 8000.
**Done when:** `docker compose up` starts the service; `docker compose down && docker compose up` retains previously ingested chunks (confirmed via `GET /health` chunk count).

---

### TASK-050 · Create `README.md`
**What:** End-to-end getting-started guide covering:
1. Prerequisites (Python 3.11, Ollama, Docker optional).
2. `git clone` → `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set required vars.
4. Download and ingest starter documents: `python scripts/ingest_bulk.py --dir docs/raw/`.
5. Start the server: `uvicorn api.main:app --reload`.
6. Open `http://localhost:8000` in a browser.
7. Run evaluation: `python scripts/evaluate.py`.
8. Docker quick-start: `docker compose up`.
**Done when:** A developer following only the README (without referring to `design.md`) can get a running, queryable instance.

---

### TASK-051 · Create `scripts/update_kb.py` CLI
**What:** Full implementation of the annual KB update CLI from `design.md §11.4`.
Flags: `--dir`, `--file`, `--delete-doc`, `--dry-run`, `--force`, `--list`.
- `--dry-run`: print actions (add/replace/skip) without touching ChromaDB.
- `--list`: print a table of all documents in the KB (filename, doc_title, assessment_year, chunk count).
- `--force`: re-ingest even if `doc_id` (SHA-256) is unchanged.
**Done when:**
  - `--dry-run` prints actions and ChromaDB chunk count is unchanged after the run.
  - `--list` prints one row per distinct `filename` in the collection.
  - `--delete-doc <filename>` removes all chunks for that file; re-running `--list` no longer shows it.

---

### TASK-052 · Document production hardening steps
**What:** Add a `DEPLOYMENT.md` file (not a full implementation task) covering:
- Restrict CORS to known frontend origin.
- Set `LLM_TEMPERATURE=0` (already default; call it out explicitly).
- Put the service behind an HTTPS reverse proxy (nginx example config provided).
- Set `INGEST_API_KEY` to a strong random value (`python -c "import secrets; print(secrets.token_hex(32))"`).
- Rotate `INGEST_API_KEY` without downtime (env var change → container restart).
- ChromaDB backup: `cp -r ./data/chromadb ./backups/chromadb-$(date +%F)`.
- Log aggregation note: application logs go to stdout; pipe to your log aggregator of choice.
**Done when:** File exists and covers all 7 points above.

---

## Task Summary

| Phase | Tasks | IDs |
|-------|-------|-----|
| 1 · Project Setup | 5 | 001–005 |
| 2 · Ingestion Pipeline | 8 | 006–013 |
| 3 · Embedding & Vector Store | 4 | 014–018 |
| 4 · Retrieval | 3 | 019–021 |
| 5 · Answer Generation | 8 | 022–029 |
| 6 · API | 8 | 030–037 |
| 7 · Chat UI | 6 | 038–043 |
| 8 · Evaluation | 4 | 044–047 |
| 9 · Deployment | 5 | 048–052 |
| **Total** | **51** | |

---

## Dependency Graph (abbreviated)

```
001 → 002 → 003 → 004 → 005
                         │
              ┌──────────┤
              ▼          ▼
           006-008      014-016
              │             │
              ▼             │
           009-010          │
              │             │
              ▼             ▼
            011           017-018
              │             │
              ▼             │
            012 ────────────┘
              │
              ▼
         019 → 020 → 021
                        │
                        ▼
                   022-029 (generation)
                        │
                        ▼
                   030-037 (API)
                        │
              ┌─────────┤
              ▼         ▼
           038-043    044-047
           (UI)       (eval)
              │
              ▼
           048-052 (deployment)
```
