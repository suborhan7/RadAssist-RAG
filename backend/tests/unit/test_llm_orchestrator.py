"""
Unit tests for LLMOrchestrator, per the frozen Phase 7 architecture
(development_log.md, "Phase 7 -- LLM Orchestrator: Architecture (FROZEN)",
"Unit testing strategy" section). Fakes PromptBuilder, ILLMClient, and
StructuralValidator -- pure retry-loop-mechanics testing, no real LLM.

Scenarios A-E below correspond to the five hand-run smoke scenarios shown
in chat before this file was written (A-D from the initial implementation,
E added after a real gap was found and fixed: a transport failure during a
content-retry attempt now gets its own transport-retry budget, same as the
first call, rather than raising immediately).
"""
from __future__ import annotations

import pytest

from app.domain.entities import ClinicalContext, ReportContent
from app.services.exceptions import LLMGenerationValidationError, LLMTransportError
from app.services.llm_orchestrator import LLMOrchestrator


class FakePromptBuilder:
    def __init__(self):
        self.build_generation_prompt_calls = []
        self.build_retry_prompt_calls = []

    def build_generation_prompt(self, context, language):
        self.build_generation_prompt_calls.append((context, language))
        return "INITIAL_PROMPT"

    def build_retry_prompt(self, context, language, previous_response, validation_errors):
        self.build_retry_prompt_calls.append((previous_response, list(validation_errors)))
        return f"RETRY_PROMPT_for[{previous_response}]"


class FakeLLMClient:
    """Returns queued responses in call order; a queued Exception instance is raised instead."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, prompt):
        self.calls.append(prompt)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeStructuralValidator:
    """Looks up a canned (is_valid, content, errors) result keyed by raw_response."""

    def __init__(self, results_by_raw):
        self.results_by_raw = results_by_raw
        self.calls = []

    def validate(self, raw_response):
        self.calls.append(raw_response)
        return self.results_by_raw[raw_response]


CONTEXT = ClinicalContext(retrieved_cases=(), voted_labels=())
CONTENT = ReportContent(
    examination="e", clinical_history="c", technique="t", findings="f",
    impression="i", recommendation="r", disclaimer="d",
)


def test_success_on_first_attempt():
    pb = FakePromptBuilder()
    llm = FakeLLMClient(["good_resp"])
    sv = FakeStructuralValidator({"good_resp": (True, CONTENT, [])})

    orchestrator = LLMOrchestrator(pb, llm, sv, transport_retry_count=1, content_retry_count=2)
    result = orchestrator.generate_draft(CONTEXT, "en")

    assert result is CONTENT
    assert len(pb.build_generation_prompt_calls) == 1
    assert pb.build_retry_prompt_calls == []
    assert llm.calls == ["INITIAL_PROMPT"]


def test_scenario_a_success_after_n_content_retries_uses_current_not_stale_errors():
    pb = FakePromptBuilder()
    llm = FakeLLMClient(["resp1", "resp2", "resp3"])
    sv = FakeStructuralValidator({
        "resp1": (False, None, ["error-from-attempt-1"]),
        "resp2": (False, None, ["error-from-attempt-2-DIFFERENT"]),
        "resp3": (True, CONTENT, []),
    })

    orchestrator = LLMOrchestrator(pb, llm, sv, transport_retry_count=1, content_retry_count=2)
    result = orchestrator.generate_draft(CONTEXT, "en")

    assert result is CONTENT
    assert len(pb.build_generation_prompt_calls) == 1
    assert pb.build_retry_prompt_calls == [
        ("resp1", ["error-from-attempt-1"]),
        ("resp2", ["error-from-attempt-2-DIFFERENT"]),
    ]


def test_scenario_b_content_budget_exhausted_raises_with_last_response_and_errors():
    pb = FakePromptBuilder()
    llm = FakeLLMClient(["r1", "r2", "r3"])
    sv = FakeStructuralValidator({
        "r1": (False, None, ["e1"]),
        "r2": (False, None, ["e2"]),
        "r3": (False, None, ["e3-final"]),
    })

    orchestrator = LLMOrchestrator(pb, llm, sv, transport_retry_count=0, content_retry_count=2)

    with pytest.raises(LLMGenerationValidationError) as exc_info:
        orchestrator.generate_draft(CONTEXT, "en")

    assert exc_info.value.last_raw_response == "r3"
    assert exc_info.value.last_validation_errors == ["e3-final"]
    assert len(pb.build_generation_prompt_calls) == 1


def test_scenario_c_transport_budget_exhausted_raises_llm_transport_error():
    pb = FakePromptBuilder()
    llm = FakeLLMClient([LLMTransportError("boom-1"), LLMTransportError("boom-2")])
    sv = FakeStructuralValidator({})

    orchestrator = LLMOrchestrator(pb, llm, sv, transport_retry_count=1, content_retry_count=2)

    with pytest.raises(LLMTransportError):
        orchestrator.generate_draft(CONTEXT, "en")

    assert llm.calls == ["INITIAL_PROMPT", "INITIAL_PROMPT"]
    assert len(pb.build_generation_prompt_calls) == 1


def test_scenario_d_transport_retry_recovers_before_content_validation():
    pb = FakePromptBuilder()
    llm = FakeLLMClient([LLMTransportError("flaky"), "good_resp"])
    sv = FakeStructuralValidator({"good_resp": (True, CONTENT, [])})

    orchestrator = LLMOrchestrator(pb, llm, sv, transport_retry_count=1, content_retry_count=2)
    result = orchestrator.generate_draft(CONTEXT, "en")

    assert result is CONTENT
    assert llm.calls == ["INITIAL_PROMPT", "INITIAL_PROMPT"]
    assert len(pb.build_generation_prompt_calls) == 1


def test_scenario_e_transport_failure_during_content_retry_gets_its_own_budget():
    """Regression test for the gap found and fixed after the initial Step 4
    implementation: a transport failure occurring on a content-retry's LLM
    call (not the very first call) must be retried at the transport level
    using the SAME retry prompt, not raise immediately."""
    pb = FakePromptBuilder()
    llm = FakeLLMClient([
        "resp1",                                        # initial call: transport OK, content invalid
        LLMTransportError("flaky-mid-content-retry"),    # 1st content-retry's LLM call: transport failure
        "resp2",                                         # transport retry of the SAME retry prompt: succeeds
    ])
    sv = FakeStructuralValidator({
        "resp1": (False, None, ["needs-fix"]),
        "resp2": (True, CONTENT, []),
    })

    orchestrator = LLMOrchestrator(pb, llm, sv, transport_retry_count=1, content_retry_count=2)
    result = orchestrator.generate_draft(CONTEXT, "en")

    assert result is CONTENT
    assert llm.calls == ["INITIAL_PROMPT", "RETRY_PROMPT_for[resp1]", "RETRY_PROMPT_for[resp1]"]
    assert len(pb.build_generation_prompt_calls) == 1
    # the retry prompt was built ONCE (for resp1's content failure) and
    # resent unchanged when its own transport call flaked, not rebuilt again
    assert len(pb.build_retry_prompt_calls) == 1


def test_build_generation_prompt_called_exactly_once_across_multiple_retries():
    """Explicit, standalone assertion (not just implicit in the scenarios
    above): build_generation_prompt must never be called again once the
    first attempt has been made, regardless of how many content retries
    follow."""
    pb = FakePromptBuilder()
    llm = FakeLLMClient(["r1", "r2", "r3", "r4"])
    sv = FakeStructuralValidator({
        "r1": (False, None, ["e1"]),
        "r2": (False, None, ["e2"]),
        "r3": (False, None, ["e3"]),
        "r4": (True, CONTENT, []),
    })

    orchestrator = LLMOrchestrator(pb, llm, sv, transport_retry_count=0, content_retry_count=3)
    result = orchestrator.generate_draft(CONTEXT, "en")

    assert result is CONTENT
    assert len(pb.build_generation_prompt_calls) == 1
