"""
Integration test: real BiomedCLIPAdapter + real ChromaVectorStore against
the actual iu_cxr_biomedclip_v1_train collection built by
ml/retrieval/build_chroma_index.py. No fakes/mocks -- proves the full
Phase 4 retrieval path works end to end against real infrastructure.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.infrastructure.biomedclip_adapter import BiomedCLIPAdapter
from app.infrastructure.chroma_store import ChromaVectorStore
from app.services.image_validator import ImageValidator
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


def test_retrieval_returns_nonempty_results(retrieval_service):
    query_image = _pick_query_image()
    results = retrieval_service.retrieve(query_image, top_k=5, min_similarity=0.0)
    assert len(results) > 0


def test_retrieved_image_paths_exist(retrieval_service):
    query_image = _pick_query_image()
    results = retrieval_service.retrieve(query_image, top_k=5, min_similarity=0.0)
    for case in results:
        assert case.image_path, f"empty image_path for source_uid={case.source_uid}"
        assert os.path.isfile(REPO_ROOT / case.image_path), (
            f"image_path does not exist on disk: {case.image_path}"
        )


def test_similarities_descending(retrieval_service):
    query_image = _pick_query_image()
    results = retrieval_service.retrieve(query_image, top_k=5, min_similarity=0.0)
    similarities = [c.similarity for c in results]
    assert similarities == sorted(similarities, reverse=True)


def test_top1_similarity_reasonably_high(retrieval_service):
    query_image = _pick_query_image()
    results = retrieval_service.retrieve(query_image, top_k=5, min_similarity=0.0)
    assert results[0].similarity > 0.5
