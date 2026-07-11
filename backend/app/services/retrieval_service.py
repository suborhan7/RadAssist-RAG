"""
app/services/retrieval_service.py
====================================================================
RetrievalService: pure orchestrator over its four injected collaborators.
No business logic here -- if logic accumulates in this class, it belongs
in one of the collaborators instead.
"""
from __future__ import annotations

from app.domain.entities import RetrievedCase
from app.domain.interfaces import (
    IEmbedder,
    IImageValidator,
    ISimilaritySearchPolicy,
    IVectorStore,
)


class RetrievalService:
    def __init__(
        self,
        validator: IImageValidator,
        embedder: IEmbedder,
        vector_store: IVectorStore,
        search_policy: ISimilaritySearchPolicy,
    ) -> None:
        self._validator = validator
        self._embedder = embedder
        self._vector_store = vector_store
        self._search_policy = search_policy

    def retrieve(
        self, image_path: str, top_k: int = 5, min_similarity: float = 0.0
    ) -> list[RetrievedCase]:
        self._validator.validate(image_path)
        query_vector = self._embedder.embed_image(image_path)
        raw_results = self._vector_store.query(query_vector, top_k)
        return self._search_policy.select(raw_results, top_k, min_similarity)
