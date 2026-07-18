"""
Unit tests for ReportEditService (Phase 17 Step 4/5). Real, throwaway
in-memory SQLite session -- same pattern as test_report_detail_service.py
and every other DB-query-logic-heavy service test in this project (a
hand-built fake cannot meaningfully exercise ownership derivation via a
real join, JSON-column merge semantics, or genuine commit/rollback
behavior).
"""
from __future__ import annotations

import uuid
from dataclasses import asdict

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.domain.entities import ReportContent, ReportStatus
from app.models.report import ReportRecord
from app.models.report_audit_log import ReportAuditLog
from app.models.retrieval_session import RetrievalSession
from app.services.exceptions import (
    ForbiddenError,
    ReportAlreadyFinalizedError,
    ReportNotFoundError,
    ReportValidationError,
)
from app.services.report_edit_service import ReportEditService

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


def _seed_session(db, doctor_id: uuid.UUID | None) -> uuid.UUID:
    session_id = uuid.uuid4()
    db.add(
        RetrievalSession(
            id=session_id, query_image_path="query.png", top_k=1,
            min_similarity=0.0, num_results=1, retrieval_time_ms=10, doctor_id=doctor_id,
        )
    )
    db.commit()
    return session_id


def _seed_report(db, session_id: uuid.UUID, status: ReportStatus = ReportStatus.AI_DRAFT) -> uuid.UUID:
    report_id = uuid.uuid4()
    db.add(
        ReportRecord(
            id=report_id, session_id=session_id, language="en", status=status,
            ai_draft_content=asdict(CONTENT), final_content=asdict(CONTENT),
            validation_warnings=[], report_date="2026-07-13",
            llm_model="llama3:8b", llm_temperature=0.0, embedding_model="biomedclip",
            embedding_version="v1", collection_name="iu_cxr_biomedclip_v1_train",
        )
    )
    db.commit()
    return report_id


def test_update_content_merges_fields_and_transitions_to_doctor_edited():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id)
    report_id = _seed_report(db, session_id)

    service = ReportEditService(db)
    record = service.update_content(str(report_id), str(owner_id), {"findings": "new findings"})

    assert record.status == ReportStatus.DOCTOR_EDITED
    assert record.final_content["findings"] == "new findings"
    # untouched fields survive the merge
    assert record.final_content["impression"] == "i"
    assert record.final_content["clinical_history"] == "c"
    # ai_draft_content is untouched -- the immutable original
    assert record.ai_draft_content["findings"] == "f"

    audit_rows = db.query(ReportAuditLog).filter(ReportAuditLog.report_id == report_id).all()
    assert len(audit_rows) == 1
    assert audit_rows[0].doctor_id == owner_id
    assert audit_rows[0].action == "EDITED"

    db.close()


def test_second_edit_creates_second_distinct_audit_row_no_overwrite():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id)
    report_id = _seed_report(db, session_id)

    service = ReportEditService(db)
    service.update_content(str(report_id), str(owner_id), {"findings": "first edit"})
    service.update_content(str(report_id), str(owner_id), {"findings": "second edit"})

    audit_rows = db.query(ReportAuditLog).filter(ReportAuditLog.report_id == report_id).all()
    assert len(audit_rows) == 2
    assert audit_rows[0].id != audit_rows[1].id

    record = db.query(ReportRecord).filter(ReportRecord.id == report_id).one()
    assert record.final_content["findings"] == "second edit"
    assert record.status == ReportStatus.DOCTOR_EDITED

    db.close()


def test_non_owner_edit_raises_forbidden_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    other_doctor_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id)
    report_id = _seed_report(db, session_id)

    service = ReportEditService(db)
    with pytest.raises(ForbiddenError):
        service.update_content(str(report_id), str(other_doctor_id), {"findings": "hijacked"})

    record = db.query(ReportRecord).filter(ReportRecord.id == report_id).one()
    assert record.status == ReportStatus.AI_DRAFT
    assert db.query(ReportAuditLog).count() == 0

    db.close()


def test_edit_on_final_report_raises_already_finalized_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id)
    report_id = _seed_report(db, session_id, status=ReportStatus.FINAL)

    service = ReportEditService(db)
    with pytest.raises(ReportAlreadyFinalizedError):
        service.update_content(str(report_id), str(owner_id), {"findings": "too late"})

    db.close()


def test_nonexistent_report_id_raises_report_not_found_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service = ReportEditService(db)

    with pytest.raises(ReportNotFoundError):
        service.update_content(str(uuid.uuid4()), str(uuid.uuid4()), {"findings": "x"})

    db.close()


def test_finalize_from_ai_draft_sets_finalized_fields():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id)
    report_id = _seed_report(db, session_id)

    service = ReportEditService(db)
    record = service.finalize(str(report_id), str(owner_id))

    assert record.status == ReportStatus.FINAL
    assert record.finalized_by == owner_id
    assert record.finalized_at is not None

    db.close()


def test_finalize_from_doctor_edited_is_also_valid():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id)
    report_id = _seed_report(db, session_id)

    service = ReportEditService(db)
    service.update_content(str(report_id), str(owner_id), {"findings": "edited findings"})
    record = service.finalize(str(report_id), str(owner_id))

    assert record.status == ReportStatus.FINAL
    assert record.final_content["findings"] == "edited findings"

    db.close()


def test_finalize_twice_raises_already_finalized_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id)
    report_id = _seed_report(db, session_id)

    service = ReportEditService(db)
    service.finalize(str(report_id), str(owner_id))

    with pytest.raises(ReportAlreadyFinalizedError):
        service.finalize(str(report_id), str(owner_id))

    db.close()


def test_finalize_non_owner_raises_forbidden_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    other_doctor_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id)
    report_id = _seed_report(db, session_id)

    service = ReportEditService(db)
    with pytest.raises(ForbiddenError):
        service.finalize(str(report_id), str(other_doctor_id))

    db.close()


def test_finalize_with_empty_findings_raises_validation_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id)
    report_id = _seed_report(db, session_id)

    service = ReportEditService(db)
    service.update_content(str(report_id), str(owner_id), {"findings": "   "})

    with pytest.raises(ReportValidationError):
        service.finalize(str(report_id), str(owner_id))

    db.close()
