"""
app/models/retrieval_session.py
====================================================================
retrieval_sessions: one row per POST /retrieve call (Phase 4 DB scope --
see the frozen architecture's "Database model overview" table). Only this
table and retrieved_evidence exist in this phase; patients/studies/reports/
the broader sessions cache are explicitly deferred.

patient_id (Phase 11, additive): nullable FK to patients.id -- nullable
because every session created before Phase 11 has no associated patient,
and retrofitting one is out of scope. No `visits` table was introduced
for this linkage (frozen Phase 11 Decision 2): retrieval_sessions already
is this system's "visit" concept, so patient_id is added directly here
rather than via a redundant parallel table.

doctor_id (Phase 13, additive): nullable FK to doctors.id, same nullable
reasoning as patient_id -- every session created before Phase 13 has no
associated doctor. Ownership attaches to the WORK (this row), per
phase13_auth_architecture.md's frozen decision, not to Patient (which
stays shared/institutional, unchanged).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.retrieved_evidence import RetrievedEvidence


class RetrievalSession(Base):
    __tablename__ = "retrieval_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    query_image_path: Mapped[str] = mapped_column(String, nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    min_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    num_results: Mapped[int] = mapped_column(Integer, nullable=False)
    retrieval_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("patients.id"), nullable=True, index=True
    )
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("doctors.id"), nullable=True, index=True
    )

    evidence: Mapped[list["RetrievedEvidence"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
