"""
Unit tests for app/api/explainability.py's exception-to-HTTP-status
mapping specifically -- the class of test that would have caught the
real, pre-existing LLMTransportError gap found while building Phase 12
Step 6 (see that file's own module docstring). No real app lifespan, no
real DB, no real Ollama/Chroma -- ExplainabilityService itself is
monkeypatched at the route module level to a fake that raises whichever
exception each test needs, so this exercises ONLY the route function's
own try/except mapping, the one thing this file is actually responsible
for.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.api.explainability as explainability_module
from app.services.exceptions import LLMTransportError, ReportNotFoundError


class _FakeService:
    def __init__(self, to_raise: Exception, **_ignored_kwargs) -> None:
        self._to_raise = to_raise

    def explain(self, report_id: str, question: str):
        raise self._to_raise


def _fake_request() -> SimpleNamespace:
    # explain_report() only reads request.app.state.* to build kwargs for
    # ExplainabilityService(...), which is monkeypatched below to ignore
    # them entirely -- any placeholder values are fine here.
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                vector_store=None,
                label_voting_service=None,
                context_builder=None,
                prompt_builder=None,
                llm_orchestrator=None,
            )
        )
    )


def _call_route(monkeypatch, to_raise: Exception):
    monkeypatch.setattr(
        explainability_module,
        "ExplainabilityService",
        lambda **kwargs: _FakeService(to_raise, **kwargs),
    )
    request_body = explainability_module.ExplainRequest(question="Why?")
    return explainability_module.explain_report(
        report_id="11111111-1111-1111-1111-111111111111",
        request_body=request_body,
        request=_fake_request(),
        db=None,
    )


def test_report_not_found_error_maps_to_404(monkeypatch):
    with pytest.raises(HTTPException) as exc_info:
        _call_route(monkeypatch, ReportNotFoundError("no ReportRecord found"))
    assert exc_info.value.status_code == 404


def test_llm_transport_error_maps_to_502(monkeypatch):
    """The real gap: before this fix, LLMTransportError had no handler in
    this route at all, so it would have propagated as an unhandled
    exception instead of a clean 502 -- this test fails against the
    pre-fix code (raises LLMTransportError directly, uncaught) and passes
    against the fix."""
    with pytest.raises(HTTPException) as exc_info:
        _call_route(monkeypatch, LLMTransportError("Ollama unreachable"))
    assert exc_info.value.status_code == 502
