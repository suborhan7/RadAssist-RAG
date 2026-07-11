"""
app/services/similarity_search.py
====================================================================
Implements ISimilaritySearchPolicy. Real logic, not a pass-through: applies
a minimum-similarity threshold, then takes the top-K by similarity descending.

Near-duplicate cluster deduplication (using cluster_id, given the known
28.2% template-duplication rate from Phase 1) is a documented future
extension point, NOT implemented here.
"""
from __future__ import annotations

from app.domain.entities import RetrievedCase


class SimilaritySearchPolicy:
    """Satisfies domain.interfaces.ISimilaritySearchPolicy."""

    def select(
        self, raw_results: list[RetrievedCase], top_k: int, min_similarity: float
    ) -> list[RetrievedCase]:
        filtered = [r for r in raw_results if r.similarity >= min_similarity]
        ranked = sorted(filtered, key=lambda r: r.similarity, reverse=True)
        return ranked[:top_k]
