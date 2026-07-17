"""
app/models/doctor.py
====================================================================
doctors: one row per registered doctor (Phase 13 DB scope -- see
phase13_auth_architecture.md's "Database" section).

Naming note: named `DoctorRecord`, not `Doctor` -- `Doctor` is already the
frozen domain entity in app/domain/entities.py, same Report/ReportRecord,
Patient/PatientRecord, Comparison/ComparisonRecord collision-avoidance
precedent applied proactively (Phase 8/11 established this convention;
this is now the fourth instance of it).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DoctorRecord(Base):
    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
