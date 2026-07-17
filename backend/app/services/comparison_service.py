"""
app/services/comparison_service.py
====================================================================
Implements the Phase 11 longitudinal-comparison use case: resolves the
previous/current report pair for a patient, runs the deterministic
finding-diff, narrates it via the LLM, and persists the exchange. Pure
sequencing over its injected collaborators -- no business/clinical logic
of its own, same discipline as ExplainabilityService (Phase 10).

Previous-report resolution, stated explicitly: when compare_against_report_id
is NOT supplied, "most recent prior" is resolved by calling
PatientService.get_history() (via the injected IPatientRepository) --
reusing the same chronological join it already performs, rather than a
second, independently-written history query -- filtering out
current_report_id, then taking the last (most recent) remaining entry
(get_history() returns ascending chronological order). Whichever report_id
is resolved this way, the actual ReportRecord row (needed for report_date
and ai_content, neither of which the Report domain entity from
get_history() alone is sufficient for -- report_date is not one of its
fields) is then fetched the same way current_report_id's own row is, via
the shared _fetch_report_record() helper -- one lookup path regardless of
how the previous report's identity was determined.

report_date (not created_at) is the date passed into
DeterministicComparator.compare() -- report_date is the frozen per-report
clinical/study date (Phase 8), while created_at is a persistence
timestamp used elsewhere (PatientService.get_history()'s chronological
ordering) for a different purpose.

Both ReportRecord reconstructions reuse build_report_domain_entity()
(Phase 10/11's shared helper) rather than a second reconstruction path,
per Step 8's explicit instruction.

Exception design (see app/services/exceptions.py's module docstring for
the full reasoning): a malformed/nonexistent report_id (current OR
compare_against) raises ReportNotFoundError, reused from Phase 10 since
it's the identical failure mode against the identical table. A patient
with no prior report at all (first visit, no compare_against_report_id
given) raises the new NoPriorReportError instead -- not a failed lookup,
simply no candidate to look up.

current_doctor_id (Phase 13, additive): the creating doctor becomes this
comparison's owner, per phase13_auth_architecture.md's "creating a
brand-new comparison makes the creating doctor its owner automatically --
there is no 'assign ownership' action" decision. No ownership CHECK is
performed here -- any authenticated doctor may create a comparison
against any shared patient's reports (read/creation are universal per
that same frozen doc); this parameter only tags who did.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.entities import Comparison
from app.domain.interfaces import IDeterministicComparator, ILLMOrchestrator, IPatientRepository, IPromptBuilder
from app.models.comparison import ComparisonRecord
from app.models.report import ReportRecord
from app.services.exceptions import NoPriorReportError, ReportNotFoundError
from app.services.report_reconstruction import build_report_domain_entity


class ComparisonService:
    def __init__(
        self,
        db: Session,
        patient_repository: IPatientRepository,
        deterministic_comparator: IDeterministicComparator,
        prompt_builder: IPromptBuilder,
        llm_orchestrator: ILLMOrchestrator,
    ) -> None:
        self._db = db
        self._patient_repository = patient_repository
        self._deterministic_comparator = deterministic_comparator
        self._prompt_builder = prompt_builder
        self._llm_orchestrator = llm_orchestrator

    def compare(
        self,
        patient_id: str,
        current_report_id: str,
        compare_against_report_id: str | None = None,
        current_doctor_id: str | None = None,
    ) -> Comparison:
        current_record = self._fetch_report_record(current_report_id)
        current_report = build_report_domain_entity(current_record)

        previous_record = self._resolve_previous_record(
            patient_id, current_report_id, compare_against_report_id
        )
        previous_report = build_report_domain_entity(previous_record)

        facts = self._deterministic_comparator.compare(
            previous_report.ai_content,
            current_report.ai_content,
            previous_record.report_date,
            current_record.report_date,
            str(previous_record.id),
            str(current_record.id),
        )

        prompt = self._prompt_builder.build_comparison_prompt(
            facts, previous_report.ai_content, current_report.ai_content
        )
        narrative = self._llm_orchestrator.answer_question(prompt)

        comparison_record = ComparisonRecord(
            patient_id=uuid.UUID(patient_id),
            previous_report_id=previous_record.id,
            current_report_id=current_record.id,
            deterministic_facts=asdict(facts),
            llm_narrative=narrative,
            doctor_id=uuid.UUID(current_doctor_id) if current_doctor_id is not None else None,
        )
        self._db.add(comparison_record)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        return Comparison(
            id=str(comparison_record.id),
            patient_id=patient_id,
            previous_report_id=str(previous_record.id),
            current_report_id=str(current_record.id),
            facts=facts,
            narrative=narrative,
            created_at=(
                comparison_record.created_at.isoformat()
                if comparison_record.created_at
                else datetime.now(timezone.utc).isoformat()
            ),
        )

    def _resolve_previous_record(
        self, patient_id: str, current_report_id: str, compare_against_report_id: str | None
    ) -> ReportRecord:
        if compare_against_report_id is not None:
            return self._fetch_report_record(compare_against_report_id)

        history = self._patient_repository.get_history(patient_id)
        prior = [report for report in history if report.id != current_report_id]
        if not prior:
            raise NoPriorReportError(
                f"patient_id={patient_id} has no prior report to compare "
                f"current_report_id={current_report_id} against"
            )
        most_recent_prior = prior[-1]  # get_history() is ascending chronological order
        return self._fetch_report_record(most_recent_prior.id)

    def _fetch_report_record(self, report_id: str) -> ReportRecord:
        # Same Uuid-typed-column lesson as Phase 8 Step 6/Phase 10: parse
        # once, raise a clean, specific error for both "malformed" and
        # "missing" rather than letting a raw ValueError/None propagate.
        try:
            report_uuid = uuid.UUID(report_id)
        except ValueError:
            raise ReportNotFoundError(f"report_id is not a valid UUID: {report_id!r}") from None

        record = self._db.query(ReportRecord).filter(ReportRecord.id == report_uuid).one_or_none()
        if record is None:
            raise ReportNotFoundError(f"no ReportRecord found for report_id={report_id}")
        return record
