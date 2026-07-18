"""
app/services/report_edit_service.py
====================================================================
Phase 17: PATCH /reports/{id} (edit) and PATCH /reports/{id}/finalize.
A new service, not an addition to ReportGenerationService (generation-only,
Phase 8) or ReportDetailService (read-only reconstruction, Phase 12) --
edit/finalize is a third, genuinely distinct use case operating on an
already-persisted ReportRecord, not a new generation and not a read.

Ownership derivation is IDENTICAL to Phase 15's read-side derivation
(report.session_id -> retrieval_sessions.doctor_id) -- reused here for the
first real write-side check per phase13_auth_architecture.md's frozen
ownership model: any authenticated doctor may READ any report; only the
owning doctor (the one whose session produced it) may EDIT or FINALIZE it.
A mismatch raises ForbiddenError (Phase 13, defined but never used until
now) -> 403 at the API layer, never 404 (the report was found; this
doctor simply isn't allowed to write to it).

Both mutations reject an already-FINAL report the same way
(ReportAlreadyFinalizedError -> 409, see that exception's own docstring
for why one type covers both call sites).

final_content is reassigned as a brand-new dict on every update, never
mutated in place -- SQLAlchemy's JSON column type only detects changes on
reassignment, not on mutating a dict object already loaded into memory
(same "call asdict() twice, don't share a reference" discipline already
applied in ReportGenerationService.generate()).

Phase 19: regenerate_section() extends this same service (an edit-
adjacent operation, per phase19_section_regeneration_architecture.md's
own framing -- "this doesn't sit beside edit/finalize, it sits in front
of it") rather than becoming a new service. Same ownership/final-check
as update_content()/finalize(); produces a candidate ONLY, no DB write --
accepting one is just a normal PATCH /reports/{id} call with the
candidate text (Decision 1), not a new write path. Needs 5 additional
collaborators update_content()/finalize() never needed (vector_store,
label_voting_service, context_builder, llm_orchestrator, prompt_builder) -- kept
Optional with a None default specifically so those two methods' existing
callers (app/api/reports.py's PATCH routes) need no changes at all; only
the new regenerate-section route constructs this service with the full
set.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.entities import EditableReportField, ReportStatus, RetrievalMetadata
from app.domain.interfaces import (
    IContextBuilder,
    ILabelVoter,
    ILLMOrchestrator,
    IPromptBuilder,
    IVectorStore,
)
from app.models.report import ReportRecord
from app.models.report_audit_log import ReportAuditLog
from app.models.retrieval_session import RetrievalSession
from app.services.exceptions import (
    ForbiddenError,
    ReportAlreadyFinalizedError,
    ReportNotFoundError,
    ReportValidationError,
)
from app.services.session_reconstruction import reconstruct_session_evidence


def _load_report_and_owner(db: Session, report_id: str) -> tuple[ReportRecord, uuid.UUID | None]:
    try:
        report_uuid = uuid.UUID(report_id)
    except ValueError:
        raise ReportNotFoundError(f"report_id is not a valid UUID: {report_id!r}") from None

    record = db.query(ReportRecord).filter(ReportRecord.id == report_uuid).one_or_none()
    if record is None:
        raise ReportNotFoundError(f"no ReportRecord found for report_id={report_id}")

    owner_doctor_id = (
        db.query(RetrievalSession.doctor_id).filter(RetrievalSession.id == record.session_id).scalar()
    )
    return record, owner_doctor_id


def _check_ownership(owner_doctor_id: uuid.UUID | None, current_doctor_id: str) -> None:
    if owner_doctor_id is None or str(owner_doctor_id) != current_doctor_id:
        raise ForbiddenError("current doctor does not own this report")


class ReportEditService:
    def __init__(
        self,
        db: Session,
        vector_store: IVectorStore | None = None,
        label_voting_service: ILabelVoter | None = None,
        context_builder: IContextBuilder | None = None,
        llm_orchestrator: ILLMOrchestrator | None = None,
        prompt_builder: IPromptBuilder | None = None,
    ) -> None:
        self._db = db
        self._vector_store = vector_store
        self._label_voting_service = label_voting_service
        self._context_builder = context_builder
        self._llm_orchestrator = llm_orchestrator
        self._prompt_builder = prompt_builder

    def update_content(self, report_id: str, current_doctor_id: str, updates: dict[str, str]) -> ReportRecord:
        record, owner_doctor_id = _load_report_and_owner(self._db, report_id)
        _check_ownership(owner_doctor_id, current_doctor_id)

        if record.status == ReportStatus.FINAL:
            raise ReportAlreadyFinalizedError(f"report {report_id} is finalized and cannot be edited")

        record.final_content = {**record.final_content, **updates}
        record.status = ReportStatus.DOCTOR_EDITED

        self._db.add(
            ReportAuditLog(report_id=record.id, doctor_id=uuid.UUID(current_doctor_id), action="EDITED")
        )

        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        return record

    def regenerate_section(
        self, report_id: str, field: EditableReportField, current_doctor_id: str
    ) -> tuple[str, bool]:
        """Returns (candidate, context_incomplete). No DB write -- Decision
        1: nothing is persisted until the doctor accepts the candidate via
        the existing update_content() (PATCH /reports/{id}), same as any
        other edit. `field` is trusted to already be one of
        EDITABLE_REPORT_FIELDS -- validated at the Pydantic/API boundary
        (a Literal type on the request schema), not re-validated here,
        same trust boundary this project already applies to
        ReportUpdateRequest's fields."""
        record, owner_doctor_id = _load_report_and_owner(self._db, report_id)
        _check_ownership(owner_doctor_id, current_doctor_id)

        if record.status == ReportStatus.FINAL:
            raise ReportAlreadyFinalizedError(f"report {report_id} is finalized and cannot be regenerated")

        retrieval_session, retrieved_cases, voted_labels = reconstruct_session_evidence(
            self._db, self._vector_store, self._label_voting_service, str(record.session_id)
        )
        retrieval_metadata = RetrievalMetadata(
            collection_name=record.collection_name,
            embedding_model=record.embedding_model,
            embedding_version=record.embedding_version,
            retrieved_at=retrieval_session.created_at.isoformat() if retrieval_session.created_at else "",
        )

        # Phase 19 Decision 4's resolution: both columns are NULL together
        # only for reports that predate context persistence.
        # ReportGenerationService.generate() normalizes BOTH fields
        # (questionnaire_answers or {}, clinical_notes or "") on its own
        # first two lines -- a real, structural guarantee proven directly
        # by test_generate_normalizes_clinical_notes_even_if_a_caller_
        # passes_none_directly (calls generate() with clinical_notes=None
        # explicitly, bypassing the type hint, and confirms the persisted
        # value is "" not None), not merely assumed from the API layer's
        # Pydantic type. AND, not OR, is therefore the correct check here:
        # it distinguishes "both NULL together" (genuinely unknown
        # original context) from every other reachable state, including a
        # doctor's real, deliberate empty answer ({}/"" -- known, not
        # unknown). See test_report_edit_service.py's asymmetric-state
        # test for what this returns if that state is ever reached anyway
        # (pre-fix data, direct DB edits) -- not reachable through
        # generate() any more, but not left undocumented either.
        context_incomplete = record.questionnaire_answers is None and record.clinical_notes is None

        context = self._context_builder.build(
            retrieved_cases,
            voted_labels,
            questionnaire_answers=record.questionnaire_answers,
            # Step 3's real wiring finding: ContextBuilder.build() already
            # normalizes questionnaire_answers (None -> {}) itself, but has
            # NO equivalent normalization for clinical_notes -- passing a
            # None straight through would reach PromptBuilder's
            # `context.clinical_notes.strip()` and raise AttributeError.
            clinical_notes=record.clinical_notes or "",
            retrieval_metadata=retrieval_metadata,
        )
        prompt = self._prompt_builder.build_section_regeneration_prompt(context, record.language, field)
        candidate = self._llm_orchestrator.generate_freeform(prompt)
        return candidate, context_incomplete

    def finalize(self, report_id: str, current_doctor_id: str) -> ReportRecord:
        record, owner_doctor_id = _load_report_and_owner(self._db, report_id)
        _check_ownership(owner_doctor_id, current_doctor_id)

        if record.status == ReportStatus.FINAL:
            raise ReportAlreadyFinalizedError(f"report {report_id} is already finalized")

        findings = (record.final_content or {}).get("findings") or ""
        impression = (record.final_content or {}).get("impression") or ""
        if not findings.strip() or not impression.strip():
            raise ReportValidationError("findings and impression must not be empty to finalize")

        record.status = ReportStatus.FINAL
        record.finalized_at = datetime.now(timezone.utc)
        record.finalized_by = uuid.UUID(current_doctor_id)

        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        return record
