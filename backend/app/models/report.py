"""
app/models/report.py
====================================================================
reports: one row per POST /generate-report call (Phase 8 DB scope -- see
the frozen architecture's "Database (new reports table)" section).

Naming note: this ORM model is named `ReportRecord`, not `Report` --
`Report` is already the frozen domain entity in app/domain/entities.py,
and silently colliding two same-named classes across the domain/
infrastructure boundary is a real correctness risk (an import alias only
protects call sites that remember to use it), not a cosmetic one. The
newly-introduced infrastructure class is renamed instead of the frozen,
foundational domain concept. The table name itself, "reports", is
unaffected -- only the Python class name differs from the filename-to-
classname convention every other model in this package otherwise follows.

Phase 17: `ai_content` renamed to `ai_draft_content` -- it already WAS
the immutable AI draft (nothing ever updated it post-insert); this names
it correctly rather than adding a duplicate column (see phase17_finalize_
edit_architecture.md Decision 3 and the Step 2 migration). `final_content`
is new, mutable via PATCH /reports/{id}, starts as a deep copy of
ai_draft_content. `finalized_at`/`finalized_by` are new, both nullable
(only set once, by PATCH /reports/{id}/finalize -- see that route for
why a denormalized finalized_by is worth keeping despite always equaling
session.doctor_id under the current ownership model).
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
    ai_draft_content: Mapped[dict] = mapped_column(JSON, nullable=False)
    final_content: Mapped[dict] = mapped_column(JSON, nullable=False)
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
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finalized_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("doctors.id"), nullable=True
    )

    session: Mapped["RetrievalSession"] = relationship()
