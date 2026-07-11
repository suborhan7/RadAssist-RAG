"""
app/models/retrieved_evidence.py
====================================================================
retrieved_evidence: one row per returned case, FK to retrieval_sessions --
audit trail (Phase 4 DB scope, see retrieval_session.py for the rest).
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.retrieval_session import RetrievalSession


class RetrievedEvidence(Base):
    __tablename__ = "retrieved_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("retrieval_sessions.id"), nullable=False, index=True
    )
    study_uid: Mapped[str] = mapped_column(String, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    similarity: Mapped[float] = mapped_column(Float, nullable=False)

    session: Mapped["RetrievalSession"] = relationship(back_populates="evidence")
