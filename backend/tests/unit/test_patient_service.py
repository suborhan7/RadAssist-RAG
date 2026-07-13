"""
Unit tests for PatientService, per the frozen Phase 11 architecture
(development_log.md, "Phase 11 -- Longitudinal Patient History &
Comparison: Architecture (FROZEN)"). Real, throwaway in-memory SQLite
session (same pattern as Phase 8 Step 6's atomicity test) rather than
fakes -- this is fundamentally DB query logic (exact-match filtering,
MAX()-based code generation, a join for chronological history), which a
hand-built fake cannot meaningfully exercise.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.domain.entities import ReportContent, ReportStatus
from app.models.report import ReportRecord
from app.models.retrieval_session import RetrievalSession
from app.services.patient_service import PatientService

CONTENT = ReportContent(
    examination="e", clinical_history="c", technique="t", findings="f",
    impression="i", recommendation="r", disclaimer="d",
)


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine


def _seed_session(db, patient_id=None) -> uuid.UUID:
    session_id = uuid.uuid4()
    db.add(
        RetrievalSession(
            id=session_id, query_image_path="query.png", top_k=5,
            min_similarity=0.0, num_results=1, retrieval_time_ms=10, patient_id=patient_id,
        )
    )
    db.commit()
    return session_id


def _seed_report(db, session_id: uuid.UUID, created_at: datetime) -> uuid.UUID:
    report_id = uuid.uuid4()
    db.add(
        ReportRecord(
            id=report_id, session_id=session_id, language="en", status=ReportStatus.AI_DRAFT,
            ai_content=asdict(CONTENT), validation_warnings=[], report_date="2026-07-13",
            llm_model="llama3:8b", llm_temperature=0.0, embedding_model="biomedclip",
            embedding_version="v1", collection_name="iu_cxr_biomedclip_v1_train",
            created_at=created_at,
        )
    )
    db.commit()
    return report_id


def _make_service(db=None):
    if db is None:
        engine = _make_engine()
        db = sessionmaker(bind=engine)()
    return PatientService(db), db


def test_create_generates_sequential_patient_code():
    service, db = _make_service()

    first = service.create(name="Jane Doe", date_of_birth="1980-01-01", gender="F")
    second = service.create(name="John Smith", date_of_birth="1975-06-15", gender="M")

    assert first.patient_code == "PAT-000001"
    assert second.patient_code == "PAT-000002"
    assert first.name == "Jane Doe"
    assert first.date_of_birth == "1980-01-01"
    assert first.gender == "F"

    db.close()


def test_find_by_code_returns_correct_patient_or_none():
    service, db = _make_service()
    created = service.create(name="Jane Doe", date_of_birth="1980-01-01", gender="F")

    found = service.find_by_code(created.patient_code)
    assert found is not None
    assert found.id == created.id
    assert found.name == "Jane Doe"

    assert service.find_by_code("PAT-999999") is None

    db.close()


def test_find_by_name_and_dob_exact_match_only_near_miss_does_not_match():
    service, db = _make_service()
    service.create(name="Jane Doe", date_of_birth="1980-01-01", gender="F")

    exact = service.find_by_name_and_dob("Jane Doe", "1980-01-01")
    assert len(exact) == 1
    assert exact[0].name == "Jane Doe"

    # near-miss name (one character short) must NOT match
    near_miss_name = service.find_by_name_and_dob("Jane Do", "1980-01-01")
    assert near_miss_name == []

    # near-miss DOB (one day off) must NOT match
    near_miss_dob = service.find_by_name_and_dob("Jane Doe", "1980-01-02")
    assert near_miss_dob == []

    db.close()


def test_multiple_patients_same_name_different_dob_correctly_distinguished():
    service, db = _make_service()
    older = service.create(name="Jane Doe", date_of_birth="1960-03-10", gender="F")
    younger = service.create(name="Jane Doe", date_of_birth="1995-11-20", gender="F")

    older_match = service.find_by_name_and_dob("Jane Doe", "1960-03-10")
    younger_match = service.find_by_name_and_dob("Jane Doe", "1995-11-20")

    assert len(older_match) == 1 and older_match[0].id == older.id
    assert len(younger_match) == 1 and younger_match[0].id == younger.id
    assert older_match[0].id != younger_match[0].id

    db.close()


def test_get_history_returns_reports_in_chronological_order():
    service, db = _make_service()
    patient = service.create(name="Jane Doe", date_of_birth="1980-01-01", gender="F")
    patient_uuid = uuid.UUID(patient.id)

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    session_1 = _seed_session(db, patient_id=patient_uuid)
    report_1 = _seed_report(db, session_1, created_at=base)
    session_3 = _seed_session(db, patient_id=patient_uuid)
    report_3 = _seed_report(db, session_3, created_at=base + timedelta(days=60))
    session_2 = _seed_session(db, patient_id=patient_uuid)
    report_2 = _seed_report(db, session_2, created_at=base + timedelta(days=30))

    history = service.get_history(patient.id)

    assert [r.id for r in history] == [str(report_1), str(report_2), str(report_3)]

    db.close()
