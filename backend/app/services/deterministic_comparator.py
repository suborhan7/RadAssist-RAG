"""
app/services/deterministic_comparator.py
====================================================================
Implements IDeterministicComparator. Pure, no LLM, no DB: diffs two
reports' taxonomy-class presence (extracted via the same word-boundary-safe
mechanism as ResponseValidator, app/services/taxonomy_matching.py -- not a
second, possibly-drifting reimplementation) into resolved/persistent/new
findings, plus a plain day-count between the two study dates.

resolved_findings/persistent_findings/new_findings are returned in
taxonomy order (the same fixed order load_taxonomy_classes() produces),
not set/insertion order -- deterministic output matters here since these
tuples flow directly into build_comparison_prompt() (Step 7) and a
hospital-facing narrative; an arbitrary set-iteration order would make the
narrative's finding ordering non-reproducible across runs for identical
inputs.

previous_report_id/current_report_id are accepted as plain string params
(not looked up) -- see IDeterministicComparator's docstring for why this
was added to the frozen Step 1 interface.
"""
from __future__ import annotations

from datetime import date

from app.domain.entities import ComparisonFacts, ReportContent
from app.services.taxonomy_matching import extract_mentioned_classes, load_taxonomy_classes


class DeterministicComparator:
    """Satisfies domain.interfaces.IDeterministicComparator."""

    def __init__(self, taxonomy_classes: tuple[str, ...] | None = None) -> None:
        self._taxonomy_classes = (
            taxonomy_classes if taxonomy_classes is not None else load_taxonomy_classes()
        )

    def compare(
        self,
        previous: ReportContent,
        current: ReportContent,
        previous_date: str,
        current_date: str,
        previous_report_id: str,
        current_report_id: str,
    ) -> ComparisonFacts:
        previous_classes = self._mentioned_classes(previous)
        current_classes = self._mentioned_classes(current)

        resolved = previous_classes - current_classes
        persistent = previous_classes & current_classes
        new = current_classes - previous_classes

        days_between = (date.fromisoformat(current_date) - date.fromisoformat(previous_date)).days

        return ComparisonFacts(
            previous_report_id=previous_report_id,
            current_report_id=current_report_id,
            resolved_findings=self._in_taxonomy_order(resolved),
            persistent_findings=self._in_taxonomy_order(persistent),
            new_findings=self._in_taxonomy_order(new),
            days_between_studies=days_between,
        )

    def _mentioned_classes(self, content: ReportContent) -> set[str]:
        text_lower = f"{content.findings} {content.impression}".lower()
        return extract_mentioned_classes(text_lower, self._taxonomy_classes)

    def _in_taxonomy_order(self, classes: set[str]) -> tuple[str, ...]:
        return tuple(cls for cls in self._taxonomy_classes if cls in classes)
