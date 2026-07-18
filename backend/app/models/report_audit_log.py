"""
app/models/report_audit_log.py
====================================================================
report_audit_log: one row per successful PATCH /reports/{id} edit
(Phase 17 -- phase17_finalize_edit_architecture.md Decision 11).

Append-only by convention, enforced at the service layer (INSERT only,
never UPDATE or DELETE) -- there is no DB-level immutability constraint,
same trust model as every other write path in this codebase (e.g.
nothing prevents a raw SQL UPDATE against `reports` either; correctness
here depends on every write going through the service layer, not on the
schema forbidding otherwise).

Only edits are logged here -- finalize is recorded directly on
`reports.finalized_by`/`finalized_at` instead (Decision 11's "finalize
happens at most once per report, so there's no silent-overwrite risk a
log table would need to prevent" reasoning).

No domain-entity collision to avoid here (unlike ReportRecord/Report,
PatientRecord/Patient, etc.) -- `ReportAuditLog` is a new concept with no
pre-existing frozen domain entity of any name, so this ORM model keeps
the direct, unprefixed name.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


from app.database.base import Base


class ReportAuditLog(Base):
    __tablename__ = "report_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reports.id"), nullable=False, index=True
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("doctors.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
