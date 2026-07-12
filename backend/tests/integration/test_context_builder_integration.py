"""
Integration test: real RetrievalService + real LabelVotingService (frozen,
unmodified since Phase 4) against a real image from ml/datasets/masked/,
feeding real output into ContextBuilder.build() (Phase 5). No fakes/mocks
-- proves the full retrieval -> voting -> context-building path works end
to end against real infrastructure (ChromaDB + BiomedCLIP).

retrieval_metadata is constructed from app.core.config.settings, the same
real configuration values (CHROMA_COLLECTION_NAME/EMBEDDING_MODEL/
EMBEDDING_VERSION) that the /retrieve endpoint's _build_response() uses
for this exact retrieval call (see app/api/retrieval.py) -- chosen so
evidence_summary comes back fully populated with no None fields at all,
rather than leaving retrieval_metadata as the untested None branch (that
branch is already covered by test_context_builder.py's unit tests).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.config import settings
from app.domain.entities import RetrievalMetadata
from app.infrastructure.biomedclip_adapter import BiomedCLIPAdapter
from app.infrastructure.chroma_store import ChromaVectorStore
from app.services.context_builder import ContextBuilder
from app.services.image_validator import ImageValidator
from app.services.label_voting_service import LabelVotingService
from app.services.retrieval_service import RetrievalService
from app.services.similarity_search import SimilaritySearchPolicy

REPO_ROOT = Path(__file__).resolve().parents[3]
CHROMA_PATH = REPO_ROOT / "ml" / "outputs" / "retrieval" / "chroma_db"
MASKED_DIR = REPO_ROOT / "ml" / "datasets" / "masked"


def _pick_query_image() -> str:
    for p in sorted(MASKED_DIR.glob("*.png")):
        return str(p)
    pytest.skip(f"no masked images found under {MASKED_DIR}")


@pytest.fixture(scope="module")
def retrieval_service() -> RetrievalService:
    if not CHROMA_PATH.exists():
        pytest.skip(f"chroma_db not found at {CHROMA_PATH} -- run build_chroma_index.py first")
    validator = ImageValidator()
    embedder = BiomedCLIPAdapter()
    vector_store = ChromaVectorStore(persist_path=str(CHROMA_PATH))
    search_policy = SimilaritySearchPolicy()
    return RetrievalService(validator, embedder, vector_store, search_policy)


def test_context_builder_against_real_retrieval_and_voting(retrieval_service):
    query_image = _pick_query_image()

    retrieved_cases = retrieval_service.retrieve(query_image, top_k=5, min_similarity=0.0)
    voted_labels = LabelVotingService().vote(retrieved_cases)

    metadata = RetrievalMetadata(
        collection_name=settings.CHROMA_COLLECTION_NAME,
        embedding_model=settings.CHROMA_EMBEDDING_MODEL,
        embedding_version=settings.CHROMA_EMBEDDING_VERSION,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )

    # no exceptions raised anywhere in the real pipeline
    context = ContextBuilder().build(
        retrieved_cases, voted_labels, retrieval_metadata=metadata
    )

    es = context.evidence_summary
    assert es is not None

    # evidence_summary fully populated -- no None fields anywhere
    # (retrieval_metadata included, since we supplied a real one above)
    assert es.top_retrieved_case is not None
    assert es.retrieval_stats is not None
    assert es.retrieval_metadata is not None
    assert es.retrieval_metadata == metadata

    # top_retrieved_case matches the actual highest-similarity case in the
    # real retrieved list (pre-dedup raw retrieval, since real retrieval
    # results here have no near-dup collisions to collapse in top_k=5)
    highest_similarity_case = max(retrieved_cases, key=lambda c: c.similarity)
    assert es.top_retrieved_case.similarity == pytest.approx(highest_similarity_case.similarity)
    assert es.top_retrieved_case.similarity == max(c.similarity for c in context.retrieved_cases)

    # label_evidence: single partition for the top voted label; supporting
    # + contradictory must sum to exactly num_cases_after_dedup, no overlap
    assert len(es.label_evidence) == 1
    partition = es.label_evidence[0]
    assert partition.label == voted_labels[0].label

    supporting_uids = {c.source_uid for c in partition.supporting_cases}
    contradictory_uids = {c.source_uid for c in partition.contradictory_cases}
    assert supporting_uids.isdisjoint(contradictory_uids)
    assert len(partition.supporting_cases) + len(partition.contradictory_cases) == (
        es.retrieval_stats.num_cases_after_dedup
    )
    assert (supporting_uids | contradictory_uids) == {c.source_uid for c in context.retrieved_cases}
