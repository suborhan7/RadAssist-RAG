"""
app/models/report.py
====================================================================
reports: one row per POST /generate-report call (Phase 8 DB scope -- see
the frozen architecture's "Database (new reports table)" section).
final_content/doctor-edit fields on the frozen domain Report entity
(app/domain/entities.py) remain null/unused here -- a future editing
phase's concern, not built in Phase 8.

Naming note: this ORM model is named `ReportRecord`, not `Report` --
`Report` is already the frozen domain entity in app/domain/entities.py,
and silently colliding two same-named classes across the domain/
infrastructure boundary is a real correctness risk (an import alias only
protects call sites that remember to use it), not a cosmetic one. The
newly-introduced infrastructure class is renamed instead of the frozen,
foundational domain concept. The table name itself, "reports", is
unaffected -- only the Python class name differs from the filename-to-
classname convention every other model in this package otherwise follows.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.domain.entities import ReportStatus

if TYPE_CHECKING:
    from app.models.retrieval_session import RetrievalSession


class ReportRecord(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("retrieval_sessions.id"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus), nullable=False, default=ReportStatus.AI_DRAFT
    )
    ai_content: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_warnings: Mapped[list] = mapped_column(JSON, nullable=False)
    report_date: Mapped[str] = mapped_column(String, nullable=False)
    llm_model: Mapped[str] = mapped_column(String, nullable=False)
    llm_temperature: Mapped[float] = mapped_column(Float, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String, nullable=False)
    embedding_version: Mapped[str] = mapped_column(String, nullable=False)
    collection_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    session: Mapped["RetrievalSession"] = relationship()
