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
from app.domain.entities import ReportContent, ReportStatus, RetrievedCase
from app.models.report import ReportRecord
from app.models.report_audit_log import ReportAuditLog
from app.models.retrieval_session import RetrievalSession
from app.models.retrieved_evidence import RetrievedEvidence
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
            }
        )
        return self.context


class FakePromptBuilder:
    def __init__(self, prompt):
        self.prompt = prompt
        self.build_section_regeneration_prompt_calls = []

    def build_section_regeneration_prompt(self, context, language, field):
        self.build_section_regeneration_prompt_calls.append((context, language, field))
        return self.prompt


class FakeLLMOrchestrator:
    def __init__(self, candidate):
        self.candidate = candidate
        self.generate_freeform_calls = []

    def generate_freeform(self, prompt):
        self.generate_freeform_calls.append(prompt)
        return self.candidate


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine


def _seed_session(
    db, doctor_id: uuid.UUID | None, study_uids: list[str] | None = None
) -> uuid.UUID:
    session_id = uuid.uuid4()
    study_uids = study_uids or []
    db.add(
        RetrievalSession(
            id=session_id, query_image_path="query.png", top_k=max(len(study_uids), 1),
            min_similarity=0.0, num_results=len(study_uids), retrieval_time_ms=10, doctor_id=doctor_id,
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


def _seed_report(
    db,
    session_id: uuid.UUID,
    status: ReportStatus = ReportStatus.AI_DRAFT,
    questionnaire_answers: dict | None = None,
    clinical_notes: str | None = None,
) -> uuid.UUID:
    report_id = uuid.uuid4()
    db.add(
        ReportRecord(
            id=report_id, session_id=session_id, language="en", status=status,
            ai_draft_content=asdict(CONTENT), final_content=asdict(CONTENT),
            validation_warnings=[], report_date="2026-07-13",
            llm_model="llama3:8b", llm_temperature=0.0, embedding_model="biomedclip",
            embedding_version="v1", collection_name="iu_cxr_biomedclip_v1_train",
            questionnaire_answers=questionnaire_answers, clinical_notes=clinical_notes,
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


# --- Phase 19: regenerate_section() ---


def _make_regenerate_service(db, cases_by_uid, voted_labels, context, candidate="regenerated text"):
    fakes = {
        "vector_store": FakeVectorStore(cases_by_uid),
        "label_voting_service": FakeLabelVoter(voted_labels),
        "context_builder": FakeContextBuilder(context),
        "prompt_builder": FakePromptBuilder("SECTION_REGEN_PROMPT"),
        "llm_orchestrator": FakeLLMOrchestrator(candidate),
    }
    service = ReportEditService(
        db,
        vector_store=fakes["vector_store"],
        label_voting_service=fakes["label_voting_service"],
        context_builder=fakes["context_builder"],
        llm_orchestrator=fakes["llm_orchestrator"],
        prompt_builder=fakes["prompt_builder"],
    )
    return service, fakes


def test_regenerate_section_returns_candidate_without_persisting():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    case_a = RetrievedCase(source_uid="u1", similarity=0.9, findings="fa", impression="ia", labels=("Pneumonia",))
    session_id = _seed_session(db, owner_id, study_uids=["u1"])
    report_id = _seed_report(
        db, session_id, questionnaire_answers={"duration": "3 days"}, clinical_notes="real notes",
    )

    service, fakes = _make_regenerate_service(db, {"u1": case_a}, [], context=None, candidate="new findings text")
    candidate, context_incomplete = service.regenerate_section(str(report_id), "findings", str(owner_id))

    assert candidate == "new findings text"
    assert context_incomplete is False

    # nothing persisted -- Decision 1
    record = db.query(ReportRecord).filter(ReportRecord.id == report_id).one()
    assert record.status == ReportStatus.AI_DRAFT
    assert record.final_content["findings"] == "f"  # untouched original
    assert db.query(ReportAuditLog).count() == 0

    db.close()


def test_regenerate_section_reconstructs_evidence_and_calls_llm_orchestrator():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    case_a = RetrievedCase(source_uid="u1", similarity=0.9, findings="fa", impression="ia", labels=("Pneumonia",))
    voted = ["some-voted-label"]
    session_id = _seed_session(db, owner_id, study_uids=["u1"])
    report_id = _seed_report(db, session_id)

    service, fakes = _make_regenerate_service(db, {"u1": case_a}, voted, context="THE_CONTEXT")
    service.regenerate_section(str(report_id), "impression", str(owner_id))

    build_call = fakes["context_builder"].build_calls[0]
    assert build_call["retrieved"] == [case_a]
    assert build_call["voted_labels"] == voted

    assert fakes["prompt_builder"].build_section_regeneration_prompt_calls == [("THE_CONTEXT", "en", "impression")]
    assert fakes["llm_orchestrator"].generate_freeform_calls == ["SECTION_REGEN_PROMPT"]

    db.close()


def test_regenerate_section_non_owner_raises_forbidden_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    other_doctor_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id, study_uids=["u1"])
    report_id = _seed_report(db, session_id)
    case_a = RetrievedCase(source_uid="u1", similarity=0.9, findings="fa", impression="ia", labels=())

    service, fakes = _make_regenerate_service(db, {"u1": case_a}, [], context=None)
    with pytest.raises(ForbiddenError):
        service.regenerate_section(str(report_id), "findings", str(other_doctor_id))

    assert fakes["llm_orchestrator"].generate_freeform_calls == []

    db.close()


def test_regenerate_section_on_final_report_raises_already_finalized_error():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id, study_uids=["u1"])
    report_id = _seed_report(db, session_id, status=ReportStatus.FINAL)
    case_a = RetrievedCase(source_uid="u1", similarity=0.9, findings="fa", impression="ia", labels=())

    service, fakes = _make_regenerate_service(db, {"u1": case_a}, [], context=None)
    with pytest.raises(ReportAlreadyFinalizedError):
        service.regenerate_section(str(report_id), "findings", str(owner_id))

    assert fakes["llm_orchestrator"].generate_freeform_calls == []

    db.close()


def test_regenerate_section_context_incomplete_true_when_both_columns_null():
    """Pre-migration report: questionnaire_answers/clinical_notes both NULL
    -- the real 'unknown original context' state (Phase 19 Decision 4)."""
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id, study_uids=["u1"])
    report_id = _seed_report(db, session_id, questionnaire_answers=None, clinical_notes=None)
    case_a = RetrievedCase(source_uid="u1", similarity=0.9, findings="fa", impression="ia", labels=())

    service, fakes = _make_regenerate_service(db, {"u1": case_a}, [], context=None)
    _, context_incomplete = service.regenerate_section(str(report_id), "findings", str(owner_id))

    assert context_incomplete is True

    db.close()


def test_regenerate_section_context_incomplete_false_when_both_columns_real():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id, study_uids=["u1"])
    report_id = _seed_report(db, session_id, questionnaire_answers={}, clinical_notes="")
    case_a = RetrievedCase(source_uid="u1", similarity=0.9, findings="fa", impression="ia", labels=())

    service, fakes = _make_regenerate_service(db, {"u1": case_a}, [], context=None)
    _, context_incomplete = service.regenerate_section(str(report_id), "findings", str(owner_id))

    assert context_incomplete is False

    db.close()


@pytest.mark.parametrize(
    "questionnaire_answers,clinical_notes",
    [
        (None, "real notes, questionnaire_answers somehow NULL"),
        ({"duration": "3 days"}, None),
    ],
)
def test_regenerate_section_context_incomplete_asymmetric_state_documented(
    questionnaire_answers, clinical_notes,
):
    """ReportGenerationService.generate() is now fixed (Phase 19) so it can
    never itself persist exactly one of these two columns as NULL -- see
    that service's own test proving the normalization runs regardless of
    caller. This asymmetric state is therefore not reachable through any
    real generation path any more, but a row could still end up this way
    through direct DB manipulation, a future bug, or data from before this
    fix -- so the CURRENT, INTENTIONAL behavior for that state is locked
    in here, not left undocumented. AND (not OR) reports this as NOT
    incomplete (False), by design: AND specifically distinguishes "both
    NULL together" (genuinely unknown original context) from any state
    where at least one real value exists -- switching to OR would not
    change behavior for any state generate() can actually produce (proven
    equivalent there), but WOULD misreport a doctor's real, deliberate
    empty answer (a known, non-NULL {}/"" pair) as incomplete if it were
    ever compared against a differently-null-shaped row -- not a concern
    this test exercises directly, but the reason AND is the considered
    choice, not an oversight now that both directions are covered."""
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id, study_uids=["u1"])
    report_id = _seed_report(
        db, session_id, questionnaire_answers=questionnaire_answers, clinical_notes=clinical_notes,
    )
    case_a = RetrievedCase(source_uid="u1", similarity=0.9, findings="fa", impression="ia", labels=())

    service, fakes = _make_regenerate_service(db, {"u1": case_a}, [], context=None)
    _, context_incomplete = service.regenerate_section(str(report_id), "findings", str(owner_id))

    assert context_incomplete is False


def test_regenerate_section_passes_none_clinical_notes_as_empty_string_to_context_builder():
    """The exact wiring gap Step 3 found: ContextBuilder.build() normalizes
    questionnaire_answers (None -> {}) itself, but has no equivalent
    normalization for clinical_notes -- regenerate_section() must do
    `record.clinical_notes or ""` itself, or this would crash later in
    PromptBuilder's `.strip()` call instead of degrading gracefully."""
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    owner_id = uuid.uuid4()
    session_id = _seed_session(db, owner_id, study_uids=["u1"])
    report_id = _seed_report(db, session_id, questionnaire_answers=None, clinical_notes=None)
    case_a = RetrievedCase(source_uid="u1", similarity=0.9, findings="fa", impression="ia", labels=())

    service, fakes = _make_regenerate_service(db, {"u1": case_a}, [], context=None)
    service.regenerate_section(str(report_id), "findings", str(owner_id))

    build_call = fakes["context_builder"].build_calls[0]
    assert build_call["clinical_notes"] == ""
    assert build_call["clinical_notes"] is not None
    # questionnaire_answers is passed through as None -- ContextBuilder's
    # OWN normalization (already verified) handles that side safely.
    assert build_call["questionnaire_answers"] is None

    db.close()
