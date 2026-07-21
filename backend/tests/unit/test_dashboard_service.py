"""
Unit tests for DashboardService, covering the two new Priority 4 fields
(examinations_today, awaiting_review) added on top of the existing
Phase 15 counts -- both real, doctor-scoped query extensions of the same
join/filter pattern get_stats() already used, no new column/table.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.domain.entities import ReportContent, ReportStatus
from app.models.report import ReportRecord
from app.models.retrieval_session import RetrievalSession
from app.services.dashboard_service import DashboardService

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


def _seed_session(db, doctor_id, created_at=None) -> uuid.UUID:
    session_id = uuid.uuid4()
    db.add(
        RetrievalSession(
            id=session_id, query_image_path="q.png", top_k=5, min_similarity=0.0,
            num_results=5, retrieval_time_ms=10, doctor_id=doctor_id,
        )
    )
    db.commit()
    if created_at is not None:
        session = db.query(RetrievalSession).filter(RetrievalSession.id == session_id).one()
        session.created_at = created_at
        db.commit()
    return session_id


def _seed_report(db, session_id, status=ReportStatus.AI_DRAFT) -> uuid.UUID:
    report_id = uuid.uuid4()
    db.add(
        ReportRecord(
            id=report_id, session_id=session_id, language="en", status=status,
            ai_draft_content=asdict(CONTENT), final_content=asdict(CONTENT),
            validation_warnings=[], report_date="2026-07-18", llm_model="llama3:8b",
            llm_temperature=0.0, embedding_model="biomedclip", embedding_version="v1",
            collection_name="iu_cxr_biomedclip_v1_train",
        )
    )
    db.commit()
    return report_id


def test_examinations_today_counts_only_todays_sessions_for_this_doctor():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    doctor_id = uuid.uuid4()

    _seed_session(db, doctor_id, created_at=datetime.combine(date.today(), datetime.min.time()))
    _seed_session(db, doctor_id, created_at=datetime.now() - timedelta(days=1))

    stats = DashboardService(db=db).get_stats(str(doctor_id))
    assert stats.examinations_today == 1

    db.close()


def test_awaiting_review_excludes_final_reports_includes_everything_else():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    doctor_id = uuid.uuid4()

    session_a = _seed_session(db, doctor_id)
    _seed_report(db, session_a, status=ReportStatus.AI_DRAFT)
    session_b = _seed_session(db, doctor_id)
    _seed_report(db, session_b, status=ReportStatus.DOCTOR_EDITED)
    session_c = _seed_session(db, doctor_id)
    _seed_report(db, session_c, status=ReportStatus.FINAL)

    stats = DashboardService(db=db).get_stats(str(doctor_id))
    assert stats.awaiting_review == 2  # AI_DRAFT + DOCTOR_EDITED, not FINAL

    db.close()


def test_oldest_awaiting_review_picks_the_actual_oldest_non_final_report():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    doctor_id = uuid.uuid4()

    session_a = _seed_session(db, doctor_id)
    newer_id = _seed_report(db, session_a, status=ReportStatus.AI_DRAFT)
    session_b = _seed_session(db, doctor_id)
    older_id = _seed_report(db, session_b, status=ReportStatus.DOCTOR_EDITED)
    session_c = _seed_session(db, doctor_id)
    _seed_report(db, session_c, status=ReportStatus.FINAL)  # not awaiting review -- must be excluded

    # force explicit created_at ordering, oldest first, independent of insert order
    db.query(ReportRecord).filter(ReportRecord.id == newer_id).update(
        {"created_at": datetime(2026, 7, 2, 10, 0, 0)}
    )
    db.query(ReportRecord).filter(ReportRecord.id == older_id).update(
        {"created_at": datetime(2026, 7, 1, 10, 0, 0)}
    )
    db.commit()

    stats = DashboardService(db=db).get_stats(str(doctor_id))
    assert stats.oldest_awaiting_review_report_id == str(older_id)
    assert stats.oldest_awaiting_review_report_date == "2026-07-18"

    db.close()


def test_oldest_awaiting_review_none_when_nothing_awaiting():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    doctor_id = uuid.uuid4()

    session_id = _seed_session(db, doctor_id)
    _seed_report(db, session_id, status=ReportStatus.FINAL)

    stats = DashboardService(db=db).get_stats(str(doctor_id))
    assert stats.oldest_awaiting_review_report_id is None
    assert stats.oldest_awaiting_review_report_date is None

    db.close()


def test_awaiting_review_and_examinations_today_scoped_to_this_doctor_only():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    doctor_a = uuid.uuid4()
    doctor_b = uuid.uuid4()

    session_a = _seed_session(db, doctor_a, created_at=datetime.combine(date.today(), datetime.min.time()))
    _seed_report(db, session_a, status=ReportStatus.AI_DRAFT)
    session_b = _seed_session(db, doctor_b, created_at=datetime.combine(date.today(), datetime.min.time()))
    _seed_report(db, session_b, status=ReportStatus.AI_DRAFT)

    stats_a = DashboardService(db=db).get_stats(str(doctor_a))
    assert stats_a.examinations_today == 1
    assert stats_a.awaiting_review == 1

    db.close()
