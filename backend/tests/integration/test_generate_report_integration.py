"""
Integration test: full real Phase 8 chain via FastAPI's TestClient. First
POST /retrieve (Phase 4's real, frozen endpoint) against a real masked
image to create a genuine RetrievalSession + RetrievedEvidence rows --
chosen over calling RetrievalService directly, since going through the
real HTTP endpoint end-to-end is the more integration-realistic path and
needs no duplicated persistence logic in this test. Then POST
/generate-report against that real session_id, exercising: real DB, real
ChromaVectorStore.get_by_ids, real LabelVotingService, real ContextBuilder,
real LLMOrchestrator (a real Ollama call), real ResponseValidator, real
ReportFormatter, real persistence. No fakes/mocks anywhere in this path.

Requires Ollama running locally with settings.OLLAMA_MODEL pulled (same
requirement as Phase 7's integration test) -- the client fixture checks
reachability first and skips with a clear, actionable message if it isn't
running, rather than silently faking a response.

Asserts STRUCTURAL/contract properties only (all frozen response fields
present, the persisted ReportRecord row matches the response exactly,
generation_metadata values match Settings) -- never asserts exact
ReportContent wording, same non-determinism discipline as Phase 7's
integration test (an LLM call is not guaranteed byte-identical run to run
even at temperature 0.0).
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.database.base import Base, SessionLocal, engine
from app.main import app
from app.models.report import ReportRecord

REPO_ROOT = Path(__file__).resolve().parents[3]
MASKED_DIR = REPO_ROOT / "ml" / "datasets" / "masked"


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
    if not _ollama_available():
        pytest.skip(
            f"Ollama not reachable at {settings.OLLAMA_BASE_URL} -- start Ollama and "
            f"ensure '{settings.OLLAMA_MODEL}' is pulled (`ollama pull {settings.OLLAMA_MODEL}`) "
            f"before running this integration test."
        )
    Base.metadata.create_all(engine)
    with TestClient(app, raise_server_exceptions=False) as c:
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


def test_generate_report_full_real_chain(client, real_session_id):
    start = time.perf_counter()
    response = client.post("/generate-report", json={"session_id": real_session_id, "language": "en"})
    elapsed = time.perf_counter() - start

    assert response.status_code == 200, f"unexpected status {response.status_code}: {response.text}"
    body = response.json()

    print(f"\n/generate-report real wall-clock time: {elapsed:.2f}s")
    print("REAL /generate-report response JSON:")
    print(json.dumps(body, indent=2, ensure_ascii=False))

    for field in ("report_id", "session_id", "formatted_report", "validation", "generation_metadata"):
        assert field in body, f"missing frozen contract field: {field}"
    assert body["session_id"] == real_session_id

    formatted_report = body["formatted_report"]
    for field in ("content", "language", "report_date", "section_headers"):
        assert field in formatted_report
    for field in (
        "examination", "clinical_history", "technique", "findings",
        "impression", "recommendation", "disclaimer",
    ):
        assert field in formatted_report["content"]
        assert isinstance(formatted_report["content"][field], str)
    assert formatted_report["language"] == "en"
    assert set(formatted_report["section_headers"].keys()) == {
        "examination", "clinical_history", "technique", "findings",
        "impression", "recommendation", "disclaimer",
    }

    validation = body["validation"]
    assert isinstance(validation["is_clean"], bool)
    assert isinstance(validation["warnings"], list)

    # generation_metadata values checked against the ACTUAL current Settings
    # (the real config this real run used), not just "some values present"
    generation_metadata = body["generation_metadata"]
    assert generation_metadata["llm_model"] == settings.OLLAMA_MODEL
    assert generation_metadata["llm_temperature"] == settings.LLM_TEMPERATURE
    assert generation_metadata["embedding_model"] == settings.CHROMA_EMBEDDING_MODEL
    assert generation_metadata["embedding_version"] == settings.CHROMA_EMBEDDING_VERSION
    assert generation_metadata["collection_name"] == settings.CHROMA_COLLECTION_NAME

    # a real ReportRecord row was persisted, matching the response exactly
    db = SessionLocal()
    try:
        report_id = uuid.UUID(body["report_id"])
        record = db.query(ReportRecord).filter(ReportRecord.id == report_id).one()
        assert str(record.session_id) == real_session_id
        assert record.language == "en"
        assert record.report_date == formatted_report["report_date"]
        assert record.llm_model == generation_metadata["llm_model"]
        assert record.llm_temperature == generation_metadata["llm_temperature"]
        assert record.embedding_model == generation_metadata["embedding_model"]
        assert record.embedding_version == generation_metadata["embedding_version"]
        assert record.collection_name == generation_metadata["collection_name"]
        assert record.validation_warnings == validation["warnings"]
        assert record.ai_content == formatted_report["content"]
    finally:
        db.close()
