"""
app/infrastructure/ollama_client.py
====================================================================
Implements ILLMClient. Thin adapter over Ollama's HTTP API
(`POST /api/generate`, non-streaming). base_url/model/timeout/temperature/seed
all default from Settings (app/core/config.py) -- no hardcoded values here,
same discipline as every other infrastructure adapter.

`seed` was added after a QA report of "the same image yields different
results across attempts" was reproduced at this layer: temperature=0.0 with
Ollama's default (random) seed produced two different reports from five
identical requests. See DEFAULT_LLM_SEED in app/core/config.py for the
measurement. Note that this pins THIS call only -- a report that reaches
LLMOrchestrator's content-retry path is generated from a different prompt
(build_retry_prompt), and is a different artifact for a different reason.

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
        seed: int = settings.LLM_SEED,
        keep_alive: str = settings.OLLAMA_KEEP_ALIVE,
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._temperature = temperature
        self._seed = seed
        self._keep_alive = keep_alive

    def complete(self, prompt: str) -> str:
        try:
            response = httpx.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    # keep_alive holds the model resident between requests. A
                    # cold model produces different (though itself reproducible)
                    # wording than a warm one -- see DEFAULT_OLLAMA_KEEP_ALIVE.
                    "keep_alive": self._keep_alive,
                    # temperature alone does NOT make this reproducible --
                    # measured, see DEFAULT_LLM_SEED in app/core/config.py for
                    # the experiment. Both are needed.
                    "options": {"temperature": self._temperature, "seed": self._seed},
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMTransportError(f"Ollama request failed: {exc}") from exc

        return response.json()["response"]
