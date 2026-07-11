"""
Unit tests for chroma_result_mapper.map_chroma_results.
Proves the distance->similarity conversion (similarity = 1 - cosine_distance)
and metadata field mapping are correct, using a hand-constructed fake
Chroma-shaped result dict -- no real ChromaDB involved.
"""
from __future__ import annotations

from app.infrastructure.chroma_result_mapper import map_chroma_results


def _fake_raw_result() -> dict:
    return {
        "ids": [["11", "22"]],
        "distances": [[0.0, 0.4]],
        "metadatas": [
            [
                {
                    "study_uid": "11",
                    "findings": "clear lungs",
                    "impression": "no acute findings",
                    "primary_label": "Normal",
                    "image_path": "ml/datasets/masked/11.png",
                    "cluster_id": 7,
                },
                {
                    "study_uid": "22",
                    "findings": "enlarged heart silhouette",
                    "impression": "cardiomegaly",
                    "primary_label": "Cardiomegaly",
                    "image_path": "ml/datasets/masked/22.png",
                    "cluster_id": -1,
                },
            ]
        ],
    }


def test_distance_to_similarity_conversion():
    cases = map_chroma_results(_fake_raw_result())
    assert cases[0].similarity == 1.0   # distance 0.0 -> identical vectors
    assert cases[1].similarity == 0.6   # distance 0.4 -> similarity 0.6


def test_field_mapping():
    cases = map_chroma_results(_fake_raw_result())
    first = cases[0]
    assert first.source_uid == "11"
    assert first.findings == "clear lungs"
    assert first.impression == "no acute findings"
    assert first.labels == ("Normal",)
    assert first.image_path == "ml/datasets/masked/11.png"
    assert first.cluster_id == 7


def test_result_order_preserved():
    cases = map_chroma_results(_fake_raw_result())
    assert [c.source_uid for c in cases] == ["11", "22"]


def test_empty_result():
    empty = {"ids": [[]], "distances": [[]], "metadatas": [[]]}
    assert map_chroma_results(empty) == []
