"""
app/services/label_voting_service.py
====================================================================
Implements ILabelVoter. Similarity-weighted vote over retrieved cases, per
the frozen Phase 4 formula (development_log.md, Phase 4 architecture
section, correction 4):
    weight(L)       = sum(similarity_i for cases carrying L)
    predicted label = argmax(weight(L))
    agreement        = fraction of retrieved cases carrying the predicted label

ILabelVoter.vote() returns list[VotedLabel], not a single label, so this
computes weight(L) and agreement(L) for every label present across the
retrieved cases (not only the argmax one) -- agreement(L) generalizes the
frozen definition to each L ("fraction of retrieved cases carrying L"),
which collapses to the frozen single-label formula exactly for the first
(highest vote_weight) entry of the returned, descending-sorted list.
"""
from __future__ import annotations

from collections import defaultdict

from app.domain.entities import RetrievedCase, VotedLabel


class LabelVotingService:
    """Satisfies domain.interfaces.ILabelVoter."""

    def vote(self, retrieved: list[RetrievedCase]) -> list[VotedLabel]:
        if not retrieved:
            return []

        weights: dict[str, float] = defaultdict(float)
        counts: dict[str, int] = defaultdict(int)
        for case in retrieved:
            for label in case.labels:
                weights[label] += case.similarity
                counts[label] += 1

        n = len(retrieved)
        voted = [
            VotedLabel(label=label, vote_weight=weight, agreement=counts[label] / n)
            for label, weight in weights.items()
        ]
        voted.sort(key=lambda v: v.vote_weight, reverse=True)
        return voted
