"""
Unit tests for QuestionnaireService, per the frozen Phase 9 architecture
(development_log.md, "Phase 9 -- Clinical Questionnaire: Architecture
(FROZEN)"). DB access uses a real, throwaway in-memory SQLite session
(same pattern and same reasoning as Phase 8's
test_report_generation_service.py -- faking SQLAlchemy's query/filter/
order_by mechanics would be more complex and less trustworthy). The
vector store, label voter, and questionnaire provider are hand-built
fakes.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.entities import QuestionnaireQuestion, RetrievedCase, VotedLabel
from app.database.base import Base
from app.models.retrieval_session import RetrievalSession
from app.models.retrieved_evidence import RetrievedEvidence
from app.services.exceptions import SessionNotFoundError
from app.services.questionnaire_service import QuestionnaireService


class FakeVectorStore:
    def __init__(self, cases_by_uid):
        self.cases_by_uid = cases_by_uid

    def get_by_ids(self, uids):
        return [self.cases_by_uid[uid] for uid in uids]

    def query(self, embedding, top_k):
        raise NotImplementedError

    def upsert(self, uid, embedding, metadata):
        raise NotImplementedError


class FakeLabelVoter:
    def __init__(self, voted_labels):
        self.voted_labels = voted_labels

    def vote(self, retrieved):
        return self.voted_labels


class FakeQuestionnaireProvider:
    def __init__(self, questions_by_label, default_questions):
        self.questions_by_label = questions_by_label
        self.default_questions = default_questions
        self.calls = []

    def get_questions_for_label(self, label):
        self.calls.append(label)
        return self.questions_by_label.get(label, self.default_questions)


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine


def _seed_session(db, study_uids: list[str]) -> uuid.UUID:
    session_id = uuid.uuid4()
    db.add(
        RetrievalSession(
            id=session_id, query_image_path="query.png", top_k=len(study_uids),
            min_similarity=0.0, num_results=len(study_uids), retrieval_time_ms=10,
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


PNEUMONIA_QUESTIONS = (
    QuestionnaireQuestion(key="duration", text="How long have symptoms been present?", input_type="text"),
    QuestionnaireQuestion(key="fever", text="Does the patient have a fever?", input_type="yes_no"),
)
DEFAULT_QUESTIONS = (
    QuestionnaireQuestion(key="symptom_reason", text="What prompted this X-ray?", input_type="text"),
)


def _make_service(db, cases_by_uid, voted_labels):
    questionnaire_provider = FakeQuestionnaireProvider({"Pneumonia": PNEUMONIA_QUESTIONS}, DEFAULT_QUESTIONS)
    service = QuestionnaireService(
        db=db,
        vector_store=FakeVectorStore(cases_by_uid),
        label_voting_service=FakeLabelVoter(voted_labels),
        questionnaire_provider=questionnaire_provider,
    )
    return service, questionnaire_provider


def test_correct_questions_returned_for_known_label():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    case_a = RetrievedCase(source_uid="u1", similarity=0.9, findings="", impression="", labels=("Pneumonia",))
    voted = [VotedLabel(label="Pneumonia", vote_weight=0.9, agreement=1.0)]
    session_id = _seed_session(db, ["u1"])

    service, provider = _make_service(db, {"u1": case_a}, voted)
    questionnaire = service.get_questionnaire(str(session_id))

    assert questionnaire.session_id == str(session_id)
    assert questionnaire.based_on_label == "Pneumonia"
    assert questionnaire.questions == PNEUMONIA_QUESTIONS
    assert provider.calls == ["Pneumonia"]
    db.close()


def test_fallback_questions_returned_for_unmapped_label():
    """Forces an unmapped top label deterministically via a fake vote
    result -- not a real session, per the frozen spec's own instruction,
    since a real session's real top label can't be forced to be unmapped."""
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    case_a = RetrievedCase(source_uid="u1", similarity=0.9, findings="", impression="", labels=("SomeFutureLabel",))
    voted = [VotedLabel(label="SomeFutureLabel", vote_weight=0.9, agreement=1.0)]
    session_id = _seed_session(db, ["u1"])

    service, provider = _make_service(db, {"u1": case_a}, voted)
    questionnaire = service.get_questionnaire(str(session_id))

    assert questionnaire.based_on_label == "SomeFutureLabel"
    assert questionnaire.questions == DEFAULT_QUESTIONS
    assert provider.calls == ["SomeFutureLabel"]
    db.close()


def test_session_not_found_raises_specific_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service, _ = _make_service(db, {}, [])

    with pytest.raises(SessionNotFoundError):
        service.get_questionnaire(str(uuid.uuid4()))
    db.close()


def test_malformed_session_id_raises_specific_error_not_a_crash():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service, _ = _make_service(db, {}, [])

    with pytest.raises(SessionNotFoundError):
        service.get_questionnaire("not-a-uuid-at-all")
    db.close()
