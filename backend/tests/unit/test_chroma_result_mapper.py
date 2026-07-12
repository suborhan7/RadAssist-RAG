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


def _fake_result_with_meta(meta: dict) -> dict:
    return {
        "ids": [["1"]],
        "distances": [[0.0]],
        "metadatas": [[meta]],
    }


def test_multi_label_case_puts_primary_label_first_not_alphabetically_first():
    # label_set is alphabetically sorted (real index behavior) and would
    # NOT put "Cardiomegaly" first if naively split -- this proves the
    # labels[0] == primary_label convention survives multi-label parsing.
    meta = {
        "study_uid": "1",
        "findings": "f",
        "impression": "i",
        "primary_label": "Cardiomegaly",
        "label_set": "Atelectasis;Cardiomegaly;Effusion",
        "image_path": "x.png",
        "cluster_id": 1,
    }
    cases = map_chroma_results(_fake_result_with_meta(meta))
    labels = cases[0].labels
    assert labels[0] == "Cardiomegaly"
    assert set(labels) == {"Atelectasis", "Cardiomegaly", "Effusion"}
    assert len(labels) == len(set(labels))  # no duplicates


def test_single_label_case_produces_clean_one_tuple():
    meta = {
        "study_uid": "1",
        "findings": "f",
        "impression": "i",
        "primary_label": "Normal",
        "label_set": "Normal",
        "image_path": "x.png",
        "cluster_id": -1,
    }
    cases = map_chroma_results(_fake_result_with_meta(meta))
    assert cases[0].labels == ("Normal",)


def test_empty_label_set_falls_back_to_primary_label_only():
    meta = {
        "study_uid": "1",
        "findings": "f",
        "impression": "i",
        "primary_label": "Normal",
        "label_set": "",
        "image_path": "x.png",
        "cluster_id": -1,
    }
    cases = map_chroma_results(_fake_result_with_meta(meta))
    assert cases[0].labels == ("Normal",)
