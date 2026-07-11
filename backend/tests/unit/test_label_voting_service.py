"""
Unit tests for LabelVotingService, hand-calculated expected output per the
frozen formula: weight(L) = sum(similarity_i for cases carrying L),
predicted label = argmax(weight(L)), agreement = fraction of retrieved
cases carrying the predicted label (generalized here to every label in
the returned list -- see label_voting_service.py docstring).
"""
from __future__ import annotations

import pytest

from app.domain.entities import RetrievedCase
from app.services.label_voting_service import LabelVotingService


def _case(uid: str, similarity: float, *labels: str) -> RetrievedCase:
    return RetrievedCase(source_uid=uid, similarity=similarity, findings="", impression="", labels=labels)


def test_single_label_weighted_vote_hand_calculated():
    # weight(Normal) = 0.9 + 0.5 = 1.4, weight(Cardiomegaly) = 0.6
    # n = 3 -> agreement(Normal) = 2/3, agreement(Cardiomegaly) = 1/3
    cases = [
        _case("a", 0.9, "Normal"),
        _case("b", 0.6, "Cardiomegaly"),
        _case("c", 0.5, "Normal"),
    ]
    voted = LabelVotingService().vote(cases)

    assert [v.label for v in voted] == ["Normal", "Cardiomegaly"]  # argmax first

    normal, cardiomegaly = voted
    assert normal.vote_weight == pytest.approx(1.4)
    assert normal.agreement == pytest.approx(2 / 3)
    assert cardiomegaly.vote_weight == pytest.approx(0.6)
    assert cardiomegaly.agreement == pytest.approx(1 / 3)


def test_multi_label_case_contributes_to_every_label_it_carries():
    # case 'a' carries two labels -> contributes its similarity to both
    # weight(Pneumonia) = 0.8 + 0.4 = 1.2, weight(Effusion) = 0.8
    # n = 2 -> agreement(Pneumonia) = 2/2 = 1.0, agreement(Effusion) = 1/2 = 0.5
    cases = [
        _case("a", 0.8, "Pneumonia", "Effusion"),
        _case("b", 0.4, "Pneumonia"),
    ]
    voted = LabelVotingService().vote(cases)

    assert [v.label for v in voted] == ["Pneumonia", "Effusion"]

    pneumonia, effusion = voted
    assert pneumonia.vote_weight == pytest.approx(1.2)
    assert pneumonia.agreement == pytest.approx(1.0)
    assert effusion.vote_weight == pytest.approx(0.8)
    assert effusion.agreement == pytest.approx(0.5)


def test_empty_retrieved_list_returns_empty_vote():
    assert LabelVotingService().vote([]) == []
