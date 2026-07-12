"""
Integration test: real OllamaClient + real PromptBuilder + real
StructuralValidator, driven by a real ClinicalContext built via the real,
frozen retrieval -> voting -> ContextBuilder pipeline (Phases 4/5, same
fixture pattern as test_context_builder_integration.py) -> real
LLMOrchestrator.generate_draft(). No fakes/mocks anywhere in this path.

Asserts STRUCTURAL properties only, per the frozen Phase 7 architecture:
returns a ReportContent, all 7 fields present and are strings. Does NOT
assert exact content/wording -- LLM output is genuinely non-deterministic
even at temperature=0.0 (batched-inference floating-point non-associativity
is a documented limitation, not an oversight -- see the Phase 7 frozen
architecture's "Determinism rules" section), so pinning a test to exact
text would make it flaky by design.

Requires Ollama running locally with settings.OLLAMA_MODEL pulled.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.core.config import settings
from app.infrastructure.biomedclip_adapter import BiomedCLIPAdapter
from app.infrastructure.chroma_store import ChromaVectorStore
from app.infrastructure.ollama_client import OllamaClient
from app.services.context_builder import ContextBuilder
from app.services.image_validator import ImageValidator
from app.services.label_voting_service import LabelVotingService
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.prompt_builder import PromptBuilder
from app.services.retrieval_service import RetrievalService
from app.services.similarity_search import SimilaritySearchPolicy
from app.services.structural_validator import StructuralValidator

REPO_ROOT = Path(__file__).resolve().parents[3]
CHROMA_PATH = REPO_ROOT / "ml" / "outputs" / "retrieval" / "chroma_db"
MASKED_DIR = REPO_ROOT / "ml" / "datasets" / "masked"


def _pick_query_image() -> str:
    for p in sorted(MASKED_DIR.glob("*.png")):
        return str(p)
    pytest.skip(f"no masked images found under {MASKED_DIR}")


@pytest.fixture(scope="module")
def real_clinical_context():
    if not CHROMA_PATH.exists():
        pytest.skip(f"chroma_db not found at {CHROMA_PATH} -- run build_chroma_index.py first")
    validator = ImageValidator()
    embedder = BiomedCLIPAdapter()
    vector_store = ChromaVectorStore(persist_path=str(CHROMA_PATH))
    search_policy = SimilaritySearchPolicy()
    retrieval_service = RetrievalService(validator, embedder, vector_store, search_policy)

    query_image = _pick_query_image()
    retrieved_cases = retrieval_service.retrieve(query_image, top_k=5, min_similarity=0.0)
    voted_labels = LabelVotingService().vote(retrieved_cases)
    return ContextBuilder().build(retrieved_cases, voted_labels)


def test_llm_orchestrator_generates_structurally_valid_report(real_clinical_context):
    orchestrator = LLMOrchestrator(
        prompt_builder=PromptBuilder(),
        llm_client=OllamaClient(),
        structural_validator=StructuralValidator(),
        transport_retry_count=settings.LLM_TRANSPORT_RETRY_COUNT,
        content_retry_count=settings.LLM_CONTENT_RETRY_COUNT,
    )

    start = time.perf_counter()
    report_content = orchestrator.generate_draft(real_clinical_context, "en")
    elapsed_seconds = time.perf_counter() - start

    print(f"\ngenerate_draft() real wall-clock time: {elapsed_seconds:.2f}s "
          f"(OLLAMA_TIMEOUT_SECONDS={settings.OLLAMA_TIMEOUT_SECONDS})")
    print("REAL GENERATED ReportContent:")
    for field_name in ("examination", "clinical_history", "technique", "findings",
                       "impression", "recommendation", "disclaimer"):
        print(f"--- {field_name} ---")
        print(getattr(report_content, field_name))

    assert report_content is not None
    for field_name in ("examination", "clinical_history", "technique", "findings",
                       "impression", "recommendation", "disclaimer"):
        value = getattr(report_content, field_name)
        assert isinstance(value, str)
