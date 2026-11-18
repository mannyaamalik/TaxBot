"""Custom exception hierarchy for TaxBot.

All domain-specific errors should subclass one of the base classes defined
here rather than raising bare Exception instances.
"""


class TaxBotError(Exception):
    """Root exception for all TaxBot errors."""


# ── Ingestion ─────────────────────────────────────────────────────────────────


class IngestError(TaxBotError):
    """Raised when document ingestion fails at any stage."""


class UnsupportedFileTypeError(IngestError):
    """Raised when an ingestion request is made for an unsupported file extension."""


# ── Embedding ─────────────────────────────────────────────────────────────────


class EmbedderError(TaxBotError):
    """Raised when an embedding call fails (local model or API)."""


# ── Vector Store ──────────────────────────────────────────────────────────────


class VectorStoreError(TaxBotError):
    """Raised when a ChromaDB operation fails."""


# ── LLM ───────────────────────────────────────────────────────────────────────


class LLMError(TaxBotError):
    """Raised when an LLM completion call fails."""
