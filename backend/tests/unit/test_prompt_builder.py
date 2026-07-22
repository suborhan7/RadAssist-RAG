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
    Language,
    LabelEvidencePartition,
    Report,
    ReportContent,
    ReportStatus,
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
        assert f"###{field_name.upper()}###" in prompt


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


def test_output_only_markers_no_json_no_markdown_instruction_present():
    """Delimiter-marker format, not JSON -- changed after Phase 20's real
    generation-quality evaluation traced all 17 real content-validation
    failures to the same JSON-escaping bug at the disclaimer field
    (development_log.md, "Finding: All 17 Generation Failures Share One
    Root Cause")."""
    prompt = PromptBuilder().build_generation_prompt(_populated_context(), "en")
    assert "Do NOT use JSON" in prompt
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
    assert "###EXAMINATION###" in prompt


def test_none_evidence_summary_produces_no_evidence_message_without_raising():
    ctx = ClinicalContext(retrieved_cases=(), voted_labels=(), evidence_summary=None)
    prompt = PromptBuilder().build_generation_prompt(ctx, "en")
    assert NO_EVIDENCE_MESSAGE in prompt


def test_build_retry_prompt_includes_previous_response_and_validation_errors_verbatim():
    ctx = _populated_context()
    previous_response = "###EXAMINATION###\nchest x-ray"
    validation_errors = ["missing required field marker: ###IMPRESSION###", "findings must not be empty"]

    prompt = PromptBuilder().build_retry_prompt(ctx, "en", previous_response, validation_errors)

    assert previous_response in prompt
    for error in validation_errors:
        assert error in prompt
    # re-includes full schema/grounding context, not just an isolated error message
    assert "GROUNDING INSTRUCTIONS" in prompt
    assert "###EXAMINATION###" in prompt
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


def test_empty_questionnaire_and_notes_produce_byte_identical_prompt():
    """The required Phase 9 regression test: _populated_context() has the
    same empty questionnaire_answers={}/clinical_notes="" every test since
    Phase 6 has used. `expected` is reconstructed independently from the
    same six unchanged private helpers build_generation_prompt always
    called, joined the same way -- proving the Phase 9 fix is a byte-exact
    no-op for this case, not just "the new section headers are absent."
    """
    ctx = _populated_context()
    pb = PromptBuilder()
    actual = pb.build_generation_prompt(ctx, "en")

    expected = "\n\n".join([
        pb._role_instruction(),
        pb._language_instruction("en"),
        pb._schema_instruction(),
        pb._grounding_instruction(),
        pb._confidence_instruction(ctx.voted_labels),
        pb._evidence_section(ctx.evidence_summary),
        "Now generate the report using the field markers above.",
    ])

    assert actual == expected
    assert "CLINICAL QUESTIONNAIRE" not in actual
    assert "ADDITIONAL CLINICAL NOTES" not in actual


def test_questionnaire_answers_included_and_sorted_alphabetically_by_key():
    ctx = dataclasses.replace(
        _populated_context(),
        questionnaire_answers={"fever": "yes", "duration": "3 days", "cough": "dry"},
    )
    prompt = PromptBuilder().build_generation_prompt(ctx, "en")

    assert "CLINICAL QUESTIONNAIRE:" in prompt
    assert "- cough: dry" in prompt
    assert "- duration: 3 days" in prompt
    assert "- fever: yes" in prompt

    section = prompt.split("CLINICAL QUESTIONNAIRE:")[1].split("\n\n")[0]
    assert section.index("cough") < section.index("duration") < section.index("fever")


def test_clinical_notes_included_when_non_empty():
    ctx = dataclasses.replace(_populated_context(), clinical_notes="Patient reports recent travel")
    prompt = PromptBuilder().build_generation_prompt(ctx, "en")
    assert "ADDITIONAL CLINICAL NOTES:" in prompt
    assert "Patient reports recent travel" in prompt


def test_whitespace_only_clinical_notes_not_included():
    ctx = dataclasses.replace(_populated_context(), clinical_notes="   \n\t  ")
    prompt = PromptBuilder().build_generation_prompt(ctx, "en")
    assert "ADDITIONAL CLINICAL NOTES" not in prompt


def test_empty_questionnaire_dict_not_included():
    ctx = dataclasses.replace(_populated_context(), questionnaire_answers={})
    prompt = PromptBuilder().build_generation_prompt(ctx, "en")
    assert "CLINICAL QUESTIONNAIRE" not in prompt


def test_build_retry_prompt_carries_questionnaire_and_notes_through():
    """Verified by reading build_retry_prompt's actual implementation (it
    calls build_generation_prompt with the same context), not assumed --
    this test proves that reading is correct."""
    ctx = dataclasses.replace(
        _populated_context(),
        questionnaire_answers={"duration": "3 days"},
        clinical_notes="Patient reports recent travel",
    )
    prompt = PromptBuilder().build_retry_prompt(ctx, "en", "bad json", ["missing field: impression"])
    assert "CLINICAL QUESTIONNAIRE:" in prompt
    assert "- duration: 3 days" in prompt
    assert "ADDITIONAL CLINICAL NOTES:" in prompt
    assert "Patient reports recent travel" in prompt


# --- Phase 10: build_explanation_prompt ---


def _report() -> Report:
    # ai_draft_content and final_content are deliberately DIFFERENT here
    # (not just one populated/one empty) so the assertions below can prove
    # which field build_explanation_prompt actually reads, per Phase 17's
    # pre-Step-6 resolution: explanation chat grounds its answer in
    # final_content (what the report currently says, including any
    # doctor edits), never the immutable ai_draft_content.
    draft_content = ReportContent(
        examination="Chest X-ray", clinical_history="Cough", technique="PA view",
        findings="Right upper lobe opacity.", impression="Findings concerning for pneumonia.",
        recommendation="Clinical correlation, consider follow-up imaging.", disclaimer="AI-generated draft",
    )
    final_content = ReportContent(
        examination="Chest X-ray", clinical_history="Cough", technique="PA view",
        findings="Right upper lobe opacity, doctor-confirmed.", impression="Consistent with early pneumonia.",
        recommendation="Start antibiotics, repeat imaging in 2 weeks.", disclaimer="AI-generated draft",
    )
    return Report(
        id="r1", study_id="s1", language=Language.ENGLISH, status=ReportStatus.DOCTOR_EDITED,
        ai_draft_content=draft_content, final_content=final_content,
    )


def test_explanation_grounding_instruction_present_and_at_least_as_strong():
    prompt = PromptBuilder().build_explanation_prompt(_report(), "Why?", _empty_context().evidence_summary)
    assert "GROUNDING INSTRUCTIONS" in prompt
    # required-strength clauses per the frozen spec, none of which are in
    # build_generation_prompt's own grounding instruction -- a strictly
    # stronger requirement, not just "a" grounding instruction
    assert "do not invent, infer, or introduce any new diagnosis" in prompt.lower()
    assert "evidence does not address this question" in prompt.lower()


def test_explanation_report_content_appears_in_output():
    report = _report()
    prompt = PromptBuilder().build_explanation_prompt(report, "Why?", _empty_context().evidence_summary)
    assert report.final_content.findings in prompt
    assert report.final_content.impression in prompt
    assert report.final_content.recommendation in prompt
    # proves final_content, not the immutable ai_draft_content, is what
    # actually gets grounded into the prompt
    assert report.ai_draft_content.findings not in prompt
    assert report.ai_draft_content.impression not in prompt


def test_explanation_evidence_appears_in_output():
    ctx = _populated_context()
    prompt = PromptBuilder().build_explanation_prompt(_report(), "Why?", ctx.evidence_summary)
    for text in ctx.evidence_summary.findings_evidence:
        assert text in prompt
    for text in ctx.evidence_summary.impressions_evidence:
        assert text in prompt


def test_explanation_question_appears_in_output():
    question = "Why do you think this is pneumonia and not just a normal finding?"
    prompt = PromptBuilder().build_explanation_prompt(_report(), question, _empty_context().evidence_summary)
    assert "QUESTION:" in prompt
    assert question in prompt


def test_explanation_prompt_determinism_same_inputs_produce_byte_identical_output():
    report = _report()
    ctx = _populated_context()
    first = PromptBuilder().build_explanation_prompt(report, "Why?", ctx.evidence_summary)
    second = PromptBuilder().build_explanation_prompt(report, "Why?", ctx.evidence_summary)
    assert first == second


# --- Phase 19: build_section_regeneration_prompt ---


def test_section_regeneration_role_and_output_instructions_mention_the_field_label():
    prompt = PromptBuilder().build_section_regeneration_prompt(_populated_context(), "en", "findings")
    assert '"Findings"' in prompt
    assert "OUTPUT FORMAT INSTRUCTIONS:" in prompt
    assert "a JSON wrapper" in prompt  # forbidding JSON, not requesting it
    # never asks for the full 7-field JSON schema -- a genuinely different
    # output contract from build_generation_prompt()
    assert "7 string fields" not in prompt


def test_section_regeneration_reuses_evidence_grounding_and_confidence_sections():
    """Same shared helpers build_generation_prompt() uses -- not a second,
    divergent copy of evidence/grounding serialization."""
    ctx = _populated_context()
    prompt = PromptBuilder().build_section_regeneration_prompt(ctx, "en", "impression")
    assert "GROUNDING INSTRUCTIONS:" in prompt
    assert "CONFIDENCE / UNCERTAINTY INSTRUCTIONS:" in prompt
    assert "EVIDENCE:" in prompt
    assert "finding one" in prompt  # real evidence text made it through
    assert "Pneumonia" in prompt  # real voted label made it through


def test_section_regeneration_questionnaire_and_notes_conditionally_included():
    ctx_without = _empty_context()
    prompt_without = PromptBuilder().build_section_regeneration_prompt(ctx_without, "en", "findings")
    assert "CLINICAL QUESTIONNAIRE:" not in prompt_without
    assert "ADDITIONAL CLINICAL NOTES:" not in prompt_without

    ctx_with = dataclasses.replace(
        _empty_context(),
        questionnaire_answers={"duration": "3 days"},
        clinical_notes="Patient reports recent travel",
    )
    prompt_with = PromptBuilder().build_section_regeneration_prompt(ctx_with, "en", "findings")
    assert "CLINICAL QUESTIONNAIRE:" in prompt_with
    assert "- duration: 3 days" in prompt_with
    assert "ADDITIONAL CLINICAL NOTES:" in prompt_with
    assert "Patient reports recent travel" in prompt_with


def test_section_regeneration_prompt_determinism_same_inputs_produce_byte_identical_output():
    ctx = _populated_context()
    first = PromptBuilder().build_section_regeneration_prompt(ctx, "en", "findings")
    second = PromptBuilder().build_section_regeneration_prompt(ctx, "en", "findings")
    assert first == second


def test_section_regeneration_prompt_differs_by_field():
    """A real, distinguishing property -- asking for 'findings' vs.
    'impression' must not produce byte-identical prompts, since the whole
    point is regenerating a SPECIFIC section."""
    ctx = _populated_context()
    findings_prompt = PromptBuilder().build_section_regeneration_prompt(ctx, "en", "findings")
    impression_prompt = PromptBuilder().build_section_regeneration_prompt(ctx, "en", "impression")
    assert findings_prompt != impression_prompt
    assert '"Findings"' in findings_prompt
    assert '"Impression"' in impression_prompt


def test_section_field_labels_keys_match_editable_report_field():
    """Consolidation proof: _SECTION_FIELD_LABELS' keys must exactly match
    EditableReportField's members -- the single canonical Python-side
    listing (app/domain/entities.py) both this dict and
    app/api/reports.py's RegenerateSectionRequest now derive from, closing
    the real duplication Phase 19 found (a fresh Literal and this dict
    independently declaring the same 5 names before consolidation). If a
    future field is ever added to EditableReportField without a matching
    label here, this test catches the drift immediately."""
    from app.domain.entities import EditableReportField
    from app.services.prompt_builder import _SECTION_FIELD_LABELS

    assert set(_SECTION_FIELD_LABELS.keys()) == set(EditableReportField)
