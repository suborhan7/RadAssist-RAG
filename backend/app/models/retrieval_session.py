"""
app/models/retrieval_session.py
====================================================================
retrieval_sessions: one row per POST /retrieve call (Phase 4 DB scope --
see the frozen architecture's "Database model overview" table). Only this
table and retrieved_evidence exist in this phase; patients/studies/reports/
the broader sessions cache are explicitly deferred.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, Integer, String, Uuid, func
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

    evidence: Mapped[list["RetrievedEvidence"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
