"""
app/services/response_validator.py
====================================================================
Implements IResponseValidator. Semantic/clinical validation of an already
structurally-valid ReportContent (Phase 7's StructuralValidator already
guaranteed shape) -- produces warnings for human review, never a pass/fail
gate that triggers automated retry (frozen Phase 8 Decision 1: a second
LLM attempt is not guaranteed to be less hallucinated, only differently
worded, and an automated retry loop is a real safety risk for a medical
system).

No reusable, importable taxonomy loader exists to reuse instead of the
direct YAML load below: `load_yaml`/`build_term_index` in
ml/preprocessing/build_study_index.py are private helpers inside an
argparse-driven CLI script, and ml/ and backend/ are frozen (CLAUDE.md,
Phase 0 architecture notes) to never import each other except through the
deliberate, one-off shared/ exception -- a hallucination-heuristic term
list doesn't qualify for that exception, so label_mapping.yaml is loaded
directly here instead of reaching across that boundary.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from app.domain.entities import EvidenceSummary, ReportContent, SemanticValidationResult, VotedLabel

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LABEL_MAPPING_PATH = _REPO_ROOT / "ml" / "config" / "label_mapping.yaml"

# "High agreement" threshold for top_label_unreflected, stated explicitly
# rather than left as an unexamined magic number: 0.5 means "a majority of
# retrieved neighbor cases agree on this label" -- a natural, easily
# explained cutoff (more likely right than wrong), not derived from a
# formal calibration study.
TOP_LABEL_AGREEMENT_THRESHOLD = 0.5


def _contains_term(text_lower: str, term: str) -> bool:
    """Word-boundary-aware containment check, NOT plain substring `in` --
    a naive substring check matches "normal" inside "abnormality" (ab +
    normal + ity is a real, common false positive for exactly the
    class name "Normal"), which would flag a report as hallucinating a
    finding it never claimed. \\b boundaries require the term to appear as
    a standalone word/phrase, not as a fragment of a larger word."""
    pattern = r"\b" + re.escape(term.lower()) + r"\b"
    return re.search(pattern, text_lower) is not None


def _load_taxonomy_classes(path: Path = DEFAULT_LABEL_MAPPING_PATH) -> tuple[str, ...]:
    """Reuses the frozen Phase 0 18-class taxonomy (label_mapping.yaml) as the
    term dictionary for the hallucination heuristic (frozen Phase 8 Decision
    3): normal_class + the 16 curated `classes` keys + other_class = 18."""
    with path.open("r", encoding="utf-8") as fh:
        mapping = yaml.safe_load(fh)
    return (mapping["normal_class"], *mapping["classes"].keys(), mapping["other_class"])


class ResponseValidator:
    """Satisfies domain.interfaces.IResponseValidator."""

    def __init__(self, taxonomy_classes: tuple[str, ...] | None = None) -> None:
        self._taxonomy_classes = (
            taxonomy_classes if taxonomy_classes is not None else _load_taxonomy_classes()
        )

    def validate_semantic(
        self,
        content: ReportContent,
        evidence_summary: EvidenceSummary,
        voted_labels: list[VotedLabel],
    ) -> SemanticValidationResult:
        missing_findings = not content.findings.strip()
        missing_impression = not content.impression.strip()

        combined_text_lower = f"{content.findings} {content.impression}".lower()
        evidence_labels = self._evidence_labels(evidence_summary)
        unsupported_terms = tuple(
            cls
            for cls in self._taxonomy_classes
            if _contains_term(combined_text_lower, cls) and cls not in evidence_labels
        )

        top_label = voted_labels[0] if voted_labels else None
        top_label_unreflected = (
            top_label is not None
            and top_label.agreement >= TOP_LABEL_AGREEMENT_THRESHOLD
            and not _contains_term(combined_text_lower, top_label.label)
        )

        warnings: list[str] = []
        if missing_findings:
            warnings.append("Findings section is empty")
        if missing_impression:
            warnings.append("Impression section is empty")
        for term in unsupported_terms:
            warnings.append(f"Mentions '{term}' which is not supported by retrieved evidence")
        if top_label_unreflected:
            warnings.append(
                f"Top voted label '{top_label.label}' (agreement {top_label.agreement:.2f}) "
                f"not reflected in report text"
            )

        is_clean = (
            not missing_findings
            and not missing_impression
            and not top_label_unreflected
            and not unsupported_terms
        )

        return SemanticValidationResult(
            missing_findings=missing_findings,
            missing_impression=missing_impression,
            unsupported_terms=unsupported_terms,
            top_label_unreflected=top_label_unreflected,
            warnings=tuple(warnings),
            is_clean=is_clean,
        )

    @staticmethod
    def _evidence_labels(evidence_summary: EvidenceSummary) -> set[str]:
        """Labels considered 'supported by retrieved evidence' for the
        hallucination heuristic. evidence_summary.label_evidence's
        supporting_cases + contradictory_cases together ALWAYS cover every
        retrieved case (Phase 5's partition is exhaustive -- proven by the
        Phase 5 integration test's disjoint-union assertion), so unioning
        labels from BOTH buckets (not just supporting_cases) yields every
        label actually present anywhere in the retrieved evidence, not just
        the ones tied to whichever single label this partition happens to be
        built for."""
        labels: set[str] = set()
        for partition in evidence_summary.label_evidence:
            labels.add(partition.label)
            for case in (*partition.supporting_cases, *partition.contradictory_cases):
                labels.update(case.labels)
        return labels
