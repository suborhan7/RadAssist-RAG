"""
Unit tests for ComparisonService, per the frozen Phase 11 architecture
(development_log.md, "Phase 11 -- Longitudinal Patient History &
Comparison: Architecture (FROZEN)", "Unit testing strategy" section).

DB access (ReportRecord/RetrievalSession/ComparisonRecord lookups and
persistence) is exercised against a REAL, throwaway in-memory SQLite
session -- same reasoning as Phase 8 Step 6/Phase 9's atomicity tests:
faking SQLAlchemy's query mechanics would be less trustworthy than a real,
disposable DB, and it's required to prove genuine commit/rollback
behavior in the atomic-persistence-failure test. Every non-DB collaborator
(patient_repository, deterministic_comparator, prompt_builder,
llm_orchestrator) is a hand-built fake, per the frozen spec's "all
collaborators faked" unit testing strategy.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.domain.entities import (
    ComparisonFacts,
    Language,
    Report,
    ReportContent,
    ReportStatus,
)
from app.models.comparison import ComparisonRecord
from app.models.report import ReportRecord
from app.models.retrieval_session import RetrievalSession
from app.services.comparison_service import ComparisonService
from app.services.exceptions import NoPriorReportError, ReportNotFoundError

CONTENT = ReportContent(
    examination="e", clinical_history="c", technique="t", findings="f",
    impression="i", recommendation="r", disclaimer="d",
)


class FakePatientRepository:
    def __init__(self, history_by_patient_id: dict[str, list[Report]]) -> None:
        self.history_by_patient_id = history_by_patient_id
        self.get_history_calls: list[str] = []

    def create(self, name, date_of_birth, gender):
        raise NotImplementedError

    def find_by_code(self, patient_code):
        raise NotImplementedError

    def find_by_name_and_dob(self, name, date_of_birth):
        raise NotImplementedError

    def get_history(self, patient_id: str) -> list[Report]:
        self.get_history_calls.append(patient_id)
        return self.history_by_patient_id.get(patient_id, [])


class FakeDeterministicComparator:
    def __init__(self, facts: ComparisonFacts) -> None:
        self.facts = facts
        self.compare_calls: list[tuple] = []

    def compare(self, previous, current, previous_date, current_date, previous_report_id, current_report_id):
        self.compare_calls.append(
            (previous, current, previous_date, current_date, previous_report_id, current_report_id)
        )
        return self.facts


class FakePromptBuilder:
    def __init__(self, prompt: str = "COMPARISON PROMPT") -> None:
        self.prompt = prompt
        self.build_comparison_prompt_calls: list[tuple] = []

    def build_comparison_prompt(self, facts, previous, current):
        self.build_comparison_prompt_calls.append((facts, previous, current))
        return self.prompt


class FakeLLMOrchestrator:
    def __init__(self, narrative: str = "The pneumonia has resolved.") -> None:
        self.narrative = narrative
        self.answer_question_calls: list[str] = []

    def generate_draft(self, context, language):
        raise NotImplementedError

    def answer_question(self, prompt: str) -> str:
        self.answer_question_calls.append(prompt)
        return self.narrative


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


def _seed_report(db, patient_id, created_at: datetime, report_date: str, content: ReportContent = CONTENT) -> uuid.UUID:
    session_id = _seed_session(db, patient_id=patient_id)
    report_id = uuid.uuid4()
    db.add(
        ReportRecord(
            id=report_id, session_id=session_id, language="en", status=ReportStatus.AI_DRAFT,
            ai_draft_content=asdict(content), final_content=asdict(content),
            validation_warnings=[], report_date=report_date,
            llm_model="llama3:8b", llm_temperature=0.0, embedding_model="biomedclip",
            embedding_version="v1", collection_name="iu_cxr_biomedclip_v1_train",
            created_at=created_at,
        )
    )
    db.commit()
    return report_id


def _domain_report(report_id: uuid.UUID, content: ReportContent = CONTENT) -> Report:
    return Report(
        id=str(report_id), study_id="s", language=Language.ENGLISH, status=ReportStatus.AI_DRAFT,
        ai_draft_content=content, final_content=ReportContent(),
    )


def _facts() -> ComparisonFacts:
    return ComparisonFacts(
        previous_report_id="ignored-placeholder", current_report_id="ignored-placeholder",
        resolved_findings=("Pneumonia",), persistent_findings=(), new_findings=(),
        days_between_studies=14,
    )


def _make_service(db, history_by_patient_id=None, facts=None):
    fakes = {
        "patient_repository": FakePatientRepository(history_by_patient_id or {}),
        "deterministic_comparator": FakeDeterministicComparator(facts or _facts()),
        "prompt_builder": FakePromptBuilder(),
        "llm_orchestrator": FakeLLMOrchestrator(),
    }
    service = ComparisonService(
        db=db,
        patient_repository=fakes["patient_repository"],
        deterministic_comparator=fakes["deterministic_comparator"],
        prompt_builder=fakes["prompt_builder"],
        llm_orchestrator=fakes["llm_orchestrator"],
    )
    return service, fakes


def test_correct_sequencing_and_call_order_with_explicit_compare_against():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    patient_id = str(uuid.uuid4())
    previous_content = CONTENT
    current_content = ReportContent(
        examination="e2", clinical_history="c2", technique="t2", findings="f2",
        impression="i2", recommendation="r2", disclaimer="d2",
    )
    previous_id = _seed_report(db, None, datetime(2026, 1, 1, tzinfo=timezone.utc), "2026-01-01", previous_content)
    current_id = _seed_report(db, None, datetime(2026, 1, 15, tzinfo=timezone.utc), "2026-01-15", current_content)

    service, fakes = _make_service(db)
    current_doctor_id = str(uuid.uuid4())

    result = service.compare(
        patient_id, str(current_id), compare_against_report_id=str(previous_id), current_doctor_id=current_doctor_id
    )

    # deterministic_comparator called with the correct content/dates/ids, in order
    assert fakes["deterministic_comparator"].compare_calls == [
        (previous_content, current_content, "2026-01-01", "2026-01-15", str(previous_id), str(current_id))
    ]
    # prompt_builder called with the facts the comparator returned, plus both contents
    assert fakes["prompt_builder"].build_comparison_prompt_calls == [
        (fakes["deterministic_comparator"].facts, previous_content, current_content)
    ]
    # llm_orchestrator called with the prompt build_comparison_prompt returned
    assert fakes["llm_orchestrator"].answer_question_calls == [fakes["prompt_builder"].prompt]

    # explicit compare_against_report_id bypasses history resolution entirely
    assert fakes["patient_repository"].get_history_calls == []

    # persisted correctly
    persisted = db.query(ComparisonRecord).one()
    assert persisted.patient_id == uuid.UUID(patient_id)
    assert persisted.previous_report_id == previous_id
    assert persisted.current_report_id == current_id
    assert persisted.llm_narrative == fakes["llm_orchestrator"].narrative
    assert persisted.doctor_id == uuid.UUID(current_doctor_id)

    # returned Comparison domain entity matches
    assert result.patient_id == patient_id
    assert result.previous_report_id == str(previous_id)
    assert result.current_report_id == str(current_id)
    assert result.facts == fakes["deterministic_comparator"].facts
    assert result.narrative == fakes["llm_orchestrator"].narrative

    db.close()


def test_resolves_most_recent_prior_via_get_history_when_no_compare_against_given():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    patient_id = str(uuid.uuid4())
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)

    oldest_id = _seed_report(db, None, base, "2026-01-01")
    middle_id = _seed_report(db, None, base + timedelta(days=10), "2026-01-11")  # true "most recent prior"
    current_id = _seed_report(db, None, base + timedelta(days=20), "2026-01-21")

    # get_history() returns ascending chronological order, including the
    # current report itself (same as PatientService.get_history()'s real
    # behavior against RetrievalSession.patient_id)
    history = {
        patient_id: [
            _domain_report(oldest_id),
            _domain_report(middle_id),
            _domain_report(current_id),
        ]
    }
    service, fakes = _make_service(db, history_by_patient_id=history)

    service.compare(patient_id, str(current_id))

    assert fakes["patient_repository"].get_history_calls == [patient_id]
    # previous_report_id in the compare() call must be middle_id, NOT oldest_id
    call = fakes["deterministic_comparator"].compare_calls[0]
    assert call[4] == str(middle_id)  # previous_report_id
    assert call[5] == str(current_id)  # current_report_id

    db.close()


def test_no_prior_report_raises_no_prior_report_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    patient_id = str(uuid.uuid4())
    current_id = _seed_report(db, None, datetime(2026, 1, 1, tzinfo=timezone.utc), "2026-01-01")

    # patient's history contains ONLY the current report -- first visit
    history = {patient_id: [_domain_report(current_id)]}
    service, fakes = _make_service(db, history_by_patient_id=history)

    with pytest.raises(NoPriorReportError, match="no prior report"):
        service.compare(patient_id, str(current_id))

    # no ComparisonRecord should have been persisted
    assert db.query(ComparisonRecord).count() == 0

    db.close()


def test_malformed_current_report_id_raises_report_not_found_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service, _ = _make_service(db)

    with pytest.raises(ReportNotFoundError, match="not a valid UUID"):
        service.compare(str(uuid.uuid4()), "not-a-uuid")

    db.close()


def test_nonexistent_current_report_id_raises_report_not_found_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service, _ = _make_service(db)

    with pytest.raises(ReportNotFoundError, match="no ReportRecord found"):
        service.compare(str(uuid.uuid4()), str(uuid.uuid4()))

    db.close()


def test_nonexistent_compare_against_report_id_raises_report_not_found_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    current_id = _seed_report(db, None, datetime(2026, 1, 1, tzinfo=timezone.utc), "2026-01-01")
    service, _ = _make_service(db)

    with pytest.raises(ReportNotFoundError, match="no ReportRecord found"):
        service.compare(str(uuid.uuid4()), str(current_id), compare_against_report_id=str(uuid.uuid4()))

    db.close()


def test_atomic_persistence_failure_leaves_zero_rows(monkeypatch):
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    previous_id = _seed_report(db, None, datetime(2026, 1, 1, tzinfo=timezone.utc), "2026-01-01")
    current_id = _seed_report(db, None, datetime(2026, 1, 15, tzinfo=timezone.utc), "2026-01-15")
    service, _ = _make_service(db)

    def failing_commit(self):
        # real proof, not a trivial short-circuit: flush the pending INSERT
        # before failing, simulating a failure between "row sent to the DB"
        # and "transaction finalized" -- same pattern as Phase 4/8's
        # atomicity tests.
        self.flush()
        raise RuntimeError("simulated persistence failure after flush, before commit")

    monkeypatch.setattr(SASession, "commit", failing_commit)

    with pytest.raises(RuntimeError, match="simulated persistence failure"):
        service.compare(str(uuid.uuid4()), str(current_id), compare_against_report_id=str(previous_id))

    monkeypatch.undo()
    fresh_db = SessionLocal()
    try:
        assert fresh_db.query(ComparisonRecord).count() == 0
    finally:
        fresh_db.close()

    db.close()
