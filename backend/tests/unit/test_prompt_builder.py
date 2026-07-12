"""
Unit tests for PromptBuilder, per the frozen Phase 6 architecture
(development_log.md, "Phase 6 -- Prompt Builder: Architecture (FROZEN)",
"Unit testing strategy" section). Pure string-content assertions, no
collaborators to fake -- ClinicalContext/EvidenceSummary are constructed
directly rather than via ContextBuilder, keeping this suite isolated to
PromptBuilder's own behavior.
"""
from __future__ import annotations

import dataclasses

from app.domain.entities import (
    ClinicalContext,
    EvidenceSummary,
    LabelEvidencePartition,
    ReportContent,
    RetrievalStats,
    RetrievedCase,
    VotedLabel,
)
from app.services.prompt_builder import NO_EVIDENCE_MESSAGE, PromptBuilder


def _case(uid, sim, findings="", impression="", labels=(), cluster_id=-1):
    return RetrievedCase(
        source_uid=uid, similarity=sim, findings=findings, impression=impression,
        labels=labels, cluster_id=cluster_id,
    )


def _stats(num_cases=0) -> RetrievalStats:
    return RetrievalStats(
        num_cases=num_cases, num_cases_after_dedup=num_cases,
        num_near_duplicates_collapsed=0, mean_similarity=0.0, min_similarity=0.0,
        max_similarity=0.0, num_unique_labels=0, num_clusters_represented=0,
    )


def _populated_context() -> ClinicalContext:
    cases = (
        _case("a", 0.9, findings="finding one", impression="impression one", labels=("Pneumonia",)),
        _case("b", 0.8, findings="finding two", impression="impression two", labels=("Pneumonia",)),
    )
    voted = (VotedLabel(label="Pneumonia", vote_weight=1.7, agreement=2 / 3),)
    partition = LabelEvidencePartition(
        label="Pneumonia", vote_weight=1.7, agreement=2 / 3,
        supporting_cases=cases, contradictory_cases=(),
    )
    evidence_summary = EvidenceSummary(
        top_retrieved_case=cases[0],
        findings_evidence=("finding one", "finding two"),
        impressions_evidence=("impression one", "impression two"),
        retrieval_stats=_stats(2),
        retrieval_metadata=None,
        label_evidence=(partition,),
    )
    return ClinicalContext(retrieved_cases=cases, voted_labels=voted, evidence_summary=evidence_summary)


def _empty_context() -> ClinicalContext:
    evidence_summary = EvidenceSummary(
        top_retrieved_case=None, findings_evidence=(), impressions_evidence=(),
        retrieval_stats=_stats(0), retrieval_metadata=None, label_evidence=(),
    )
    return ClinicalContext(retrieved_cases=(), voted_labels=(), evidence_summary=evidence_summary)


def test_schema_instruction_lists_all_seven_report_content_fields():
    prompt = PromptBuilder().build_generation_prompt(_populated_context(), "en")
    real_field_names = [f.name for f in dataclasses.fields(ReportContent)]
    assert len(real_field_names) == 7
    for field_name in real_field_names:
        assert f'"{field_name}"' in prompt


def test_language_instruction_reflects_en_and_bn():
    ctx = _populated_context()
    prompt_en = PromptBuilder().build_generation_prompt(ctx, "en")
    prompt_bn = PromptBuilder().build_generation_prompt(ctx, "bn")
    assert "Respond in English." in prompt_en
    assert "Respond in Bengali" in prompt_bn
    assert "Respond in English." not in prompt_bn
    assert "Respond in Bengali" not in prompt_en


def test_grounding_instruction_present():
    prompt = PromptBuilder().build_generation_prompt(_populated_context(), "en")
    assert "GROUNDING INSTRUCTIONS" in prompt
    assert "Do not invent, infer, or hallucinate" in prompt


def test_output_only_json_no_markdown_instruction_present():
    prompt = PromptBuilder().build_generation_prompt(_populated_context(), "en")
    assert "ONLY a single JSON object" in prompt
    assert "markdown code fences" in prompt


def test_top_label_agreement_value_appears_rounded_in_prompt():
    ctx = _populated_context()
    prompt = PromptBuilder().build_generation_prompt(ctx, "en")
    top_label = ctx.voted_labels[0]
    rounded = f"{top_label.agreement:.2f}"
    assert rounded == "0.67"
    assert rounded in prompt
    # full, unrounded precision must NOT leak into the prompt
    assert str(top_label.agreement) not in prompt


def test_all_findings_and_impressions_evidence_entries_appear_in_output():
    ctx = _populated_context()
    prompt = PromptBuilder().build_generation_prompt(ctx, "en")
    for text in ctx.evidence_summary.findings_evidence:
        assert text in prompt
    for text in ctx.evidence_summary.impressions_evidence:
        assert text in prompt


def test_empty_evidence_summary_produces_no_evidence_message_without_raising():
    prompt = PromptBuilder().build_generation_prompt(_empty_context(), "en")
    assert NO_EVIDENCE_MESSAGE in prompt
    # still fully-formed: schema/grounding sections still present, no crash
    assert "GROUNDING INSTRUCTIONS" in prompt
    assert '"examination"' in prompt


def test_none_evidence_summary_produces_no_evidence_message_without_raising():
    ctx = ClinicalContext(retrieved_cases=(), voted_labels=(), evidence_summary=None)
    prompt = PromptBuilder().build_generation_prompt(ctx, "en")
    assert NO_EVIDENCE_MESSAGE in prompt


def test_build_retry_prompt_includes_previous_response_and_validation_errors_verbatim():
    ctx = _populated_context()
    previous_response = '{"examination": "chest x-ray"}'
    validation_errors = ["missing required field: impression", "findings must not be empty"]

    prompt = PromptBuilder().build_retry_prompt(ctx, "en", previous_response, validation_errors)

    assert previous_response in prompt
    for error in validation_errors:
        assert error in prompt
    # re-includes full schema/grounding context, not just an isolated error message
    assert "GROUNDING INSTRUCTIONS" in prompt
    assert '"examination"' in prompt
    assert "please try again" not in prompt.lower()


def test_build_retry_prompt_with_no_validation_errors_uses_fallback_text():
    prompt = PromptBuilder().build_retry_prompt(_populated_context(), "en", "some response", [])
    assert "(no specific validation errors provided)" in prompt


def test_determinism_same_inputs_produce_byte_identical_generation_prompt():
    ctx = _populated_context()
    first = PromptBuilder().build_generation_prompt(ctx, "en")
    second = PromptBuilder().build_generation_prompt(ctx, "en")
    assert first == second


def test_determinism_same_inputs_produce_byte_identical_retry_prompt():
    ctx = _populated_context()
    errors = ["missing required field: impression"]
    first = PromptBuilder().build_retry_prompt(ctx, "en", "prev", errors)
    second = PromptBuilder().build_retry_prompt(ctx, "en", "prev", errors)
    assert first == second
