# ── Stage 1: build / install dependencies ─────────────────────────────────
FROM python:3.11-slim AS builder

# Install build tools needed for some ML packages (tokenizers, numpy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Create a venv so we copy a clean, self-contained directory to the runtime stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies first (cached layer unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download the sentence-transformer and cross-encoder models into the venv cache
# so the runtime container doesn't need internet access.
# Skip this if models are mounted via a volume in your environment.
ARG PRELOAD_MODELS=false
RUN if [ "$PRELOAD_MODELS" = "true" ]; then \
      python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); \
from sentence_transformers.cross_encoder import CrossEncoder; \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"; \
    fi

# ── Stage 2: runtime image ─────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Install curl (required by HEALTHCHECK) and nothing else
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appgroup && \
    useradd -r -g appgroup -u 1000 -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source (excluding items in .dockerignore)
COPY --chown=appuser:appgroup . .

# Create data directory and set ownership
RUN mkdir -p /app/data/chromadb && \
    chown -R appuser:appgroup /app/data

USER appuser

# Runtime environment defaults (all overridable at container start)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8000 \
    HOST=0.0.0.0 \
    LOG_LEVEL=INFO

EXPOSE 8000

# Health check — uses /ready so the container is marked unhealthy during startup
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl --fail --silent http://localhost:${PORT}/ready || exit 1

CMD ["sh", "-c", "uvicorn api.main:app --host $HOST --port $PORT --workers 1"]
