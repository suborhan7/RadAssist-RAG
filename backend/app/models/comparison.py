"""
app/models/comparison.py
====================================================================
comparisons: one row per POST /comparisons call (Phase 11 DB scope -- see
the frozen architecture's "Database" section). Three foreign keys:
patient_id -> patients.id, previous_report_id -> reports.id,
current_report_id -> reports.id -- the latter two both target the same
table, so each needs its own explicit, distinctly-named FK constraint
(SQLAlchemy/Alembic cannot infer two separate FKs to the same target table
from an unqualified ForeignKey("reports.id") on two different columns
without them being distinguishable by column, which they already are here
by attribute name).

deterministic_facts (JSON) stores asdict(ComparisonFacts) -- same
pattern as ReportRecord.ai_content storing asdict(ReportContent).

Column name is `llm_narrative` per the frozen schema, while the domain
entity's field is `narrative` (app/domain/entities.py Comparison) --
this naming difference is expected and reconciled in Step 8's
ComparisonService reconstruction helper, not a mismatch to fix here.

Naming note: named `ComparisonRecord`, not `Comparison` -- `Comparison` is
already the frozen domain entity, same Report/ReportRecord and
Patient/PatientRecord collision-avoidance precedent applied proactively.

doctor_id (Phase 13, additive): nullable FK to doctors.id -- the doctor
who created this comparison, per phase13_auth_architecture.md's frozen
"ownership attaches to the work" decision (creation only; reads stay
universal).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ComparisonRecord(Base):
    __tablename__ = "comparisons"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.id"), nullable=False, index=True
    )
    previous_report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reports.id"), nullable=False, index=True
    )
    current_report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reports.id"), nullable=False, index=True
    )
    deterministic_facts: Mapped[dict] = mapped_column(JSON, nullable=False)
    llm_narrative: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("doctors.id"), nullable=True, index=True
    )
