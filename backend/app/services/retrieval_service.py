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
        return self.retrieve_by_vector(query_vector, top_k, min_similarity)

    def retrieve_by_vector(
        self, query_vector: list[float], top_k: int = 5, min_similarity: float = 0.0
    ) -> list[RetrievedCase]:
        """The query half of retrieve(), entered with an already-computed
        embedding.

        Required by the pipeline order frozen in §9 of
        input_admission_projection_gate_architecture_v1.1_FROZEN.md:

            ... -> EmbeddingService -> ModalityGateService -> RetrievalService

        ModalityGateService sits BETWEEN the embed step and the retrieval
        step, and M1 forbids it from encoding the image again -- it takes
        the existing vector as a parameter. retrieve() owns embed-then-
        query as one indivisible step, so there is no point inside it at
        which the gate could run. Splitting the query half out is what
        makes the frozen order expressible.

        This is an extraction, not a second retrieval path: retrieve()
        above now calls it, so both entry points run the identical
        query/select logic and cannot drift. Callers that already hold a
        vector (app/api/retrieval.py, which must embed the MASKED image
        itself so the gate and the retrieval judge the same tensor) use
        this one; callers that hold only a path keep using retrieve()
        unchanged, which is why the Phase 4 regression tests still
        describe real behavior.

        No validator call here, deliberately: the validator's subject is a
        file, and this method has no file. Admission (§5) happens further
        upstream, at the API boundary, on the raw upload bytes -- which is
        strictly earlier and strictly stronger than the Phase 4 check
        retrieve() performs.
        """
        raw_results = self._vector_store.query(query_vector, top_k)
        return self._search_policy.select(raw_results, top_k, min_similarity)
