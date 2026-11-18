"""TaxBot configuration singleton.

All tuneable parameters are read from environment variables (or a .env file).
Import the ``settings`` singleton; never instantiate Settings directly in
application code.

Usage::

    from config import settings
    print(settings.chunk_size)   # 512
"""

import logging
import logging.config

import nltk
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Embedding ──────────────────────────────────────────────────────────
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embed_batch_size: int = 64

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_embed_model: str = "text-embedding-3-small"

    # ── Vector Store ───────────────────────────────────────────────────────
    chroma_db_path: str = "./data/chromadb"
    chroma_collection: str = "taxbot_kb"

    # ── Chunking ───────────────────────────────────────────────────────────
    chunk_size: int = Field(default=512, gt=0)
    chunk_overlap: int = Field(default=64, ge=0)

    # ── Retrieval ──────────────────────────────────────────────────────────
    retrieval_top_k: int = Field(default=5, gt=0)
    similarity_threshold: float = Field(default=0.40, ge=0.0, le=1.0)

    # ── Reranker ───────────────────────────────────────────────────────────
    reranker_enabled: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_threshold: float = 0.0

    # ── LLM ────────────────────────────────────────────────────────────────
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    llm_api_key: str = ""
    llm_api_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=1024, gt=0)

    # ── Session ────────────────────────────────────────────────────────────
    session_history_turns: int = Field(default=5, gt=0)
    session_ttl_minutes: int = Field(default=60, gt=0)

    # ── API ────────────────────────────────────────────────────────────────
    rate_limit_per_minute: int = Field(default=30, gt=0)
    ingest_api_key: str = "change-me-before-running"

    # ── Server ─────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = Field(default=8000, gt=0)

    # ── Logging ────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    @field_validator("chunk_overlap")
    @classmethod
    def overlap_less_than_size(cls, v: int, info: object) -> int:
        """Overlap must be strictly less than chunk size."""
        # info.data is populated with already-validated fields
        data = getattr(info, "data", {})
        chunk_size = data.get("chunk_size", 512)
        if v >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({v}) must be less than chunk_size ({chunk_size})"
            )
        return v

    def __repr__(self) -> str:
        """Redact secret fields to avoid accidental logging."""
        return (
            f"Settings("
            f"embed_model={self.embed_model!r}, "
            f"chunk_size={self.chunk_size}, "
            f"retrieval_top_k={self.retrieval_top_k}, "
            f"llm_provider={self.llm_provider!r}, "
            f"openai_api_key='[REDACTED]', "
            f"ingest_api_key='[REDACTED]')"
        )


def _configure_logging(level: str) -> None:
    """Set up stdlib logging with a consistent format."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def _ensure_nltk_data() -> None:
    """Download punkt tokeniser data if not already present (TASK-005)."""
    for resource in ("punkt", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{resource}")
        except LookupError:
            nltk.download(resource, quiet=True)


# ── Singleton ─────────────────────────────────────────────────────────────────
settings = Settings()
_configure_logging(settings.log_level)
_ensure_nltk_data()
