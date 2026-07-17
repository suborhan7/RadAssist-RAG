"""
app/services/dashboard_service.py
====================================================================
Implements the Phase 15 dashboard-stats use case: real, queried counts
for "your reports vs. the shared registry," per
design_specification.md's ownership model (§3 of
phase13_auth_architecture.md) and frontend/CLAUDE.md's explicit
instruction to use "real counts from the API," not an invented
placeholder stat like "38 of 142."

Ownership is derived through retrieval_sessions.doctor_id, the same
single source of truth every other Phase 15 owner field uses (reports
have no doctor_id of their own; patients are shared/institutional and
have none at all, per phase13_auth_architecture.md Decision 2) -- no new
column, no redundant tracking.

my_patients counts DISTINCT patients this doctor has created at least
one session for, not total sessions -- a doctor who examined the same
patient five times should not inflate their own patient count fivefold.
NULL patient_id sessions (pre-Phase-11) are naturally excluded by the
join and are not this doctor's concern either way.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.patient import PatientRecord
from app.models.report import ReportRecord
from app.models.retrieval_session import RetrievalSession


@dataclass(frozen=True)
class DashboardStats:
    my_reports: int
    total_reports: int
    my_patients: int
    total_patients: int


class DashboardService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_stats(self, current_doctor_id: str) -> DashboardStats:
        # RetrievalSession.doctor_id is a SQLAlchemy Uuid column -- it
        # expects a real uuid.UUID for comparison, not the plain str every
        # caller here holds (same lesson as every other doctor_id filter
        # in this codebase, e.g. DoctorService.find_by_id). Passing the
        # bare string compiles fine but raises AttributeError at execution
        # time deep inside the DBAPI parameter binding -- caught for real
        # by running this against a live query, not assumed correct.
        current_doctor_uuid = uuid.UUID(current_doctor_id)

        total_reports = self._db.query(func.count(ReportRecord.id)).scalar() or 0
        total_patients = self._db.query(func.count(PatientRecord.id)).scalar() or 0

        my_reports = (
            self._db.query(func.count(ReportRecord.id))
            .join(RetrievalSession, ReportRecord.session_id == RetrievalSession.id)
            .filter(RetrievalSession.doctor_id == current_doctor_uuid)
            .scalar()
            or 0
        )
        my_patients = (
            self._db.query(func.count(func.distinct(RetrievalSession.patient_id)))
            .filter(
                RetrievalSession.doctor_id == current_doctor_uuid,
                RetrievalSession.patient_id.isnot(None),
            )
            .scalar()
            or 0
        )

        return DashboardStats(
            my_reports=my_reports,
            total_reports=total_reports,
            my_patients=my_patients,
            total_patients=total_patients,
        )
