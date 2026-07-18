"""
app/services/report_detail_service.py
====================================================================
Implements the Phase 12 report-detail use case: given a report_id,
reconstructs everything the frontend's Radiologist Workspace page needs
to render -- report content, the patient this report belongs to (if any),
validation warnings, generation metadata, and the real retrieved evidence
that originally justified the report (for the evidence accordion).

A real gap, not a speculative feature: no endpoint existed anywhere that
could answer "get this report's full detail from just its report_id" --
POST /generate-report's response is scoped to the generation moment
itself, not persisted for later re-fetch, and no other route returns a
report's content plus its evidence together. Found while building Phase
12 Step 5, confirmed via a plain grep across every route file before
writing any code.

Reuses two existing helpers rather than a third/fourth reconstruction
path: build_report_domain_entity() (Phase 10, for ai_draft_content/
final_content/language/status) and reconstruct_session_evidence()
(Phase 9, for both the retrieved evidence AND -- new use of an existing
return value -- the
RetrievalSession itself, whose patient_id is the only real path from a
report_id to the patient it belongs to; Phase 11 never added a
ReportRecord.patient_id column, only retrieval_sessions.patient_id).

validation_warnings/llm_model/etc. are read directly off the persisted
ReportRecord row -- these were never part of the Report domain entity,
only ever part of Phase 8's reports table schema.

Malformed OR missing report_id both raise ReportNotFoundError, matching
Phase 10's ExplainabilityService precedent for this exact resource
(deliberately NOT the same 400-malformed/404-missing split app/api/patients.py
uses for a different resource) -- consistency is scoped to what's already
established for "reports," not blanket-copied from "patients."
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domain.entities import ReportContent, ReportStatus, RetrievedCase
from app.domain.interfaces import ILabelVoter, IVectorStore
from app.models.report import ReportRecord
from app.models.report_audit_log import ReportAuditLog
from app.services.exceptions import ReportNotFoundError
from app.services.report_reconstruction import build_report_domain_entity
from app.services.session_reconstruction import reconstruct_session_evidence


@dataclass(frozen=True)
class ReportAuditLogEntry:
    """Phase 17 Step 6: one row per successful edit. Defined locally here,
    not in app/domain/entities.py -- like ReportDetail itself below, this
    is a read-projection assembled for this one use case, not a value
    returned by a mutation elsewhere (contrast ExplanationRecord/Comparison,
    which ARE domain entities because they're each a mutation's own return
    value)."""

    id: str
    doctor_id: str
    action: str
    at: str


@dataclass(frozen=True)
class ReportDetail:
    report_id: str
    session_id: str
    patient_id: str | None
    content: ReportContent
    # Phase 17 Step 6: the immutable AI draft, additive -- for the
    # frontend's "Restore AI Draft" action.
    ai_draft_content: ReportContent
    language: str
    status: ReportStatus
    validation_warnings: tuple[str, ...]
    llm_model: str
    llm_temperature: float
    embedding_model: str
    embedding_version: str
    collection_name: str
    report_date: str
    created_at: str
    retrieved_cases: tuple[RetrievedCase, ...]
    # Phase 15: a report's owner is derived via session.doctor_id, per
    # phase13_auth_architecture.md's "reports has no doctor_id of its
    # own" decision -- this is that derived value, not a new column.
    doctor_id: str | None = None
    # Phase 17 Step 6: nullable -- only set once a report has actually
    # been finalized.
    finalized_at: str | None = None
    finalized_by: str | None = None
    audit_log: tuple[ReportAuditLogEntry, ...] = ()


class ReportDetailService:
    def __init__(self, db: Session, vector_store: IVectorStore, label_voting_service: ILabelVoter) -> None:
        self._db = db
        self._vector_store = vector_store
        self._label_voting_service = label_voting_service

    def get_report_detail(self, report_id: str) -> ReportDetail:
        try:
            report_uuid = uuid.UUID(report_id)
        except ValueError:
            raise ReportNotFoundError(f"report_id is not a valid UUID: {report_id!r}") from None

        record = self._db.query(ReportRecord).filter(ReportRecord.id == report_uuid).one_or_none()
        if record is None:
            raise ReportNotFoundError(f"no ReportRecord found for report_id={report_id}")

        report = build_report_domain_entity(record)
        retrieval_session, retrieved_cases, _voted_labels = reconstruct_session_evidence(
            self._db, self._vector_store, self._label_voting_service, str(record.session_id)
        )

        audit_rows = (
            self._db.query(ReportAuditLog)
            .filter(ReportAuditLog.report_id == record.id)
            .order_by(ReportAuditLog.at)
            .all()
        )

        return ReportDetail(
            report_id=str(record.id),
            session_id=str(record.session_id),
            patient_id=str(retrieval_session.patient_id) if retrieval_session.patient_id else None,
            # Phase 17: "what does this report currently say" reads
            # final_content (the doctor's current, possibly-edited
            # version), not the immutable AI draft -- explicit user
            # decision, resolved before this step.
            content=report.final_content,
            ai_draft_content=report.ai_draft_content,
            language=report.language.value,
            status=report.status,
            validation_warnings=tuple(record.validation_warnings),
            llm_model=record.llm_model,
            llm_temperature=record.llm_temperature,
            embedding_model=record.embedding_model,
            embedding_version=record.embedding_version,
            collection_name=record.collection_name,
            report_date=record.report_date,
            created_at=report.created_at.isoformat() if report.created_at else "",
            retrieved_cases=tuple(retrieved_cases),
            doctor_id=str(retrieval_session.doctor_id) if retrieval_session.doctor_id else None,
            finalized_at=record.finalized_at.isoformat() if record.finalized_at else None,
            finalized_by=str(record.finalized_by) if record.finalized_by else None,
            audit_log=tuple(
                ReportAuditLogEntry(
                    id=str(row.id), doctor_id=str(row.doctor_id), action=row.action,
                    at=row.at.isoformat() if row.at else "",
                )
                for row in audit_rows
            ),
        )
