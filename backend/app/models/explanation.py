"""
app/models/explanation.py
====================================================================
explanations: one row per POST /reports/{report_id}/explain call (Phase 10
DB scope -- see the frozen architecture's "Database (explanations table)"
section). FK to `reports.id` -- a DIFFERENT parent table than every prior
FK in this schema (`retrieved_evidence.session_id` and `reports.session_id`
both point at `retrieval_sessions.id`; this is the first FK that points at
`reports` instead). Double-checked deliberately, not assumed by pattern-
matching against the prior two FKs.

Naming note: named `Explanation` (matching the filename-to-classname
convention every other model follows) rather than `ExplanationRecord` --
the frozen domain entity is `ExplanationRecord`, a different name, so
there is no Report/ReportRecord-style collision here to avoid.

doctor_id (Phase 13, additive): nullable FK to doctors.id -- the doctor
who created this explanation, per phase13_auth_architecture.md's frozen
"ownership attaches to the work" decision (creation only; reads stay
universal).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.report import ReportRecord


class Explanation(Base):
    __tablename__ = "explanations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reports.id"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(String, nullable=False)
    answer: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("doctors.id"), nullable=True, index=True
    )

    report: Mapped["ReportRecord"] = relationship()
