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
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.entities import ReportStatus
from app.models.report import ReportRecord
from app.models.report_audit_log import ReportAuditLog
from app.models.retrieval_session import RetrievalSession
from app.services.exceptions import (
    ForbiddenError,
    ReportAlreadyFinalizedError,
    ReportNotFoundError,
    ReportValidationError,
)


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
    def __init__(self, db: Session) -> None:
        self._db = db

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
