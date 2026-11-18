# TaxBot – Production Deployment Task List

> Companion to `tasks.md` (backend logic tasks 001–052).
> These tasks cover containerisation, hardening, CI/CD, hosting, ops, and docs.
> Tasks build on each other in group order. Each group ends with a review checkpoint.

---

## Status legend
- `[ ]` not started
- `[x]` done
- `[~]` in progress

---

## Group A — API layer (prerequisite for everything) ✦ EXECUTE FIRST

### DEPLOY-001 · Implement session store (`session/store.py`)
**What:** In-memory session dict with TTL eviction.
- `get_or_create_session(session_id)`, `add_turn()`, `get_history()`, `cleanup_expired()`.
- Background asyncio task evicts idle sessions every 5 min.
**Done when:** session_history_turns cap works, TTL eviction runs without crashing.

### DEPLOY-002 · Implement FastAPI app (`api/main.py`)
**What:** Full FastAPI application with:
- Lifespan events: initialise `embedder`, `store`, `llm_client` singletons; start session cleanup task.
- CORS with `ALLOWED_ORIGINS` env var (default `*` for dev, restricted for prod).
- Request-ID middleware (`X-Request-ID` header on every response).
- Global exception handler (catches `TaxBotError` → HTTP 400/500 with JSON body).
- Request body size limit: 64 KB.
- `slowapi` rate limiter wired to `/chat`.
- Register routers: `/chat`, `/ingest`, `/health`.
- Serve `ui/index.html` at `GET /`.
**Done when:** `uvicorn api.main:app --reload` starts; `GET /health` returns 200.

### DEPLOY-003 · Implement `/health` and `/ready` endpoints (`api/routers/health.py`)
**What:**
- `GET /health` → `{"status":"ok","total_chunks":<int>,"active_ingest_jobs":<int>}` (always 200).
- `GET /ready` → 200 when embedder and store are initialised; 503 until they are (used by container health checks and load balancers).
**Done when:** Both endpoints return correct status codes before and after startup.

### DEPLOY-004 · Implement `/chat` router (`api/routers/chat.py`)
**What:** `POST /chat` with rate-limit 30/min/IP.
- Validate `ChatRequest` (Pydantic, 1–2000 chars).
- Input sanitisation: strip leading/trailing whitespace, collapse repeated whitespace.
- Prompt-injection guard: reject questions containing `RULE`, `SYSTEM`, `CONTEXT`, `END CONTEXT`, `IGNORE PREVIOUS INSTRUCTIONS`, or other known injection markers (case-insensitive, regex).
- Full RAG pipeline: session load → embed → retrieve → rerank → generate.
- Response caching: SHA-256(question) → cached `ChatResponse` with 5-min TTL (in-memory LRU, maxsize=256).
- Structured logging: log each request with request_id, session_id, latency_ms, not_found, num_sources.
**Done when:** `POST /chat` returns valid `ChatResponse`; repeated identical questions hit cache; injected prompts are rejected with 400.

### DEPLOY-005 · Implement `/ingest` router (`api/routers/ingest.py`)
**What:** `POST /ingest` (Bearer token auth).
- Validate MIME and extension (`.pdf`, `.html`, `.htm`, `.txt`, `.md` only).
- File size limit: 50 MB.
- Save to temp file; run `ingest_file()` as `BackgroundTask`.
- Job registry dict keyed by UUID4; status cycles queued → running → done/failed.
- `GET /ingest/{job_id}` returns job status.
**Done when:** Upload returns 202; unsupported type → 415; no token → 401; >50 MB → 413.

### DEPLOY-006 · Add structured JSON logging and Sentry integration (`api/main.py`, `config.py`)
**What:**
- Replace `basicConfig` text format with `python-json-logger` JSON output (fields: timestamp, level, logger, message, request_id, latency_ms).
- Add `SENTRY_DSN` env var; if set, initialise Sentry SDK with `traces_sample_rate=0.1`.
- Capture unhandled exceptions and slow requests (> 10 s) to Sentry.
**Done when:** Log lines are valid JSON in production mode; Sentry SDK initialises without error when `SENTRY_DSN` is set.

---

## Group B — Containerisation

### DEPLOY-007 · Multi-stage Dockerfile for backend
**What:** `Dockerfile` in project root.
- Stage 1 `builder`: `python:3.11-slim`, install deps into `/opt/venv`.
- Stage 2 `runtime`: copy venv + source, create non-root user `appuser` (UID 1000), set `PYTHONPATH`, expose port 8000.
- `HEALTHCHECK CMD curl --fail http://localhost:8000/ready || exit 1` with 30 s start-period.
- `.dockerignore` excludes `.venv`, `__pycache__`, `tests`, `*.pyc`, `.git`, `taxmitra-web`.
**Done when:** `docker build -t taxbot-api .` succeeds; container starts and `/ready` returns 200; runs as non-root.

### DEPLOY-008 · Dockerfile for Next.js frontend
**What:** `taxmitra-web/Dockerfile`.
- Stage 1 `deps`: `node:20-alpine`, `npm ci`.
- Stage 2 `builder`: copy source, `NEXT_PUBLIC_API_URL` build arg, `npm run build` with `output: "standalone"` in `next.config.mjs`.
- Stage 3 `runner`: `node:20-alpine`, copy `.next/standalone` + `.next/static` + `public`, non-root user `nextjs` (UID 1001), expose 3000.
- `HEALTHCHECK CMD wget -qO- http://localhost:3000/api/health || exit 1`.
**Done when:** `docker build -t taxbot-web taxmitra-web/` succeeds; container serves the app on port 3000.

### DEPLOY-009 · `docker-compose.yml` and `.env.example` (root)
**What:** `docker-compose.yml` orchestrating three services.
- `backend`: builds from `Dockerfile`, env from `.env`, mounts `./data/chromadb` as named volume, port 8000.
- `frontend`: builds from `taxmitra-web/Dockerfile`, build arg `NEXT_PUBLIC_API_URL=http://backend:8000`, port 3000.
- `chromadb_data` named volume for persistence.
- `healthcheck` dependencies: frontend waits for backend.
- Companion `.env.example` at project root documenting all required vars for compose.
**Done when:** `docker compose up --build` starts both services; chat works end-to-end; `docker compose down && docker compose up` retains ingested data.

---

## Group C — CI/CD with GitHub Actions

### DEPLOY-010 · Backend CI workflow (`.github/workflows/backend-ci.yml`)
**What:** Triggers on `push` and `pull_request` to any branch.
- Jobs: `lint` (ruff), `typecheck` (mypy), `test` (pytest with coverage), `eval` (runs `evaluate.py` against a live server started in the CI job).
- `eval` job reads `EVAL_PASS_THRESHOLD` from `.github/eval-config.yml` (default 80); fails if pass-rate < threshold.
- Uses matrix: Python 3.11.
- Caches pip deps.
**Done when:** Pipeline runs green on a clean push; pushing a broken citation guard makes the eval job fail.

### DEPLOY-011 · Frontend CI workflow (`.github/workflows/frontend-ci.yml`)
**What:** Triggers on `push` and `pull_request`.
- Jobs: `lint` (`next lint`), `typecheck` (`tsc --noEmit`), `build` (`next build`).
- Node 20, caches `.npm`.
**Done when:** Pipeline runs green; a type error in a component breaks the `typecheck` job.

### DEPLOY-012 · Docker build & push workflow (`.github/workflows/docker-push.yml`)
**What:** Triggers on merge to `main`.
- Builds both images; pushes to GitHub Container Registry (`ghcr.io/<owner>/taxbot-api` and `taxbot-web`).
- Tags: `latest` + git SHA.
- Reuses GitHub Actions cache for Docker layers.
**Done when:** Merging to main triggers the workflow; both images appear in GHCR.

### DEPLOY-013 · Auto-deploy workflow (`.github/workflows/deploy.yml`)
**What:** Triggers after `docker-push.yml` completes on `main`.
- Deploys backend to Render via `curl` to Render Deploy Hook URL (secret: `RENDER_DEPLOY_HOOK_URL`).
- Deploys frontend to Vercel via `vercel --prod` (secret: `VERCEL_TOKEN`).
- Posts a Slack/Discord notification on success or failure (optional `NOTIFY_WEBHOOK_URL`).
**Done when:** A merge to main triggers a full redeploy; `RENDER_DEPLOY_HOOK_URL` secret present → Render deploy triggered.

### DEPLOY-014 · Evaluation config file (`.github/eval-config.yml`)
**What:** Single YAML file defining the CI evaluation thresholds.
```yaml
pass_rate_threshold: 80        # minimum % of questions that must pass
p95_latency_ms: 15000          # maximum allowed p95 latency
citation_rate_threshold: 90    # minimum % of non-not-found answers with citations
```
**Done when:** Changing `pass_rate_threshold: 100` causes the eval CI job to fail.

---

## Group D — Hosting configuration

### DEPLOY-015 · `render.yaml` (Render.com blueprint)
**What:** Infrastructure-as-code for Render.
- Service `taxbot-api`: Docker runtime, `Dockerfile` in repo root, 1 vCPU / 512 MB, auto-deploy on main, health check path `/ready`, env vars listed (secrets from Render dashboard).
- Persistent disk mounted at `/app/data/chromadb`.
**Done when:** `render.yaml` is valid; importing it into Render creates the service.

### DEPLOY-016 · Vercel configuration (`taxmitra-web/vercel.json`)
**What:** Vercel project config.
- `framework: nextjs`, `buildCommand: npm run build`, output `standalone`.
- Rewrites: `/api/chat` → backend URL (avoids CORS by proxying through Vercel edge).
- `NEXT_PUBLIC_API_URL` environment variable set to Render backend URL.
**Done when:** `vercel --prod` deploys the frontend successfully; API calls route correctly.

### DEPLOY-017 · AWS deployment guide (`docs/aws-deployment.md`)
**What:** Step-by-step instructions covering:
1. Push images to ECR (login, tag, push commands).
2. App Runner service from ECR image (console + CLI steps); env vars; health check.
3. Alternative: ECS Fargate task definition + service + ALB (abbreviated).
4. IAM roles: least-privilege policy for ECR pull.
5. Environment variables via AWS Systems Manager Parameter Store.
6. Custom domain via Route 53 + ACM certificate.
**Done when:** A developer can follow the doc to deploy on AWS without referring to external docs.

### DEPLOY-018 · Custom domain and HTTPS instructions (`docs/custom-domain.md`)
**What:** Combined guide covering:
- Vercel custom domain: add domain in dashboard, update DNS CNAME, automatic TLS.
- Render custom domain: add domain in settings, update DNS A record, automatic TLS.
- AWS: ACM certificate + ALB HTTPS listener setup.
- Updating `ALLOWED_ORIGINS` to match the custom domain.
**Done when:** Doc exists and covers all three hosting paths.

---

## Group E — Operations

### DEPLOY-019 · Analytics endpoint (`api/routers/analytics.py`)
**What:** `GET /analytics` (no auth required, rate-limited to 10/min).
- Returns in-memory counters (reset on restart):
  `questions_total`, `not_found_total`, `out_of_scope_total`, `cache_hits`,
  `feedback_up`, `feedback_down`, `avg_latency_ms`, `p95_latency_ms`.
- `POST /feedback` persists thumbs-up/down to the in-memory counters (session_id, question, feedback type).
**Done when:** After 5 chat requests, `GET /analytics` returns non-zero `questions_total`.

### DEPLOY-020 · Uptime monitoring (`docs/monitoring.md`)
**What:** Documentation file covering:
- BetterUptime (or UptimeRobot free tier): monitor `/ready` every 1 min; alert on 2 consecutive failures.
- Sentry: error tracking, session replay disabled (privacy), alert on new issues.
- Render built-in metrics: CPU, memory, request rate.
- Vercel analytics: Core Web Vitals, error rate.
**Done when:** Doc exists with step-by-step configuration for each tool.

### DEPLOY-021 · Scheduled KB re-ingestion job (`scripts/scheduled_kb_update.py`)
**What:** Script intended to run as a cron job (Render Cron Job or GitHub Actions scheduled workflow).
- Reads `KB_UPDATE_DIR` env var (directory of new documents to ingest).
- Calls `ingest_file()` for each file in the directory.
- Runs `evaluate.py` smoke test after ingestion.
- Sends a summary notification to `NOTIFY_WEBHOOK_URL` (Slack/Discord/email).
- Companion: `.github/workflows/kb-update.yml` — scheduled workflow (`cron: "0 6 1 2 *"`) that triggers this script after each Union Budget (Feb 1) and financial year change (Apr 1).
**Done when:** Script runs without error on a directory of test documents; workflow YAML is valid.

---

## Group F — Documentation

### DEPLOY-022 · `README.md` (root)
**What:** Complete project README with:
- Mermaid architecture diagram (user → frontend → backend → ChromaDB + LLM).
- Prerequisites section.
- Local setup (clone, venv, .env, ingest starter docs, run server).
- Docker quick-start.
- Deployment section: Vercel + Render (links to docs/), AWS alternative (link).
- Evaluation: how to run `evaluate.py`.
- Troubleshooting: ChromaDB path, Ollama not running, missing NLTK data, CORS errors.
- Contributing and licence.
**Done when:** A developer following only the README gets a working local instance.

---

## Task Summary by Group

| Group | Tasks | Description |
|-------|-------|-------------|
| A — API layer | DEPLOY-001–006 | Session store, FastAPI app, health, chat, ingest, logging |
| B — Containers | DEPLOY-007–009 | Backend Dockerfile, frontend Dockerfile, docker-compose |
| C — CI/CD | DEPLOY-010–014 | GitHub Actions workflows + eval config |
| D — Hosting | DEPLOY-015–018 | render.yaml, vercel.json, AWS guide, domain guide |
| E — Operations | DEPLOY-019–021 | Analytics, monitoring doc, scheduled KB update |
| F — Docs | DEPLOY-022 | README with Mermaid diagram |
| **Total** | **22** | |

---

## Review Checkpoints

After Group A → review: does `uvicorn api.main:app` start cleanly and serve `/health`?
After Group B → review: does `docker compose up` run both containers end-to-end?
After Group C → review: do all GitHub Actions workflows pass on a clean push?
After Group D → review: are hosting configs syntactically valid and complete?
After Group E → review: does `/analytics` return data after a chat session?
After Group F → review: is the README accurate and self-contained?
