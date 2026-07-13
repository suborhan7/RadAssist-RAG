"""
app/services/exceptions.py
====================================================================
Service-level exceptions shared across phases. Phase 7 (LLM Orchestrator):
two independent failure modes, two distinct exception types -- transport
failure (Ollama unreachable/timed out) and content failure (structural
validation never passed) are different problems with different retry
budgets, and must not be conflated into one exception type. Phase 8
(ReportGenerationService): SessionNotFoundError, distinguishable from any
other failure inside generate() by exception type, not by string matching.
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


class SessionNotFoundError(Exception):
    """Raised by ReportGenerationService.generate() when session_id matches
    no RetrievalSession row -- distinguishable from any other failure inside
    generate() (LLM transport/content errors, DB persistence errors) so a
    caller (Step 7's API route) can map it to its own specific HTTP status
    rather than a generic 500."""
