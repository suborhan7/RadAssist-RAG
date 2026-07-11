"""
app/infrastructure/chroma_result_mapper.py
====================================================================
Pure function: chromadb's raw query() result dict -> list[RetrievedCase].
No I/O, no ChromaDB client dependency here -- keeps the distance->similarity
conversion and metadata mapping unit-testable without a real collection.

The iu_cxr_biomedclip_v1_train collection (ml/retrieval/build_chroma_index.py)
was created with metadata={"hnsw:space": "cosine"}. Verified against the real
collection: querying with an embedding identical to a stored one returns
distance == 0.0 for that record, i.e. Chroma returns COSINE DISTANCE
(1 - cosine_similarity), not similarity directly. So similarity = 1 - distance.
"""
from __future__ import annotations

from typing import Any

from app.domain.entities import RetrievedCase


def map_chroma_results(raw_result: dict[str, Any]) -> list[RetrievedCase]:
    """Maps a single-query chromadb collection.query() result to RetrievedCase list.

    Expects raw_result shaped like chromadb's client return value:
    {"ids": [[...]], "distances": [[...]], "metadatas": [[...]]}
    (outer list is per-query-embedding; only the first query is mapped, since
    RetrievalService always queries with exactly one embedding).
    """
    ids = raw_result["ids"][0]
    distances = raw_result["distances"][0]
    metadatas = raw_result["metadatas"][0]

    cases: list[RetrievedCase] = []
    for _id, distance, meta in zip(ids, distances, metadatas):
        similarity = 1.0 - distance
        # TODO: label_set parsing into multiple labels is not required yet --
        # single-label tuple from primary_label only, for now.
        cases.append(
            RetrievedCase(
                source_uid=str(meta.get("study_uid", _id)),
                similarity=similarity,
                findings=str(meta.get("findings", "")),
                impression=str(meta.get("impression", "")),
                labels=(str(meta.get("primary_label", "")),),
                image_path=str(meta.get("image_path", "")),
                cluster_id=int(meta.get("cluster_id", -1)),
            )
        )
    return cases
