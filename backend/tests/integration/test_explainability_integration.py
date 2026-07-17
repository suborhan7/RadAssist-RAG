"""
Integration test: full real Phase 10 chain via FastAPI's TestClient.
A real report is produced by chaining a real POST /retrieve (Phase 4's
frozen endpoint) -> real POST /generate-report (Phase 8's endpoint) --
same self-contained pattern already used by
test_questionnaire_integration.py and test_generate_report_integration.py
(chained directly in this test's own fixture, rather than importing
another test module's fixtures across files) -- then a real
POST /reports/{report_id}/explain with a real question against that real
report_id, exercising the entire real chain: real DB fetch of the
ReportRecord, real reconstruct_session_evidence, real Report/ReportContent
reconstruction from persisted ai_content, real
PromptBuilder.build_explanation_prompt, real LLMOrchestrator.answer_question
(a real Ollama call), real persistence.

Requires Ollama running locally with settings.OLLAMA_MODEL pulled (same
requirement as every prior real-LLM integration test) -- the client
fixture checks reachability first and skips with a clear, actionable
message if it isn't running.

Asserts STRUCTURAL/contract properties only (200 response, all frozen
response fields present, the persisted Explanation row matches the
response field-for-field) -- never asserts exact answer wording, same
non-determinism discipline as every real-LLM integration test so far.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.database.base import Base, SessionLocal, engine
from app.main import app
from app.models.explanation import Explanation
from tests.integration.auth_helpers import register_test_doctor

REPO_ROOT = Path(__file__).resolve().parents[3]
MASKED_DIR = REPO_ROOT / "ml" / "datasets" / "masked"
CHROMA_PATH = REPO_ROOT / "ml" / "outputs" / "retrieval" / "chroma_db"


def _pick_sample_image() -> Path:
    for p in sorted(MASKED_DIR.glob("*.png")):
        return p
    pytest.skip(f"no masked images found under {MASKED_DIR}")


def _ollama_available() -> bool:
    try:
        response = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="module")
def client():
    if not CHROMA_PATH.exists():
        pytest.skip(f"chroma_db not found at {CHROMA_PATH} -- run build_chroma_index.py first")
    if not _ollama_available():
        pytest.skip(
            f"Ollama not reachable at {settings.OLLAMA_BASE_URL} -- start Ollama and "
            f"ensure '{settings.OLLAMA_MODEL}' is pulled before running this integration test."
        )
    Base.metadata.create_all(engine)
    with TestClient(app, raise_server_exceptions=False) as c:
        register_test_doctor(c)
        yield c
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="module")
def real_report_id(client) -> str:
    sample = _pick_sample_image()
    with open(sample, "rb") as f:
        retrieve_response = client.post(
            "/retrieve",
            files={"file": (sample.name, f, "image/png")},
            data={"top_k": "5", "min_similarity": "0.0"},
        )
    assert retrieve_response.status_code == 200, f"failed to create a real retrieval session: {retrieve_response.text}"
    session_id = retrieve_response.json()["session_id"]

    generate_response = client.post(
        "/generate-report", json={"session_id": session_id, "language": "en"}
    )
    assert generate_response.status_code == 200, f"failed to create a real report: {generate_response.text}"
    return generate_response.json()["report_id"]


def test_explain_report_full_real_chain(client, real_report_id):
    question = "Why do you think this finding is significant, and what should the clinician watch for?"

    response = client.post(f"/reports/{real_report_id}/explain", json={"question": question})
    assert response.status_code == 200, f"unexpected status {response.status_code}: {response.text}"
    body = response.json()

    print(f"\nreal report_id: {real_report_id}")
    print(f"real question: {question}")
    print("\n=== REAL ANSWER (model's actual response) ===")
    print(body["answer"])

    for field in ("id", "report_id", "question", "answer", "created_at"):
        assert field in body, f"missing frozen contract field: {field}"

    assert body["report_id"] == real_report_id
    assert body["question"] == question
    assert isinstance(body["answer"], str)
    assert body["answer"].strip() != ""

    assert body["created_at"].strip() != ""

    # a real Explanation row persisted, matching the response exactly
    db = SessionLocal()
    try:
        explanation_id = uuid.UUID(body["id"])
        record = db.query(Explanation).filter(Explanation.id == explanation_id).one()
        assert str(record.report_id) == real_report_id
        assert record.question == question
        assert record.answer == body["answer"]
        assert record.created_at is not None
    finally:
        db.close()
