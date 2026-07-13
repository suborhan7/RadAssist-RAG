"""
app/services/prompt_builder.py
====================================================================
Implements IPromptBuilder. Transforms a ClinicalContext (Phase 5's output)
into a deterministic prompt string for a specific language, per the frozen
Phase 6 architecture (development_log.md, "Phase 6 -- Prompt Builder:
Architecture (FROZEN)"). Pure text construction only -- no LLM calls, no
response parsing, no report formatting, no clinical judgment.

build_generation_prompt, build_retry_prompt, and (as of Phase 10)
build_explanation_prompt are implemented here. build_translation_prompt
(permanently unimplemented per the frozen spec -- bilingual output is
produced by the LLM generating directly in the target language via the
`language` parameter, not a separate translation pass) is intentionally
absent from this class; IPromptBuilder is a Protocol, not an ABC, so this
class is not required to implement every method on it, only the ones a
given caller actually invokes.

build_explanation_prompt reuses _evidence_section (the exact same
deterministic evidence serialization build_generation_prompt already
uses) rather than a second, divergent copy -- same "one shared
serialization" discipline as every prior phase's reuse decisions.

Determinism: every prompt is a pure function of its arguments -- no
timestamps, no wall-clock reads, no random ordering. ClinicalContext's
collections are already deterministically ordered by Phase 5; this module
only serializes in the given order, never re-sorts.
"""
from __future__ import annotations

from app.domain.entities import ClinicalContext, EvidenceSummary, Report, ReportContent, VotedLabel

REPORT_CONTENT_FIELDS = (
    "examination",
    "clinical_history",
    "technique",
    "findings",
    "impression",
    "recommendation",
    "disclaimer",
)

NO_EVIDENCE_MESSAGE = "No retrieved evidence is available for this case."

_LANGUAGE_INSTRUCTIONS = {
    "en": "Respond in English.",
    "bn": "Respond in Bengali (বাংলা).",
}


class PromptBuilder:
    """Satisfies domain.interfaces.IPromptBuilder (partially -- see module docstring)."""

    def build_generation_prompt(self, context: ClinicalContext, language: str) -> str:
        sections = [
            self._role_instruction(),
            self._language_instruction(language),
            self._schema_instruction(),
            self._grounding_instruction(),
            self._confidence_instruction(context.voted_labels),
            self._evidence_section(context.evidence_summary),
        ]
        # Phase 9 fix: questionnaire_answers/clinical_notes existed on
        # ClinicalContext since Phase 5 but were never serialized into the
        # prompt -- silently accepted, never read. Both sections are
        # conditionally included ONLY when there's real content, so the
        # empty-fixture case every test since Phase 6 has exercised is
        # byte-identical to before this fix (see
        # test_empty_questionnaire_and_notes_produce_byte_identical_prompt).
        if context.questionnaire_answers:
            sections.append(self._questionnaire_section(context.questionnaire_answers))
        if context.clinical_notes.strip():
            sections.append(self._clinical_notes_section(context.clinical_notes))
        sections.append("Now generate the JSON report.")
        return "\n\n".join(sections)

    def build_retry_prompt(
        self,
        context: ClinicalContext,
        language: str,
        previous_response: str,
        validation_errors: list[str],
    ) -> str:
        base_prompt = self.build_generation_prompt(context, language)
        errors_block = (
            "\n".join(f"- {error}" for error in validation_errors)
            if validation_errors
            else "(no specific validation errors provided)"
        )
        retry_section = (
            "---\n"
            "RETRY INSTRUCTIONS:\n"
            "Your previous response failed validation and could not be accepted. "
            "You must correct every issue listed below and output a new, complete, "
            "valid JSON object following all the instructions above exactly. Do not "
            "repeat the same mistakes.\n\n"
            "PREVIOUS RESPONSE (rejected):\n"
            f"{previous_response}\n\n"
            "VALIDATION ERRORS (must all be fixed):\n"
            f"{errors_block}"
        )
        return f"{base_prompt}\n\n{retry_section}"

    def build_explanation_prompt(
        self, report: Report, question: str, evidence_summary: EvidenceSummary | None
    ) -> str:
        sections = [
            self._explanation_role_instruction(),
            self._report_content_section(report.ai_content),
            self._evidence_section(evidence_summary),
            self._explanation_grounding_instruction(),
            self._question_section(question),
        ]
        return "\n\n".join(sections)

    @staticmethod
    def _explanation_role_instruction() -> str:
        return (
            "You are an AI radiology assistant answering a clinician's question "
            "about a previously generated chest X-ray report."
        )

    @staticmethod
    def _report_content_section(content: ReportContent) -> str:
        return (
            "REPORT CONTENT:\n"
            f"Examination: {content.examination}\n"
            f"Clinical History: {content.clinical_history}\n"
            f"Technique: {content.technique}\n"
            f"Findings: {content.findings}\n"
            f"Impression: {content.impression}\n"
            f"Recommendation: {content.recommendation}\n"
            f"Disclaimer: {content.disclaimer}"
        )

    @staticmethod
    def _explanation_grounding_instruction() -> str:
        # At least as strong as _grounding_instruction() above -- interactive
        # chat is a worse hallucination surface than one-shot generation (a
        # clinician can ask leading questions), so this adds an explicit
        # "never introduce a new diagnosis" clause and a mandatory fallback
        # sentence for out-of-scope questions, both stronger than the plain
        # "do not include it" of the generation-time instruction.
        return (
            "GROUNDING INSTRUCTIONS:\n"
            "You must answer ONLY using the report content and evidence provided "
            "above. Do not invent, infer, or introduce any new diagnosis, finding, "
            "measurement, or clinical detail that is not already present in the "
            "report content or the evidence above. If the question asks about "
            "something the report content and evidence above do not address, you "
            "MUST explicitly state that the available evidence does not address "
            "this question, rather than speculating or guessing."
        )

    @staticmethod
    def _question_section(question: str) -> str:
        return f"QUESTION:\n{question}"

    @staticmethod
    def _role_instruction() -> str:
        return (
            "You are an AI radiology assistant generating a structured chest "
            "X-ray report."
        )

    @staticmethod
    def _language_instruction(language: str) -> str:
        instruction = _LANGUAGE_INSTRUCTIONS.get(
            language, f"Respond in the language identified by the code '{language}'."
        )
        return f"LANGUAGE INSTRUCTIONS:\n{instruction}"

    @staticmethod
    def _schema_instruction() -> str:
        field_lines = "\n".join(f'  "{name}": "<string>",' for name in REPORT_CONTENT_FIELDS)
        # trim the trailing comma on the final field so the example reads as valid JSON
        field_lines = field_lines.rsplit(",", 1)[0] if field_lines.endswith(",") else field_lines
        return (
            "OUTPUT FORMAT INSTRUCTIONS:\n"
            "You must output ONLY a single JSON object and nothing else. Do not "
            "wrap the JSON in markdown code fences (no ``` characters), and do not "
            "include any explanation, preamble, or trailing text outside the JSON "
            "object. The JSON object must contain exactly these 7 string fields, in "
            "this shape:\n"
            "{\n"
            f"{field_lines}\n"
            "}"
        )

    @staticmethod
    def _grounding_instruction() -> str:
        return (
            "GROUNDING INSTRUCTIONS:\n"
            "You must base your report ONLY on the evidence provided below. Do not "
            "invent, infer, or hallucinate any finding, measurement, or clinical "
            "detail that is not directly supported by the evidence below. If the "
            "evidence is insufficient to support a finding, do not include it."
        )

    @staticmethod
    def _confidence_instruction(voted_labels: tuple[VotedLabel, ...]) -> str:
        if not voted_labels:
            return (
                "CONFIDENCE / UNCERTAINTY INSTRUCTIONS:\n"
                "No label-voting evidence is available for this case. Do not state "
                "any diagnosis with certainty; express appropriate clinical "
                "uncertainty throughout."
            )
        top_label = voted_labels[0]
        return (
            "CONFIDENCE / UNCERTAINTY INSTRUCTIONS:\n"
            f'The top candidate label from retrieval-based voting is "{top_label.label}" '
            f"with an agreement score of {top_label.agreement:.2f} (the fraction of "
            "retrieved neighbor cases agreeing on this label). If this agreement "
            "score is low, you MUST express appropriate clinical uncertainty in your "
            "findings and impression rather than false certainty. Do not state a "
            "diagnosis as certain when the agreement score is low."
        )

    @staticmethod
    def _evidence_section(evidence_summary: EvidenceSummary | None) -> str:
        if evidence_summary is None or (
            not evidence_summary.findings_evidence
            and not evidence_summary.impressions_evidence
            and not evidence_summary.label_evidence
        ):
            return f"EVIDENCE:\n{NO_EVIDENCE_MESSAGE}"

        lines = ["EVIDENCE:"]

        lines.append("Retrieved findings from similar cases (most similar first):")
        if evidence_summary.findings_evidence:
            for i, text in enumerate(evidence_summary.findings_evidence, start=1):
                lines.append(f"{i}. {text}")
        else:
            lines.append("(none provided)")

        lines.append("")
        lines.append("Retrieved impressions from similar cases (most similar first):")
        if evidence_summary.impressions_evidence:
            for i, text in enumerate(evidence_summary.impressions_evidence, start=1):
                lines.append(f"{i}. {text}")
        else:
            lines.append("(none provided)")

        lines.append("")
        lines.append("Label evidence (top voted label partition):")
        if evidence_summary.label_evidence:
            partition = evidence_summary.label_evidence[0]
            lines.append(f"- Label: {partition.label}")
            lines.append(f"- Vote weight: {partition.vote_weight:.2f}")
            lines.append(f"- Agreement: {partition.agreement:.2f}")
            lines.append(f"- Supporting cases: {len(partition.supporting_cases)}")
            lines.append(f"- Contradictory cases: {len(partition.contradictory_cases)}")
        else:
            lines.append("(none)")

        return "\n".join(lines)

    @staticmethod
    def _questionnaire_section(questionnaire_answers: dict[str, str]) -> str:
        lines = ["CLINICAL QUESTIONNAIRE:"]
        for key in sorted(questionnaire_answers):
            lines.append(f"- {key}: {questionnaire_answers[key]}")
        return "\n".join(lines)

    @staticmethod
    def _clinical_notes_section(clinical_notes: str) -> str:
        return f"ADDITIONAL CLINICAL NOTES:\n{clinical_notes}"
