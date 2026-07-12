"""
app/services/exceptions.py
====================================================================
Phase 7 (LLM Orchestrator) exceptions. Two independent failure modes, two
distinct exception types -- transport failure (Ollama unreachable/timed
out) and content failure (structural validation never passed) are
different problems with different retry budgets, and must not be
conflated into one exception type.
"""
from __future__ import annotations


class LLMTransportError(Exception):
    """Ollama unreachable or timed out after the transport retry budget."""


class LLMGenerationValidationError(Exception):
    """Content retry budget exhausted; structural validation never passed."""

    def __init__(self, last_raw_response: str, last_validation_errors: list[str]) -> None:
        super().__init__(
            f"LLM generation validation failed after exhausting the content retry "
            f"budget. Last validation errors: {last_validation_errors}"
        )
        self.last_raw_response = last_raw_response
        self.last_validation_errors = last_validation_errors
