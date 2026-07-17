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

bmdc_number/default_* (Phase 16, additive, nullable): Settings/Profile's
identity + per-doctor workspace-preference fields. Extending this same
table rather than a new doctor_preferences table -- explicit decision,
matching this project's precedent of not over-splitting small 1:1 data.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DoctorRecord(Base):
    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    bmdc_number: Mapped[str | None] = mapped_column(String, nullable=True)
    default_top_k: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_language: Mapped[str | None] = mapped_column(String, nullable=True)
    default_questionnaire_skip: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    default_rail_state: Mapped[str | None] = mapped_column(String, nullable=True)
    default_export_format: Mapped[str | None] = mapped_column(String, nullable=True)
