"""
app/models/patient.py
====================================================================
patients: one row per registered patient (Phase 11 DB scope -- see the
frozen architecture's "Database" section).

Naming note: named `PatientRecord`, not `Patient` -- `Patient` is already
the frozen domain entity in app/domain/entities.py, and colliding two
same-named classes across the domain/infrastructure boundary is a real
correctness risk (an import alias only protects call sites that remember
to use it), not a cosmetic one. Same reasoning, applied proactively this
time, as Phase 8's Report/ReportRecord collision fix. The newly-introduced
infrastructure class is renamed; the table name itself, "patients", is
unaffected.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PatientRecord(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    patient_code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
