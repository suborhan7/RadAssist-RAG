"""
Unit tests for ReportGenerationService, per the frozen Phase 8 architecture
(development_log.md, "Phase 8 -- Response Validator + Hospital Report
Formatter: Architecture (FROZEN)", "Unit testing strategy" section).

DB access is exercised against a REAL, throwaway in-memory SQLite session
(via SQLAlchemy's own Session class, same engine shared across a test via
StaticPool) rather than a hand-built fake -- faking SQLAlchemy's query/
filter/order_by mechanics would be more complex to write and less
trustworthy than just using a real, fast, disposable DB, and it lets the
atomic-persistence-failure test prove genuine rollback behavior (same
pattern as Phase 4's test_transaction_atomicity_on_persistence_failure),
not just "my code calls .rollback() when .commit() raises." Every
non-DB collaborator (vector_store, label_voting_service, context_builder,
llm_orchestrator, response_validator, report_formatter) is a hand-built
fake, per the frozen spec's "all collaborators faked" unit testing
strategy.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database.base import Base
from app.domain.entities import (
    ClinicalContext,
    EvidenceSummary,
    FormattedReport,
    ReportContent,
    ReportStatus,
    RetrievalStats,
    RetrievedCase,
    SemanticValidationResult,
    VotedLabel,
)
from app.models.report import ReportRecord
from app.models.retrieval_session import RetrievalSession
from app.models.retrieved_evidence import RetrievedEvidence
from app.services.exceptions import LLMGenerationValidationError, LLMTransportError, SessionNotFoundError
from app.services.report_generation_service import ReportGenerationService


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
        self.build_calls.append(
            {
                "retrieved": list(retrieved),
                "voted_labels": list(voted_labels),
                "questionnaire_answers": questionnaire_answers,
                "clinical_notes": clinical_notes,
                "retrieval_metadata": retrieval_metadata,
            }
        )
        return self.context


class FakeLLMOrchestrator:
    def __init__(self, content=None, raises=None):
        self.content = content
        self.raises = raises
        self.generate_draft_calls = []

    def generate_draft(self, context, language):
        self.generate_draft_calls.append((context, language))
        if self.raises is not None:
            raise self.raises
        return self.content


class FakeResponseValidator:
    def __init__(self, result):
        self.result = result
        self.validate_semantic_calls = []

    def validate_semantic(self, content, evidence_summary, voted_labels):
        self.validate_semantic_calls.append((content, evidence_summary, list(voted_labels)))
        return self.result


class FakeReportFormatter:
    def __init__(self, formatted_report):
        self.formatted_report = formatted_report
        self.format_calls = []

    def format(self, content, language, report_date):
        self.format_calls.append((content, language, report_date))
        return self.formatted_report


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine


def _seed_session(db: SASession, study_uids: list[str]) -> uuid.UUID:
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
VALIDATION_RESULT = SemanticValidationResult(
    missing_findings=False, missing_impression=False, unsupported_terms=(),
    top_label_unreflected=False, warnings=("some warning",), is_clean=False,
)
FORMATTED_REPORT = FormattedReport(content=CONTENT, language="en", report_date="2026-07-12", section_headers={})


def _evidence_summary() -> EvidenceSummary:
    return EvidenceSummary(
        top_retrieved_case=None, findings_evidence=(), impressions_evidence=(),
        retrieval_stats=RetrievalStats(0, 0, 0, 0.0, 0.0, 0.0, 0, 0),
        retrieval_metadata=None, label_evidence=(),
    )


def _make_service(db, cases_by_uid, voted_labels, context, llm_content=None, llm_raises=None):
    fakes = {
        "vector_store": FakeVectorStore(cases_by_uid),
        "label_voting_service": FakeLabelVoter(voted_labels),
        "context_builder": FakeContextBuilder(context),
        "llm_orchestrator": FakeLLMOrchestrator(content=llm_content, raises=llm_raises),
        "response_validator": FakeResponseValidator(VALIDATION_RESULT),
        "report_formatter": FakeReportFormatter(FORMATTED_REPORT),
    }
    service = ReportGenerationService(
        db=db,
        vector_store=fakes["vector_store"],
        label_voting_service=fakes["label_voting_service"],
        context_builder=fakes["context_builder"],
        llm_orchestrator=fakes["llm_orchestrator"],
        response_validator=fakes["response_validator"],
        report_formatter=fakes["report_formatter"],
    )
    return service, fakes


def test_correct_sequencing_and_data_flow():
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    case_a = RetrievedCase(source_uid="u1", similarity=1.0, findings="fa", impression="ia", labels=("Pneumonia",))
    case_b = RetrievedCase(source_uid="u2", similarity=1.0, findings="fb", impression="ib", labels=("Normal",))
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=0.5)]
    context = ClinicalContext(retrieved_cases=(case_a, case_b), voted_labels=tuple(voted), evidence_summary=_evidence_summary())

    session_id = _seed_session(db, ["u1", "u2"])
    retrieval_session = db.query(RetrievalSession).filter(RetrievalSession.id == session_id).one()

    service, fakes = _make_service(
        db, {"u1": case_a, "u2": case_b}, voted, context, llm_content=CONTENT,
    )

    report_id, formatted_report, validation_result, generation_metadata = service.generate(str(session_id), "en")

    # 1-2-3: fetch + study_uids extraction + get_by_ids, in rank order
    assert fakes["vector_store"].get_by_ids_calls == [["u1", "u2"]]
    # 4: vote called with exactly what get_by_ids returned
    assert fakes["label_voting_service"].vote_calls == [[case_a, case_b]]
    # 5: context_builder.build called with retrieved + voted_labels + retrieval_metadata
    build_call = fakes["context_builder"].build_calls[0]
    assert build_call["retrieved"] == [case_a, case_b]
    assert build_call["voted_labels"] == voted
    assert build_call["retrieval_metadata"].collection_name == settings.CHROMA_COLLECTION_NAME
    assert build_call["retrieval_metadata"].embedding_model == settings.CHROMA_EMBEDDING_MODEL
    assert build_call["retrieval_metadata"].embedding_version == settings.CHROMA_EMBEDDING_VERSION
    assert build_call["retrieval_metadata"].retrieved_at == retrieval_session.created_at.isoformat()
    # Phase 9: questionnaire_answers/clinical_notes default to {}/"" when omitted
    assert build_call["questionnaire_answers"] == {}
    assert build_call["clinical_notes"] == ""
    # 6: llm_orchestrator.generate_draft called with (context, language)
    assert fakes["llm_orchestrator"].generate_draft_calls == [(context, "en")]
    # 7: response_validator.validate_semantic called with (content, evidence_summary, voted_labels)
    assert fakes["response_validator"].validate_semantic_calls == [(CONTENT, context.evidence_summary, voted)]
    # 8-9: report_formatter.format called with (content, language, today's UTC date)
    today = datetime.now(timezone.utc).date().isoformat()
    assert fakes["report_formatter"].format_calls == [(CONTENT, "en", today)]
    # 11: return value matches (now a 4-tuple: report_id, formatted_report,
    # validation_result, generation_metadata)
    assert formatted_report is FORMATTED_REPORT
    assert validation_result is VALIDATION_RESULT

    # 10: ReportRecord persisted with correct fields
    record = db.query(ReportRecord).filter(ReportRecord.session_id == session_id).one()
    assert report_id == record.id
    assert record.language == "en"
    assert record.status == ReportStatus.AI_DRAFT
    assert record.ai_draft_content == {
        "examination": "e", "clinical_history": "c", "technique": "t",
        "findings": "f", "impression": "i", "recommendation": "r", "disclaimer": "d",
    }
    assert record.final_content == record.ai_draft_content
    assert record.validation_warnings == ["some warning"]
    assert record.report_date == today
    assert record.llm_model == settings.OLLAMA_MODEL
    assert record.llm_temperature == settings.LLM_TEMPERATURE
    assert record.embedding_model == settings.CHROMA_EMBEDDING_MODEL
    assert record.embedding_version == settings.CHROMA_EMBEDDING_VERSION
    assert record.collection_name == settings.CHROMA_COLLECTION_NAME
    # Phase 19 Decision 4: persisted, not just passed to context_builder --
    # {}/"" here (both real, non-None values), never NULL, since this call
    # omitted both and generate() normalizes None -> {} before this point.
    assert record.questionnaire_answers == {}
    assert record.clinical_notes == ""

    # generation_metadata mirrors exactly what was persisted, not re-queried
    assert generation_metadata.llm_model == record.llm_model
    assert generation_metadata.llm_temperature == record.llm_temperature
    assert generation_metadata.embedding_model == record.embedding_model
    assert generation_metadata.embedding_version == record.embedding_version
    assert generation_metadata.collection_name == record.collection_name

    db.close()


def test_session_not_found_raises_specific_error_before_touching_collaborators():
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    service, fakes = _make_service(db, {}, [], None, llm_content=CONTENT)

    with pytest.raises(SessionNotFoundError):
        service.generate(str(uuid.uuid4()), "en")

    assert fakes["vector_store"].get_by_ids_calls == []
    assert fakes["label_voting_service"].vote_calls == []
    assert fakes["llm_orchestrator"].generate_draft_calls == []
    assert db.query(ReportRecord).count() == 0

    db.close()


def test_malformed_session_id_raises_specific_error_not_a_crash():
    """session_id isn't even a valid UUID string -- must still raise
    SessionNotFoundError cleanly, not a raw exception from deep inside the
    DBAPI parameter binding (the actual bug caught while writing this
    suite: a bare str was originally passed straight into a Uuid-typed
    column filter)."""
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    service, fakes = _make_service(db, {}, [], None, llm_content=CONTENT)

    with pytest.raises(SessionNotFoundError):
        service.generate("not-a-uuid-at-all", "en")

    assert fakes["vector_store"].get_by_ids_calls == []
    db.close()


def test_llm_transport_error_propagates_unchanged_and_nothing_persisted():
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    case_a = RetrievedCase(source_uid="u1", similarity=1.0, findings="fa", impression="ia", labels=("Pneumonia",))
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=0.5)]
    context = ClinicalContext(retrieved_cases=(case_a,), voted_labels=tuple(voted), evidence_summary=_evidence_summary())
    session_id = _seed_session(db, ["u1"])

    service, fakes = _make_service(
        db, {"u1": case_a}, voted, context, llm_raises=LLMTransportError("simulated transport failure"),
    )

    with pytest.raises(LLMTransportError):
        service.generate(str(session_id), "en")

    assert db.query(ReportRecord).count() == 0
    db.close()


def test_llm_generation_validation_error_propagates_unchanged_and_nothing_persisted():
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    case_a = RetrievedCase(source_uid="u1", similarity=1.0, findings="fa", impression="ia", labels=("Pneumonia",))
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=0.5)]
    context = ClinicalContext(retrieved_cases=(case_a,), voted_labels=tuple(voted), evidence_summary=_evidence_summary())
    session_id = _seed_session(db, ["u1"])

    error = LLMGenerationValidationError(last_raw_response="bad json", last_validation_errors=["oops"])
    service, fakes = _make_service(db, {"u1": case_a}, voted, context, llm_raises=error)

    with pytest.raises(LLMGenerationValidationError) as exc_info:
        service.generate(str(session_id), "en")

    assert exc_info.value.last_raw_response == "bad json"
    assert exc_info.value.last_validation_errors == ["oops"]
    assert db.query(ReportRecord).count() == 0
    db.close()


def test_atomic_persistence_failure_leaves_zero_rows(monkeypatch):
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    case_a = RetrievedCase(source_uid="u1", similarity=1.0, findings="fa", impression="ia", labels=("Pneumonia",))
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=0.5)]
    context = ClinicalContext(retrieved_cases=(case_a,), voted_labels=tuple(voted), evidence_summary=_evidence_summary())
    session_id = _seed_session(db, ["u1"])

    service, fakes = _make_service(db, {"u1": case_a}, voted, context, llm_content=CONTENT)

    def failing_commit(self):
        # real proof, not a trivial short-circuit: actually flush the
        # pending INSERT before failing, simulating a failure between
        # "row sent to the DB" and "transaction finalized" -- same pattern
        # as Phase 4's test_transaction_atomicity_on_persistence_failure.
        self.flush()
        raise RuntimeError("simulated persistence failure after flush, before commit")

    monkeypatch.setattr(SASession, "commit", failing_commit)

    with pytest.raises(RuntimeError, match="simulated persistence failure"):
        service.generate(str(session_id), "en")

    monkeypatch.undo()
    # fresh session against the same engine to confirm nothing leaked
    fresh_db = SessionLocal()
    try:
        assert fresh_db.query(ReportRecord).count() == 0
    finally:
        fresh_db.close()

    db.close()


def test_no_questionnaire_data_produces_byte_identical_behavior_to_phase_8():
    """The required Phase 9 regression test, and the most important one in
    this phase. Proof strategy, stated explicitly:

    1. Call generate() TWICE on the exact same real session/language: once
       with questionnaire_answers/clinical_notes OMITTED entirely (relying
       on the new defaults), once EXPLICITLY passing questionnaire_answers={}
       and clinical_notes="". report_id legitimately differs between the
       two calls (a fresh ReportRecord row is persisted each time -- that
       is expected, not a bug), but formatted_report/validation_result/
       generation_metadata must be identical, AND the actual arguments
       reaching context_builder.build() (captured by FakeContextBuilder)
       must be identical too -- proving "omitted" and "explicitly empty"
       are genuinely the same code path, not two paths that coincidentally
       produce the same fake output.
    2. test_correct_sequencing_and_data_flow above (Phase 8's own original
       test, left unmodified except for two new assertion lines that check
       the *new* default values -- none of its Phase 8 assertions were
       touched or loosened) is re-run as part of this same file/suite and
       still passes verbatim. Combined with (1), this demonstrates the
       Phase 9 extension did not alter Phase 8's already-shipped,
       already-tested no-questionnaire behavior at all.
    """
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    case_a = RetrievedCase(source_uid="u1", similarity=1.0, findings="fa", impression="ia", labels=("Pneumonia",))
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=0.5)]
    context = ClinicalContext(retrieved_cases=(case_a,), voted_labels=tuple(voted), evidence_summary=_evidence_summary())
    session_id = _seed_session(db, ["u1"])

    service, fakes = _make_service(db, {"u1": case_a}, voted, context, llm_content=CONTENT)

    # call 1: new params OMITTED entirely
    report_id_1, formatted_report_1, validation_1, generation_metadata_1 = service.generate(str(session_id), "en")

    # call 2: new params EXPLICITLY passed as empty
    report_id_2, formatted_report_2, validation_2, generation_metadata_2 = service.generate(
        str(session_id), "en", questionnaire_answers={}, clinical_notes="",
    )

    assert report_id_1 != report_id_2  # legitimately different rows, expected
    assert formatted_report_1 == formatted_report_2
    assert validation_1 == validation_2
    assert generation_metadata_1 == generation_metadata_2

    # the actual arguments context_builder.build() received are identical
    # between the two calls -- not just the final fake-returned output
    call_1, call_2 = fakes["context_builder"].build_calls[0], fakes["context_builder"].build_calls[1]
    assert call_1["questionnaire_answers"] == {} and call_2["questionnaire_answers"] == {}
    assert call_1["clinical_notes"] == "" and call_2["clinical_notes"] == ""
    assert call_1 == call_2

    db.close()


def test_questionnaire_answers_and_notes_reach_context_builder_when_provided():
    """Fake ContextBuilder capturing its call arguments -- proves non-empty
    questionnaire_answers/clinical_notes actually reach the
    context_builder.build() call, not just accepted and silently dropped
    (the exact Phase 6/9 gap this phase's pre-design verification found in
    PromptBuilder, checked here one layer up the call chain)."""
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    case_a = RetrievedCase(source_uid="u1", similarity=1.0, findings="fa", impression="ia", labels=("Pneumonia",))
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=0.5)]
    context = ClinicalContext(retrieved_cases=(case_a,), voted_labels=tuple(voted), evidence_summary=_evidence_summary())
    session_id = _seed_session(db, ["u1"])

    service, fakes = _make_service(db, {"u1": case_a}, voted, context, llm_content=CONTENT)

    answers = {"duration": "3 days", "fever": "yes"}
    notes = "Patient reports recent travel"
    report_id, _, _, _ = service.generate(
        str(session_id), "en", questionnaire_answers=answers, clinical_notes=notes
    )

    build_call = fakes["context_builder"].build_calls[0]
    assert build_call["questionnaire_answers"] == answers
    assert build_call["clinical_notes"] == notes

    # Phase 19 Decision 4: also persisted onto the real row, not just
    # forwarded to context_builder and then dropped on the floor at the
    # DB-write step -- the real gap Step 1 found for existing reports.
    record = db.query(ReportRecord).filter(ReportRecord.id == report_id).one()
    assert record.questionnaire_answers == answers
    assert record.clinical_notes == notes


def test_questionnaire_answers_and_clinical_notes_are_never_null_for_one_but_not_the_other():
    """Phase 19: proves the invariant the regenerate-section design relies
    on -- questionnaire_answers and clinical_notes are always NULL/non-NULL
    TOGETHER, never exactly one of them, for any report this service ever
    creates. generate() normalizes BOTH on its own first two lines
    (questionnaire_answers or {}, clinical_notes or "") -- structurally
    guaranteed by this service's own code, not merely true because the API
    layer's Pydantic type happens to forbid a null clinical_notes today
    (see the next test, which proves this directly by bypassing that type
    entirely)."""
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    case_a = RetrievedCase(source_uid="u1", similarity=1.0, findings="fa", impression="ia", labels=("Pneumonia",))
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=0.5)]
    context = ClinicalContext(retrieved_cases=(case_a,), voted_labels=tuple(voted), evidence_summary=_evidence_summary())
    session_id = _seed_session(db, ["u1"])

    service, fakes = _make_service(db, {"u1": case_a}, voted, context, llm_content=CONTENT)

    # Both entirely omitted -- the "nothing provided" path.
    report_id, _, _, _ = service.generate(str(session_id), "en")
    record = db.query(ReportRecord).filter(ReportRecord.id == report_id).one()
    assert record.questionnaire_answers is not None
    assert record.clinical_notes is not None
    # AND and OR agree here precisely because neither is ever null alone.
    both_null = record.questionnaire_answers is None and record.clinical_notes is None
    either_null = record.questionnaire_answers is None or record.clinical_notes is None
    assert both_null == either_null == False


def test_generate_normalizes_clinical_notes_even_if_a_caller_passes_none_directly():
    """Real proof the guarantee lives in THIS service, not just in the API
    layer's Pydantic type -- Python does not enforce type hints at
    runtime, so nothing stops a direct caller (a future second endpoint,
    a script, a test) from passing clinical_notes=None despite the `str`
    annotation. Before this phase's fix, that would have persisted a real
    NULL clinical_notes alongside a real questionnaire_answers dict --
    exactly the asymmetric state the regenerate-section design's
    context_incomplete check (AND, not OR) would have silently
    under-reported as complete. Calling generate() with an explicit
    clinical_notes=None here, bypassing the type hint entirely, is the
    only way to actually prove the normalization runs regardless of
    caller discipline."""
    engine = _make_engine()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    case_a = RetrievedCase(source_uid="u1", similarity=1.0, findings="fa", impression="ia", labels=("Pneumonia",))
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=0.5)]
    context = ClinicalContext(retrieved_cases=(case_a,), voted_labels=tuple(voted), evidence_summary=_evidence_summary())
    session_id = _seed_session(db, ["u1"])

    service, fakes = _make_service(db, {"u1": case_a}, voted, context, llm_content=CONTENT)

    answers = {"duration": "3 days"}
    report_id, _, _, _ = service.generate(
        str(session_id), "en", questionnaire_answers=answers, clinical_notes=None,  # type: ignore[arg-type]
    )

    record = db.query(ReportRecord).filter(ReportRecord.id == report_id).one()
    assert record.questionnaire_answers == answers  # real, non-empty dict
    assert record.clinical_notes == ""  # normalized, NOT None
    assert record.clinical_notes is not None

    db.close()
