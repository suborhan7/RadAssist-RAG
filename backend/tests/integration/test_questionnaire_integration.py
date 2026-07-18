"""
Integration test: real QuestionnaireService against a real, persisted
session. A real POST /retrieve call (Phase 4's frozen endpoint, via
TestClient) creates a genuine RetrievalSession + RetrievedEvidence first --
same pattern as Phase 8's own integration test -- then a real
QuestionnaireService.get_questionnaire() call, using real ChromaVectorStore,
real LabelVotingService, and real QuestionnaireTemplateProvider (no fakes).

Does NOT require Ollama running -- get_questionnaire() never calls the LLM
(LLMOrchestrator is not one of its collaborators), unlike
test_generate_report_integration.py.

Asserts: the returned label matches what a fresh, independent
LabelVotingService.vote() call produces for the same real retrieved cases
(proving get_questionnaire's internal vote isn't silently different), and
the returned questions match questionnaire_templates' real data for that
label (not a fake/canned set).
"""
from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.database.base import Base, SessionLocal, engine
from app.domain.entities import RetrievalMetadata
from app.infrastructure.chroma_store import ChromaVectorStore
from app.main import app
from app.models.report import ReportRecord
from app.services.context_builder import ContextBuilder
from app.services.label_voting_service import LabelVotingService
from app.services.prompt_builder import PromptBuilder
from app.services.questionnaire_service import QuestionnaireService
from app.services.questionnaire_templates import QuestionnaireTemplateProvider
from app.services.session_reconstruction import reconstruct_session_evidence
from tests.integration.auth_helpers import register_test_doctor

REPO_ROOT = Path(__file__).resolve().parents[3]
MASKED_DIR = REPO_ROOT / "ml" / "datasets" / "masked"
CHROMA_PATH = REPO_ROOT / "ml" / "outputs" / "retrieval" / "chroma_db"


def _ollama_available() -> bool:
    try:
        response = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def _answer_for(question: dict) -> str:
    if question["input_type"] == "yes_no":
        return "yes"
    if question["input_type"] == "select":
        return "moderate"
    return f"Sample response for {question['key']}"


def _pick_sample_image() -> Path:
    for p in sorted(MASKED_DIR.glob("*.png")):
        return p
    pytest.skip(f"no masked images found under {MASKED_DIR}")


@pytest.fixture(scope="module")
def client():
    if not CHROMA_PATH.exists():
        pytest.skip(f"chroma_db not found at {CHROMA_PATH} -- run build_chroma_index.py first")
    Base.metadata.create_all(engine)
    with TestClient(app, raise_server_exceptions=False) as c:
        register_test_doctor(c)
        yield c
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="module")
def real_session_id(client) -> str:
    sample = _pick_sample_image()
    with open(sample, "rb") as f:
        response = client.post(
            "/retrieve",
            files={"file": (sample.name, f, "image/png")},
            data={"top_k": "5", "min_similarity": "0.0"},
        )
    assert response.status_code == 200, f"failed to create a real retrieval session: {response.text}"
    return response.json()["session_id"]


def test_get_questionnaire_for_real_session(client, real_session_id):
    vector_store = ChromaVectorStore()
    label_voting_service = LabelVotingService()
    questionnaire_provider = QuestionnaireTemplateProvider()

    db = SessionLocal()
    try:
        service = QuestionnaireService(
            db=db,
            vector_store=vector_store,
            label_voting_service=label_voting_service,
            questionnaire_provider=questionnaire_provider,
        )
        questionnaire = service.get_questionnaire(real_session_id)
    finally:
        db.close()

    print(f"\nreal session_id: {real_session_id}")
    print(f"real based_on_label: {questionnaire.based_on_label}")
    print("real questions:")
    for q in questionnaire.questions:
        print(f"  {q.key:25s} [{q.input_type:6s}] {q.text}")

    assert questionnaire.session_id == real_session_id
    assert len(questionnaire.questions) > 0

    # independent re-vote against the exact same real retrieved cases must
    # produce the same top label get_questionnaire used internally
    db2 = SessionLocal()
    try:
        from app.models.retrieval_session import RetrievalSession
        from app.models.retrieved_evidence import RetrievedEvidence
        import uuid as uuid_module

        evidence_rows = (
            db2.query(RetrievedEvidence)
            .filter(RetrievedEvidence.session_id == uuid_module.UUID(real_session_id))
            .order_by(RetrievedEvidence.rank)
            .all()
        )
        study_uids = [row.study_uid for row in evidence_rows]
        retrieved_cases = vector_store.get_by_ids(study_uids)
        independent_voted_labels = LabelVotingService().vote(retrieved_cases)
    finally:
        db2.close()

    assert independent_voted_labels, "expected at least one voted label for a real session"
    assert questionnaire.based_on_label == independent_voted_labels[0].label

    # questions match questionnaire_templates' real data for that label,
    # not a fake/canned set
    real_expected_questions = questionnaire_provider.get_questions_for_label(questionnaire.based_on_label)
    assert questionnaire.questions == real_expected_questions


def test_questionnaire_answers_reach_real_generated_prompt(client, real_session_id):
    """Step 8's full real flow: real /retrieve -> real GET /questionnaire
    -> real answers to the REAL question keys returned -> proof the
    answers/notes reach the real generated prompt -> real POST
    /generate-report with those same answers.

    Proof-of-reaching-the-LLM-prompt approach, stated explicitly: neither
    LLMOrchestrator nor OllamaClient expose the final prompt string
    anywhere capturable on a real call, and modifying either just to add
    an inspection hook would be scope creep on frozen Phase 7 files for a
    test-only need. Instead, this reconstructs the exact real
    ClinicalContext the real pipeline would build up to that point --
    real ChromaVectorStore.get_by_ids + real LabelVotingService.vote()
    (via the same shared reconstruct_session_evidence() used by both
    ReportGenerationService and QuestionnaireService) + real
    ContextBuilder.build() with the real submitted answers/notes -- and
    feeds it to the REAL PromptBuilder (not faked, since PromptBuilder is
    the exact component the Phase 9 pre-design verification found broken).
    This proves the answers reach the real generated prompt string
    directly and deterministically, with no LLM call and no non-
    determinism involved in that specific assertion.
    """
    if not _ollama_available():
        pytest.skip(
            f"Ollama not reachable at {settings.OLLAMA_BASE_URL} -- start Ollama and "
            f"ensure '{settings.OLLAMA_MODEL}' is pulled before running this integration test."
        )

    # 1. real GET /questionnaire/{session_id}
    q_response = client.get(f"/questionnaire/{real_session_id}")
    assert q_response.status_code == 200, f"unexpected status: {q_response.text}"
    questionnaire_body = q_response.json()
    assert questionnaire_body["session_id"] == real_session_id
    assert len(questionnaire_body["questions"]) > 0

    # 2. real answers to the REAL question keys returned (not arbitrary
    # made-up keys)
    answers = {q["key"]: _answer_for(q) for q in questionnaire_body["questions"]}
    clinical_notes = "Patient reports recent travel and a low-grade fever for the past three days."

    print(f"\nreal top label: {questionnaire_body['based_on_label']}")
    print(f"real question keys -> constructed real answers: {answers}")
    print(f"real clinical_notes: {clinical_notes!r}")

    # 3. PROOF: real PromptBuilder fed the real ClinicalContext the real
    # pipeline would build for this exact request
    db = SessionLocal()
    try:
        vector_store = ChromaVectorStore()
        label_voting_service = LabelVotingService()
        retrieval_session, retrieved_cases, voted_labels = reconstruct_session_evidence(
            db, vector_store, label_voting_service, real_session_id
        )
        retrieval_metadata = RetrievalMetadata(
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_model=settings.CHROMA_EMBEDDING_MODEL,
            embedding_version=settings.CHROMA_EMBEDDING_VERSION,
            retrieved_at=retrieval_session.created_at.isoformat() if retrieval_session.created_at else "",
        )
        context = ContextBuilder().build(
            retrieved_cases,
            voted_labels,
            questionnaire_answers=answers,
            clinical_notes=clinical_notes,
            retrieval_metadata=retrieval_metadata,
        )
    finally:
        db.close()

    prompt = PromptBuilder().build_generation_prompt(context, "en")

    print("\n=== real generated prompt excerpt (questionnaire/notes sections) ===")
    excerpt_start = prompt.index("CLINICAL QUESTIONNAIRE:")
    print(prompt[excerpt_start:])

    assert "CLINICAL QUESTIONNAIRE:" in prompt
    for key, value in answers.items():
        assert f"- {key}: {value}" in prompt
    assert "ADDITIONAL CLINICAL NOTES:" in prompt
    assert clinical_notes in prompt

    # 4. standard integration assertions: real POST /generate-report with
    # these same real answers/notes -> 200, frozen contract fields present,
    # real ReportRecord persisted matching the response
    response = client.post(
        "/generate-report",
        json={
            "session_id": real_session_id,
            "language": "en",
            "questionnaire_answers": answers,
            "clinical_notes": clinical_notes,
        },
    )
    assert response.status_code == 200, f"unexpected status: {response.text}"
    body = response.json()

    for field in ("report_id", "session_id", "formatted_report", "validation", "generation_metadata"):
        assert field in body, f"missing frozen contract field: {field}"
    assert body["session_id"] == real_session_id

    db2 = SessionLocal()
    try:
        report_id = uuid.UUID(body["report_id"])
        record = db2.query(ReportRecord).filter(ReportRecord.id == report_id).one()
        assert str(record.session_id) == real_session_id
        assert record.ai_draft_content == body["formatted_report"]["content"]
    finally:
        db2.close()
