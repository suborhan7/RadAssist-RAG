"""
app/services/report_reconstruction.py
====================================================================
Shared helper: reconstructs the frozen Report domain entity from a
persisted ReportRecord row. Extracted from ExplainabilityService (Phase
10) so ExplainabilityService and PatientService (Phase 11) call the exact
same reconstruction logic rather than maintaining two, potentially-
drifting copies -- same "one shared implementation" discipline as Phase
9's reconstruct_session_evidence() extraction.

ai_draft_content/final_content were both persisted via
dataclasses.asdict(ReportContent instance) -- exactly the 7 field names
ReportContent expects -- so ReportContent(**dict) round-trips each of
them directly.

study_id substitution, documented rather than silently populated: the
frozen Report entity predates this system's actual persistence model and
expects a study_id (a studies table that, per CLAUDE.md, does not exist
in this codebase). report.study_id is populated with
str(ReportRecord.session_id) instead -- the closest real identifier this
system actually has for "what this report is about" -- since nothing else
is available and leaving it silently wrong would be worse than
documenting the substitution. `evidence` is left at its empty default
(no caller of this helper currently needs it repopulated).

Phase 17: final_content is now populated from the real, persisted column
(previously always ReportContent(), an empty placeholder, since no
doctor-edit workflow existed to write anything else). ComparisonService
now reads final_content off the returned Report ("what does this report
currently say" -- explicit user decision, resolved before Step 6).
ExplainabilityService's PromptBuilder call site still reads
ai_draft_content, pending confirmation of that call site's real usage
(explanation-chat grounding) before applying the same switch there --
see prompt_builder.py's own Phase 17 note.
"""
from __future__ import annotations

from app.domain.entities import Language, Report, ReportContent
from app.models.report import ReportRecord


def build_report_domain_entity(report_record: ReportRecord) -> Report:
    return Report(
        id=str(report_record.id),
        study_id=str(report_record.session_id),
        language=Language(report_record.language),
        status=report_record.status,
        ai_draft_content=ReportContent(**report_record.ai_draft_content),
        final_content=ReportContent(**report_record.final_content),
        created_at=report_record.created_at,
        updated_at=report_record.updated_at,
    )
