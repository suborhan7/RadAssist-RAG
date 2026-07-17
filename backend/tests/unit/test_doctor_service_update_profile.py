"""
Unit tests for DoctorService.update_profile() (Phase 16, Settings路Profile).
Real, in-memory SQLite DB (StaticPool), same pattern as
test_patient_service.py/test_auth_service.py -- no collaborators to fake,
this method only touches the DB.

The one behavior worth a dedicated test: a partial update must leave
every field NOT present in the call untouched, not silently reset it to
None -- the real risk with **fields-style updates is accidentally wiping
sibling columns.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.services.doctor_service import DoctorService


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine


def test_new_doctor_has_all_profile_fields_none_by_default():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service = DoctorService(db=db)

    doctor = service.create("a@example.com", "hashed", "Dr. A")

    assert doctor.bmdc_number is None
    assert doctor.default_top_k is None
    assert doctor.default_language is None
    assert doctor.default_questionnaire_skip is None
    assert doctor.default_rail_state is None
    assert doctor.default_export_format is None

    db.close()


def test_update_profile_sets_only_the_fields_passed():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service = DoctorService(db=db)
    doctor = service.create("a@example.com", "hashed", "Dr. A")

    updated = service.update_profile(doctor.id, bmdc_number="A-12345", default_top_k=10)

    assert updated.bmdc_number == "A-12345"
    assert updated.default_top_k == 10
    # untouched fields stay None, not silently reset
    assert updated.default_language is None
    assert updated.default_questionnaire_skip is None
    assert updated.full_name == "Dr. A"

    db.close()


def test_update_profile_second_call_does_not_erase_first_calls_fields():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service = DoctorService(db=db)
    doctor = service.create("a@example.com", "hashed", "Dr. A")

    service.update_profile(doctor.id, bmdc_number="A-12345")
    updated = service.update_profile(doctor.id, default_language="bn")

    # the real risk this test exists to catch: a second partial update
    # must not wipe out what the first one set
    assert updated.bmdc_number == "A-12345"
    assert updated.default_language == "bn"

    db.close()


def test_update_profile_nonexistent_doctor_raises_value_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service = DoctorService(db=db)

    with pytest.raises(ValueError, match="no DoctorRecord found"):
        service.update_profile("11111111-1111-1111-1111-111111111111", bmdc_number="X")

    db.close()
