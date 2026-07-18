"""
Unit tests for ReportDetailService, per the Phase 12 addition (see that
service's own module docstring for why it was added -- no endpoint
existed anywhere that could answer "get this report's full detail from
just its report_id"). Same real-DB-plus-fakes pattern as
test_explainability_service.py: DB access uses a real, throwaway
in-memory SQLite session; vector_store/label_voting_service are hand-built
fakes.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.domain.entities import ReportContent, ReportStatus, RetrievedCase, VotedLabel
from app.models.report import ReportRecord
from app.models.report_audit_log import ReportAuditLog
from app.models.retrieval_session import RetrievalSession
from app.models.retrieved_evidence import RetrievedEvidence
from app.services.exceptions import ReportNotFoundError
from app.services.report_detail_service import ReportDetailService

CONTENT = ReportContent(
    examination="e", clinical_history="c", technique="t", findings="f",
    impression="i", recommendation="r", disclaimer="d",
)


class FakeVectorStore:
    def __init__(self, cases_by_uid):
        self.cases_by_uid = cases_by_uid
        self.get_by_ids_calls = []

    def get_by_ids(self, uids):
        self.get_by_ids_calls.append(list(uids))
        return [self.cases_by_uid[uid] for uid in uids]

    def query(self, embedding, top_k):
        raise NotImplementedError

    def upsert(self, uid, embedding, metadata):
        raise NotImplementedError


class FakeLabelVoter:
    def __init__(self, voted_labels):
        self.voted_labels = voted_labels
        self.vote_calls = []

    def vote(self, retrieved):
        self.vote_calls.append(list(retrieved))
        return self.voted_labels


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine


def _seed_session(db, study_uids: list[str], patient_id=None) -> uuid.UUID:
    session_id = uuid.uuid4()
    db.add(
        RetrievalSession(
            id=session_id, query_image_path="query.png", top_k=len(study_uids),
            min_similarity=0.0, num_results=len(study_uids), retrieval_time_ms=10,
            patient_id=patient_id,
        )
    )
    db.add_all(
        [
            RetrievedEvidence(session_id=session_id, study_uid=uid, rank=rank, similarity=0.9)
            for rank, uid in enumerate(study_uids, start=1)
        ]
    )
    db.commit()
    return session_id


def _seed_report(db, session_id: uuid.UUID, validation_warnings=None) -> uuid.UUID:
    report_id = uuid.uuid4()
    db.add(
        ReportRecord(
            id=report_id, session_id=session_id, language="en", status=ReportStatus.AI_DRAFT,
            ai_draft_content=asdict(CONTENT), final_content=asdict(CONTENT),
            validation_warnings=validation_warnings or [],
            report_date="2026-07-13", llm_model="llama3:8b", llm_temperature=0.0,
            embedding_model="biomedclip", embedding_version="v1",
            collection_name="iu_cxr_biomedclip_v1_train",
        )
    )
    db.commit()
    return report_id


def _make_service(db, cases_by_uid, voted_labels):
    fakes = {
        "vector_store": FakeVectorStore(cases_by_uid),
        "label_voting_service": FakeLabelVoter(voted_labels),
    }
    service = ReportDetailService(
        db=db, vector_store=fakes["vector_store"], label_voting_service=fakes["label_voting_service"]
    )
    return service, fakes


def test_correct_data_flow_with_patient_and_evidence():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()

    case_a = RetrievedCase(source_uid="u1", similarity=0.95, findings="fa", impression="ia", labels=("Pneumonia",))
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=0.5)]
    patient_id = uuid.uuid4()

    session_id = _seed_session(db, ["u1"], patient_id=patient_id)
    report_id = _seed_report(db, session_id, validation_warnings=["Mentions 'X' which is not supported"])

    service, fakes = _make_service(db, {"u1": case_a}, voted)

    detail = service.get_report_detail(str(report_id))

    assert detail.report_id == str(report_id)
    assert detail.session_id == str(session_id)
    assert detail.patient_id == str(patient_id)
    assert detail.content == CONTENT
    assert detail.ai_draft_content == CONTENT
    assert detail.language == "en"
    assert detail.status == ReportStatus.AI_DRAFT
    assert detail.validation_warnings == ("Mentions 'X' which is not supported",)
    assert detail.llm_model == "llama3:8b"
    assert detail.retrieved_cases == (case_a,)
    assert fakes["vector_store"].get_by_ids_calls == [["u1"]]
    # a fresh, never-edited/finalized report has no finalized_at/by and no audit log
    assert detail.finalized_at is None
    assert detail.finalized_by is None
    assert detail.audit_log == ()

    db.close()


def test_edited_and_finalized_report_surfaces_audit_log_and_finalized_fields():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()

    case_a = RetrievedCase(source_uid="u1", similarity=0.9, findings="fa", impression="ia", labels=())
    session_id = _seed_session(db, ["u1"], patient_id=None)
    report_id = _seed_report(db, session_id)

    doctor_id = uuid.uuid4()
    edited_content = ReportContent(
        examination="e", clinical_history="c", technique="t", findings="edited findings",
        impression="i", recommendation="r", disclaimer="d",
    )
    finalized_at = datetime(2026, 7, 14, 10, 0, 0)
    report_record = db.query(ReportRecord).filter(ReportRecord.id == report_id).one()
    report_record.final_content = asdict(edited_content)
    report_record.status = ReportStatus.FINAL
    report_record.finalized_at = finalized_at
    report_record.finalized_by = doctor_id
    db.add(
        ReportAuditLog(
            report_id=report_id, doctor_id=doctor_id, action="EDITED",
            at=datetime(2026, 7, 14, 9, 0, 0),
        )
    )
    db.add(
        ReportAuditLog(
            report_id=report_id, doctor_id=doctor_id, action="EDITED",
            at=datetime(2026, 7, 14, 9, 30, 0),
        )
    )
    db.commit()

    service, _ = _make_service(db, {"u1": case_a}, [])
    detail = service.get_report_detail(str(report_id))

    assert detail.content == edited_content
    assert detail.ai_draft_content == CONTENT  # immutable original, untouched by the edit
    assert detail.status == ReportStatus.FINAL
    assert detail.finalized_at == finalized_at.isoformat()
    assert detail.finalized_by == str(doctor_id)
    assert len(detail.audit_log) == 2
    # oldest first
    assert detail.audit_log[0].at < detail.audit_log[1].at
    assert all(entry.doctor_id == str(doctor_id) and entry.action == "EDITED" for entry in detail.audit_log)

    db.close()


def test_patient_id_is_none_when_session_has_none():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()

    case_a = RetrievedCase(source_uid="u1", similarity=0.9, findings="fa", impression="ia", labels=())
    session_id = _seed_session(db, ["u1"], patient_id=None)
    report_id = _seed_report(db, session_id)

    service, _ = _make_service(db, {"u1": case_a}, [])

    detail = service.get_report_detail(str(report_id))
    assert detail.patient_id is None

    db.close()


def test_nonexistent_report_id_raises_report_not_found_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service, fakes = _make_service(db, {}, [])

    with pytest.raises(ReportNotFoundError):
        service.get_report_detail(str(uuid.uuid4()))

    assert fakes["vector_store"].get_by_ids_calls == []
    db.close()


def test_malformed_report_id_raises_report_not_found_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service, fakes = _make_service(db, {}, [])

    with pytest.raises(ReportNotFoundError):
        service.get_report_detail("not-a-uuid")

    assert fakes["vector_store"].get_by_ids_calls == []
    db.close()
