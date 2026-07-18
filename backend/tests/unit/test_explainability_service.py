"""
Unit tests for ExplainabilityService, per the frozen Phase 10 architecture
(development_log.md, "Phase 10 -- Explainability Chat: Architecture
(FROZEN)"). DB access uses a real, throwaway in-memory SQLite session (same
pattern and reasoning as Phase 8/9's report_generation_service/
questionnaire_service tests) rather than a hand-built fake -- faking
SQLAlchemy's query/filter mechanics would be more complex and less
trustworthy, and it lets the atomic-persistence-failure test prove genuine
rollback behavior. Every non-DB collaborator (vector_store,
label_voting_service, context_builder, prompt_builder, llm_orchestrator)
is a hand-built fake.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.domain.entities import (
    ClinicalContext,
    EvidenceSummary,
    ReportContent,
    ReportStatus,
    RetrievalStats,
    RetrievedCase,
    VotedLabel,
)
from app.models.explanation import Explanation
from app.models.report import ReportRecord
from app.models.retrieval_session import RetrievalSession
from app.models.retrieved_evidence import RetrievedEvidence
from app.services.exceptions import ReportNotFoundError
from app.services.explainability_service import ExplainabilityService


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


class FakeContextBuilder:
    def __init__(self, context):
        self.context = context
        self.build_calls = []

    def build(self, retrieved, voted_labels, questionnaire_answers=None, clinical_notes="", retrieval_metadata=None):
        self.build_calls.append({"retrieved": list(retrieved), "voted_labels": list(voted_labels)})
        return self.context


class FakePromptBuilder:
    def __init__(self, prompt):
        self.prompt = prompt
        self.build_explanation_prompt_calls = []

    def build_explanation_prompt(self, report, question, evidence_summary):
        self.build_explanation_prompt_calls.append((report, question, evidence_summary))
        return self.prompt


class FakeLLMOrchestrator:
    def __init__(self, answer):
        self.answer = answer
        self.answer_question_calls = []

    def answer_question(self, prompt):
        self.answer_question_calls.append(prompt)
        return self.answer


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


CONTENT = ReportContent(
    examination="e", clinical_history="c", technique="t", findings="f",
    impression="i", recommendation="r", disclaimer="d",
)


def _seed_report(db, session_id: uuid.UUID) -> uuid.UUID:
    report_id = uuid.uuid4()
    db.add(
        ReportRecord(
            id=report_id, session_id=session_id, language="en", status=ReportStatus.AI_DRAFT,
            ai_draft_content=asdict(CONTENT), final_content=asdict(CONTENT),
            validation_warnings=[], report_date="2026-07-13",
            llm_model="llama3:8b", llm_temperature=0.0, embedding_model="biomedclip",
            embedding_version="v1", collection_name="iu_cxr_biomedclip_v1_train",
        )
    )
    db.commit()
    return report_id


def _evidence_summary() -> EvidenceSummary:
    return EvidenceSummary(
        top_retrieved_case=None, findings_evidence=(), impressions_evidence=(),
        retrieval_stats=RetrievalStats(0, 0, 0, 0.0, 0.0, 0.0, 0, 0),
        retrieval_metadata=None, label_evidence=(),
    )


def _make_service(db, cases_by_uid, voted_labels, context, answer="a real-sounding answer"):
    fakes = {
        "vector_store": FakeVectorStore(cases_by_uid),
        "label_voting_service": FakeLabelVoter(voted_labels),
        "context_builder": FakeContextBuilder(context),
        "prompt_builder": FakePromptBuilder("EXPLANATION_PROMPT"),
        "llm_orchestrator": FakeLLMOrchestrator(answer),
    }
    service = ExplainabilityService(
        db=db,
        vector_store=fakes["vector_store"],
        label_voting_service=fakes["label_voting_service"],
        context_builder=fakes["context_builder"],
        prompt_builder=fakes["prompt_builder"],
        llm_orchestrator=fakes["llm_orchestrator"],
    )
    return service, fakes


def test_correct_sequencing_and_data_flow():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()

    case_a = RetrievedCase(source_uid="u1", similarity=1.0, findings="fa", impression="ia", labels=("Pneumonia",))
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=0.5)]
    context = ClinicalContext(retrieved_cases=(case_a,), voted_labels=tuple(voted), evidence_summary=_evidence_summary())

    session_id = _seed_session(db, ["u1"])
    report_id = _seed_report(db, session_id)

    service, fakes = _make_service(db, {"u1": case_a}, voted, context, answer="Because the finding is stable.")

    question = "Why do you think this is pneumonia?"
    current_doctor_id = str(uuid.uuid4())
    result = service.explain(str(report_id), question, current_doctor_id=current_doctor_id)

    # evidence reconstruction: get_by_ids -> vote -> context_builder.build
    assert fakes["vector_store"].get_by_ids_calls == [["u1"]]
    assert fakes["label_voting_service"].vote_calls == [[case_a]]
    assert fakes["context_builder"].build_calls[0]["retrieved"] == [case_a]
    assert fakes["context_builder"].build_calls[0]["voted_labels"] == voted

    # prompt_builder.build_explanation_prompt called with (report, question, evidence_summary)
    report_arg, question_arg, evidence_summary_arg = fakes["prompt_builder"].build_explanation_prompt_calls[0]
    assert question_arg == question
    assert evidence_summary_arg is context.evidence_summary
    assert report_arg.ai_draft_content == CONTENT
    assert report_arg.study_id == str(session_id)  # documented substitution, see module docstring

    # llm_orchestrator.answer_question called with the built prompt
    assert fakes["llm_orchestrator"].answer_question_calls == ["EXPLANATION_PROMPT"]

    # return value
    assert result.answer == "Because the finding is stable."
    assert result.question == question
    assert result.report_id == str(report_id)

    # real Explanation row persisted
    record = db.query(Explanation).filter(Explanation.report_id == report_id).one()
    assert record.question == question
    assert record.answer == "Because the finding is stable."
    assert str(record.id) == result.id
    assert record.doctor_id == uuid.UUID(current_doctor_id)

    db.close()


def test_report_not_found_raises_specific_error_before_touching_collaborators():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service, fakes = _make_service(db, {}, [], None)

    with pytest.raises(ReportNotFoundError):
        service.explain(str(uuid.uuid4()), "Why?")

    assert fakes["vector_store"].get_by_ids_calls == []
    assert fakes["llm_orchestrator"].answer_question_calls == []
    assert db.query(Explanation).count() == 0

    db.close()


def test_malformed_report_id_raises_specific_error_not_a_crash():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service, fakes = _make_service(db, {}, [], None)

    with pytest.raises(ReportNotFoundError):
        service.explain("not-a-uuid-at-all", "Why?")

    assert fakes["vector_store"].get_by_ids_calls == []
    db.close()


def test_atomic_persistence_failure_leaves_zero_rows(monkeypatch):
    engine = _make_engine()
    db = sessionmaker(bind=engine)()

    case_a = RetrievedCase(source_uid="u1", similarity=1.0, findings="fa", impression="ia", labels=("Pneumonia",))
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=0.5)]
    context = ClinicalContext(retrieved_cases=(case_a,), voted_labels=tuple(voted), evidence_summary=_evidence_summary())
    session_id = _seed_session(db, ["u1"])
    report_id = _seed_report(db, session_id)

    service, fakes = _make_service(db, {"u1": case_a}, voted, context)

    def failing_commit(self):
        # real proof, not a trivial short-circuit: actually flush the
        # pending INSERT before failing, same pattern as every prior
        # atomic-persistence test in this project.
        self.flush()
        raise RuntimeError("simulated persistence failure after flush, before commit")

    monkeypatch.setattr(SASession, "commit", failing_commit)

    with pytest.raises(RuntimeError, match="simulated persistence failure"):
        service.explain(str(report_id), "Why?")

    monkeypatch.undo()
    fresh_db = sessionmaker(bind=engine)()
    try:
        assert fresh_db.query(Explanation).count() == 0
    finally:
        fresh_db.close()

    db.close()
