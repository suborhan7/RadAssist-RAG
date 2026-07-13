"""
app/services/patient_service.py
====================================================================
Implements IPatientRepository. Patient registration (auto-generated
sequential patient_code), exact-match search (by code, or by name+DOB --
no fuzzy matching, per frozen Phase 11 Decision 4: a doctor picking the
wrong patient from a fuzzy-matched list is a worse failure mode than being
asked to re-enter a name correctly), and chronological history retrieval.

patient_code generation strategy, stated explicitly: sequential, derived
from the current max existing patient_code's numeric suffix + 1 -- not a
separate auto-increment integer column (the frozen schema doesn't have
one), and not row-COUNT-based (which would risk reusing a code if a row
were ever deleted). Zero-padded to 6 digits ("PAT-000001"); consistent
width means a plain lexicographic SQL MAX() gives the same answer as
numeric ordering would. Documented concurrency caveat: two concurrent
create() calls could compute the same "next" candidate code before either
commits; the schema's UNIQUE constraint on patient_code (Step 2) makes a
genuine race fail loudly (an IntegrityError at commit), not silently
create a duplicate -- acceptable for this thesis system's expected usage,
not a claim of production-grade concurrency handling.

get_history() reuses the shared build_report_domain_entity() helper
(Phase 10, extracted this phase into report_reconstruction.py) rather
than a second reconstruction path.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.entities import Patient, Report
from app.models.patient import PatientRecord
from app.models.report import ReportRecord
from app.models.retrieval_session import RetrievalSession
from app.services.report_reconstruction import build_report_domain_entity


class PatientService:
    """Satisfies domain.interfaces.IPatientRepository."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, name: str, date_of_birth: str, gender: str) -> Patient:
        record = PatientRecord(
            patient_code=self._generate_next_patient_code(),
            name=name,
            date_of_birth=date.fromisoformat(date_of_birth),
            gender=gender,
        )
        self._db.add(record)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return self._to_domain(record)

    def find_by_code(self, patient_code: str) -> Patient | None:
        record = self._db.query(PatientRecord).filter(PatientRecord.patient_code == patient_code).one_or_none()
        return self._to_domain(record) if record is not None else None

    def find_by_name_and_dob(self, name: str, date_of_birth: str) -> list[Patient]:
        dob = date.fromisoformat(date_of_birth)
        records = (
            self._db.query(PatientRecord)
            .filter(PatientRecord.name == name, PatientRecord.date_of_birth == dob)
            .all()
        )
        return [self._to_domain(r) for r in records]

    def get_history(self, patient_id: str) -> list[Report]:
        patient_uuid = uuid.UUID(patient_id)
        records = (
            self._db.query(ReportRecord)
            .join(RetrievalSession, ReportRecord.session_id == RetrievalSession.id)
            .filter(RetrievalSession.patient_id == patient_uuid)
            .order_by(ReportRecord.created_at.asc())
            .all()
        )
        return [build_report_domain_entity(r) for r in records]

    def _generate_next_patient_code(self) -> str:
        max_code = self._db.query(func.max(PatientRecord.patient_code)).scalar()
        next_number = int(max_code.split("-")[1]) + 1 if max_code else 1
        return f"PAT-{next_number:06d}"

    @staticmethod
    def _to_domain(record: PatientRecord) -> Patient:
        return Patient(
            id=str(record.id),
            patient_code=record.patient_code,
            name=record.name,
            date_of_birth=record.date_of_birth.isoformat(),
            gender=record.gender,
        )
