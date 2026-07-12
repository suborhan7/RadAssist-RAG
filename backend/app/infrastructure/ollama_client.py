"""
app/infrastructure/ollama_client.py
====================================================================
Implements ILLMClient. Thin adapter over Ollama's HTTP API
(`POST /api/generate`, non-streaming). base_url/model/timeout/temperature
all default from Settings (app/core/config.py) -- no hardcoded values here,
same discipline as every other infrastructure adapter.

Connection failures, timeouts, and non-2xx responses (httpx.HTTPError and
its subclasses -- httpx.RequestError, httpx.HTTPStatusError) are all
transport-level problems from the orchestrator's point of view and are
raised as LLMTransportError so LLMOrchestrator can reliably distinguish
"never got a usable response" from "got a response, content was invalid,"
which trigger different retry budgets (Phase 7 architecture).
"""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.services.exceptions import LLMTransportError


class OllamaClient:
    """Satisfies domain.interfaces.ILLMClient."""

    def __init__(
        self,
        base_url: str = settings.OLLAMA_BASE_URL,
        model: str = settings.OLLAMA_MODEL,
        timeout_seconds: int = settings.OLLAMA_TIMEOUT_SECONDS,
        temperature: float = settings.LLM_TEMPERATURE,
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._temperature = temperature

    def complete(self, prompt: str) -> str:
        try:
            response = httpx.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": self._temperature},
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMTransportError(f"Ollama request failed: {exc}") from exc

        return response.json()["response"]
