"""
app/services/doctor_service.py
====================================================================
Implements IDoctorRepository. Same "repository-Protocol implementation
lives in app/services/ as a plain xxx_service.py" convention as
PatientService -- this codebase has no separate infrastructure/
repositories/ layer, and introducing one for exactly one new entity would
fragment an otherwise consistent convention (see IDoctorRepository's own
docstring in domain/interfaces.py).

No auto-generated identifier scheme here unlike PatientService's
patient_code -- email is the natural, already-unique, user-supplied
identifier (enforced by the doctors.email UNIQUE index, Step 2's
migration), so there is nothing analogous to invent.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.domain.entities import Doctor
from app.models.doctor import DoctorRecord


class DoctorService:
    """Satisfies domain.interfaces.IDoctorRepository."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, email: str, password_hash: str, full_name: str) -> Doctor:
        record = DoctorRecord(email=email, password_hash=password_hash, full_name=full_name)
        self._db.add(record)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return self._to_domain(record)

    def find_by_email(self, email: str) -> Doctor | None:
        record = self._db.query(DoctorRecord).filter(DoctorRecord.email == email).one_or_none()
        return self._to_domain(record) if record is not None else None

    def find_by_id(self, doctor_id: str) -> Doctor | None:
        # Same "parse once, let a malformed id raise ValueError" pattern as
        # PatientService.find_by_id() -- the route layer maps ValueError to
        # its own HTTP status, not this service.
        doctor_uuid = uuid.UUID(doctor_id)
        record = self._db.query(DoctorRecord).filter(DoctorRecord.id == doctor_uuid).one_or_none()
        return self._to_domain(record) if record is not None else None

    @staticmethod
    def _to_domain(record: DoctorRecord) -> Doctor:
        return Doctor(
            id=str(record.id),
            email=record.email,
            password_hash=record.password_hash,
            full_name=record.full_name,
            created_at=record.created_at.isoformat() if record.created_at else "",
        )
