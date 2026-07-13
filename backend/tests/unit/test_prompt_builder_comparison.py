"""
Unit tests for PromptBuilder.build_comparison_prompt, per the frozen
Phase 11 architecture (development_log.md, "Phase 11 -- Longitudinal
Patient History & Comparison: Architecture (FROZEN)"). Same discipline as
Phase 9/10's grounding tests: asserts on the EXACT required prohibition
clauses, not just header presence -- a header-presence check would not
catch a future weakening of the wording, and this prompt is safety-
critical (it's the one place an LLM could reintroduce hallucinated
clinical trend language on top of already-computed, trusted facts).
"""
from __future__ import annotations

from app.domain.entities import ComparisonFacts, ReportContent
from app.services.prompt_builder import PromptBuilder


def _content(findings: str, impression: str) -> ReportContent:
    return ReportContent(
        examination="Chest X-ray", clinical_history="Cough", technique="PA view",
        findings=findings, impression=impression,
        recommendation="Clinical correlation advised.", disclaimer="AI-generated draft",
    )


def _facts(
    resolved=("Pneumonia",), persistent=("Cardiomegaly",), new=("Pleural Effusion",), days=30,
) -> ComparisonFacts:
    return ComparisonFacts(
        previous_report_id="prev-id",
        current_report_id="curr-id",
        resolved_findings=resolved,
        persistent_findings=persistent,
        new_findings=new,
        days_between_studies=days,
    )


def _previous() -> ReportContent:
    return _content(
        findings="Findings consistent with pneumonia. Cardiomegaly is noted.",
        impression="Pneumonia with cardiomegaly.",
    )


def _current() -> ReportContent:
    return _content(
        findings="Cardiomegaly persists. New pleural effusion is seen.",
        impression="Cardiomegaly with pleural effusion.",
    )


def test_grounding_instruction_present_and_at_least_as_strict_as_explanation_prompt():
    prompt = PromptBuilder().build_comparison_prompt(_facts(), _previous(), _current())
    assert "GROUNDING INSTRUCTIONS" in prompt
    lowered = prompt.lower()

    # explicit prohibitions required by the frozen spec, each asserted as its
    # own exact clause, not inferred from a generic "be careful" statement
    assert "must not invent any finding" in lowered
    assert "must not invent, suggest, or imply any diagnosis" in lowered
    assert "must not estimate or characterize the severity" in lowered

    # directional/trend language ban, only permitted as a restatement of a
    # deterministic fact -- never as independent inference
    assert '"improved"' in lowered
    assert '"worsened"' in lowered
    assert '"progression"' in lowered
    assert '"regression"' in lowered
    assert '"increasing"' in lowered
    assert '"decreasing"' in lowered
    assert "never as your own independent inference" in lowered

    # explicit "prose conversion only, not clinical reasoning" instruction
    assert "your only job is to convert the deterministic comparison facts" in lowered
    assert "not performing clinical reasoning" in lowered


def test_both_report_contents_appear_fully_serialized_and_labeled():
    previous, current = _previous(), _current()
    prompt = PromptBuilder().build_comparison_prompt(_facts(), previous, current)

    assert "PREVIOUS REPORT CONTENT" in prompt
    assert "CURRENT REPORT CONTENT" in prompt
    assert previous.findings in prompt
    assert previous.impression in prompt
    assert current.findings in prompt
    assert current.impression in prompt
    # both examination/technique/clinical_history/recommendation/disclaimer fields
    # reused from the same serialization build_explanation_prompt established
    assert previous.clinical_history in prompt
    assert current.recommendation in prompt


def test_all_three_finding_categories_appear():
    facts = _facts(
        resolved=("Pneumonia", "Atelectasis"),
        persistent=("Cardiomegaly",),
        new=("Pleural Effusion",),
    )
    prompt = PromptBuilder().build_comparison_prompt(facts, _previous(), _current())

    assert "Pneumonia" in prompt
    assert "Atelectasis" in prompt
    assert "Cardiomegaly" in prompt
    assert "Pleural Effusion" in prompt
    assert "Resolved findings" in prompt
    assert "Persistent findings" in prompt
    assert "New findings" in prompt


def test_empty_finding_categories_render_explicitly_as_none_not_omitted():
    facts = _facts(resolved=(), persistent=(), new=())
    prompt = PromptBuilder().build_comparison_prompt(facts, _previous(), _current())

    assert "Resolved findings" in prompt
    assert "Persistent findings" in prompt
    assert "New findings" in prompt
    assert "(none)" in prompt


def test_days_between_studies_appears():
    facts = _facts(days=47)
    prompt = PromptBuilder().build_comparison_prompt(facts, _previous(), _current())
    assert "Days between studies: 47" in prompt


def test_determinism_same_inputs_produce_byte_identical_output():
    facts, previous, current = _facts(), _previous(), _current()
    first = PromptBuilder().build_comparison_prompt(facts, previous, current)
    second = PromptBuilder().build_comparison_prompt(facts, previous, current)
    assert first == second
