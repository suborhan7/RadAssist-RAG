"""
app/services/taxonomy_matching.py
====================================================================
Word-boundary-safe taxonomy-class detection, extracted from
response_validator.py (Phase 8) so DeterministicComparator (Phase 11)
can reuse the exact same matching mechanism rather than a second,
possibly-drifting reimplementation -- same "don't duplicate a source of
truth" discipline as report_reconstruction.py's extraction in this phase.

Phase 8's original bug this guards against: a naive substring check
matches "normal" inside "abnormality" (ab + normal + ity), which would
misclassify a report as mentioning "Normal" when it never did. \\b
boundaries require the term to appear as a standalone word/phrase.

No reusable, importable taxonomy loader exists elsewhere to reuse instead:
`load_yaml`/`build_term_index` in ml/preprocessing/build_study_index.py
are private helpers inside an argparse-driven CLI script, and ml/ and
backend/ are frozen (CLAUDE.md, Phase 0 architecture notes) to never
import each other except through the deliberate, one-off shared/
exception -- a hallucination/comparison heuristic term list doesn't
qualify for that exception, so label_mapping.yaml is loaded directly here.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LABEL_MAPPING_PATH = _REPO_ROOT / "ml" / "config" / "label_mapping.yaml"


def contains_term(text_lower: str, term: str) -> bool:
    """Word-boundary-aware containment check, NOT plain substring `in` --
    a naive substring check matches "normal" inside "abnormality" (ab +
    normal + ity is a real, common false positive for exactly the
    class name "Normal"). \\b boundaries require the term to appear as
    a standalone word/phrase, not as a fragment of a larger word."""
    pattern = r"\b" + re.escape(term.lower()) + r"\b"
    return re.search(pattern, text_lower) is not None


def load_taxonomy_classes(path: Path = DEFAULT_LABEL_MAPPING_PATH) -> tuple[str, ...]:
    """Reuses the frozen Phase 0 18-class taxonomy (label_mapping.yaml) as the
    term dictionary: normal_class + the 16 curated `classes` keys + other_class
    = 18."""
    with path.open("r", encoding="utf-8") as fh:
        mapping = yaml.safe_load(fh)
    return (mapping["normal_class"], *mapping["classes"].keys(), mapping["other_class"])


def extract_mentioned_classes(text_lower: str, taxonomy_classes: tuple[str, ...]) -> set[str]:
    """Every taxonomy class mentioned (word-boundary-safe) anywhere in
    text_lower. Order-independent (a set) -- callers needing taxonomy
    order back should re-filter `taxonomy_classes` against the result."""
    return {cls for cls in taxonomy_classes if contains_term(text_lower, cls)}
