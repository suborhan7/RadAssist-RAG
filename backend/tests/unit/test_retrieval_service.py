"""
Unit tests for RetrievalService. All 4 collaborators are fakes/mocks --
no real ChromaDB or BiomedCLIP involved. Asserts call order, correct
pass-through of search_policy's output, and short-circuit on validation
failure.
"""
from __future__ import annotations

import pytest

from app.domain.entities import RetrievedCase
from app.services.retrieval_service import RetrievalService


class RecordingFake:
    """Base fake that records when it was called, for order assertions."""

    def __init__(self, call_log: list[str]):
        self._call_log = call_log


class FakeValidator(RecordingFake):
    def __init__(self, call_log, should_raise=False):
        super().__init__(call_log)
        self.should_raise = should_raise

    def validate(self, image_path: str) -> None:
        self._call_log.append("validate")
        if self.should_raise:
            raise ValueError("invalid image")


class FakeEmbedder(RecordingFake):
    def embed_image(self, image_path: str) -> list[float]:
        self._call_log.append("embed_image")
        return [0.1, 0.2, 0.3]

    def embed_text(self, text: str) -> list[float]:
        return [0.0]


class FakeVectorStore(RecordingFake):
    def __init__(self, call_log, raw_results):
        super().__init__(call_log)
        self._raw_results = raw_results
        self.received_embedding = None
        self.received_top_k = None

    def query(self, embedding, top_k):
        self._call_log.append("query")
        self.received_embedding = embedding
        self.received_top_k = top_k
        return self._raw_results

    def upsert(self, uid, embedding, metadata):
        pass


class FakeSearchPolicy(RecordingFake):
    def __init__(self, call_log, selected_results):
        super().__init__(call_log)
        self._selected_results = selected_results
        self.received_args = None

    def select(self, raw_results, top_k, min_similarity):
        self._call_log.append("select")
        self.received_args = (raw_results, top_k, min_similarity)
        return self._selected_results


def _sample_case(uid: str, sim: float) -> RetrievedCase:
    return RetrievedCase(source_uid=uid, similarity=sim, findings="f", impression="i")


def test_call_order_and_return_value():
    call_log: list[str] = []
    raw_results = [_sample_case("a", 0.9), _sample_case("b", 0.4)]
    selected = [_sample_case("a", 0.9)]

    validator = FakeValidator(call_log)
    embedder = FakeEmbedder(call_log)
    vector_store = FakeVectorStore(call_log, raw_results)
    search_policy = FakeSearchPolicy(call_log, selected)

    service = RetrievalService(validator, embedder, vector_store, search_policy)
    result = service.retrieve("dummy.png", top_k=1, min_similarity=0.5)

    assert call_log == ["validate", "embed_image", "query", "select"]
    assert result is selected
    assert vector_store.received_top_k == 1
    assert search_policy.received_args == (raw_results, 1, 0.5)


def test_validator_raises_short_circuits_pipeline():
    call_log: list[str] = []
    validator = FakeValidator(call_log, should_raise=True)
    embedder = FakeEmbedder(call_log)
    vector_store = FakeVectorStore(call_log, [])
    search_policy = FakeSearchPolicy(call_log, [])

    service = RetrievalService(validator, embedder, vector_store, search_policy)

    with pytest.raises(ValueError, match="invalid image"):
        service.retrieve("bad.png")

    assert call_log == ["validate"]
