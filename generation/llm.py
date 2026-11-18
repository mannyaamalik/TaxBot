"""LLM client implementations for TaxBot.

Two clients share ``LLMClientProtocol``:
- ``OllamaClient``  — talks to a locally running Ollama server.
- ``OpenAIClient``  — talks to any OpenAI-compatible chat-completion API.

``get_llm_client()`` selects the right one from ``settings.llm_provider``.
Both clients are stateless and thread-safe; create once at startup.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

import httpx

from config import settings
from exceptions import LLMError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Interface every LLM client must satisfy."""

    def complete(self, messages: list[dict[str, str]]) -> str:
        """Send *messages* to the model and return the reply text."""
        ...


# ---------------------------------------------------------------------------
# Ollama client  (TASK-024)
# ---------------------------------------------------------------------------


class OllamaClient:
    """HTTP client for a locally running Ollama server."""

    def __init__(self) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model
        self._temperature = settings.llm_temperature
        self._max_tokens = settings.llm_max_tokens

        # Reuse a single httpx client for connection pooling
        self._http = httpx.Client(timeout=120.0)
        logger.info(
            "OllamaClient ready: model=%s base_url=%s",
            self._model,
            self._base_url,
        )

    def complete(self, messages: list[dict[str, str]]) -> str:
        """POST to /api/chat and return the assistant's reply text.

        Raises:
            LLMError: on connection failure, timeout, or non-200 response.
        """
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self._temperature,
                "num_predict": self._max_tokens,
            },
        }
        try:
            response = self._http.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise LLMError(
                f"Cannot connect to Ollama at {self._base_url}. "
                "Is Ollama running? (ollama serve)"
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMError(
                f"Ollama request timed out after 120 s (model={self._model!r})."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMError(
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc

        data = response.json()
        # Ollama /api/chat non-streaming response format:
        # {"message": {"role": "assistant", "content": "..."}, ...}
        try:
            content: str = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMError(f"Unexpected Ollama response structure: {data}") from exc

        logger.debug("OllamaClient: received %d chars.", len(content))
        return content


# ---------------------------------------------------------------------------
# OpenAI-compatible client  (TASK-025)
# ---------------------------------------------------------------------------


class OpenAIClient:
    """Client for any OpenAI-compatible chat-completion API."""

    def __init__(self) -> None:
        try:
            import openai  # lazy import — not required if using Ollama
        except ImportError as exc:
            raise LLMError(
                "openai package is not installed. "
                "Run: pip install openai>=1.30"
            ) from exc

        self._client = openai.OpenAI(
            api_key=settings.llm_api_key or "placeholder",
            base_url=settings.llm_api_base_url,
        )
        self._model = settings.llm_model
        self._temperature = settings.llm_temperature
        self._max_tokens = settings.llm_max_tokens

        logger.info(
            "OpenAIClient ready: model=%s base_url=%s",
            self._model,
            settings.llm_api_base_url,
        )

    def complete(self, messages: list[dict[str, str]]) -> str:
        """Call the chat-completion endpoint and return the reply text.

        Raises:
            LLMError: on API error, timeout, or empty response.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
        except Exception as exc:
            raise LLMError(f"OpenAI API call failed: {exc}") from exc

        try:
            content = response.choices[0].message.content or ""
        except (IndexError, AttributeError) as exc:
            raise LLMError(f"Unexpected OpenAI response structure: {response}") from exc

        if not content.strip():
            raise LLMError("LLM returned an empty response.")

        logger.debug("OpenAIClient: received %d chars.", len(content))
        return content


# ---------------------------------------------------------------------------
# Factory  (TASK-026)
# ---------------------------------------------------------------------------


def get_llm_client() -> LLMClientProtocol:
    """Return the LLM client selected by ``settings.llm_provider``.

    Returns:
        ``OpenAIClient`` when ``LLM_PROVIDER=openai``;
        ``OllamaClient`` otherwise.
    """
    if settings.llm_provider.lower() == "openai":
        logger.info("LLM provider: openai")
        return OpenAIClient()
    logger.info("LLM provider: ollama (default)")
    return OllamaClient()
