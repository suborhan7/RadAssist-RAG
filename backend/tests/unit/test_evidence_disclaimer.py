"""
Unit tests for render_disclaimer -- requirements S1 to S4 and §7.2's
support matrix of input_admission_projection_gate_architecture_v1.1_FROZEN.md.

The four matrix cells are checked one by one, and then the two properties
that hold across all of them: the disclaimer reads BOTH signals (§7.1's
Rule), and it never claims more than the measurement shows (§7.2's Rule).
"""
from __future__ import annotations

import pytest

from app.domain.entities import RetrievalSupport
from app.services.evidence_disclaimer import render_disclaimer

FLOOR = 0.76
AGREEMENT_THRESHOLD = 0.5

# The exact sentence S4 makes mandatory for a low support category.
S4_STATEMENT = "No retrieved case meets the minimum retrieval-support threshold"
# The exact sentence §7.2's matrix puts in the high-agreement/low-support
# cell -- the one §7.1's Warning is about.
MATRIX_HIGH_LOW = "The agreement score alone does not indicate strong evidence"


def _render(agreement, support, top1=0.70, language="en"):
    return render_disclaimer(
        agreement=agreement,
        support=support,
        top1_similarity=top1,
        retrieval_floor=FLOOR,
        agreement_threshold=AGREEMENT_THRESHOLD,
        language=language,
    )


# --- the four cells of §7.2 -------------------------------------------


def test_at_or_above_floor_with_high_agreement_is_the_standard_disclaimer():
    text = _render(0.8, RetrievalSupport.AT_OR_ABOVE_FLOOR, top1=0.95)
    assert S4_STATEMENT not in text
    assert "requires review and approval by a qualified radiologist" in text


def test_at_or_above_floor_with_low_agreement_says_the_cases_conflict():
    text = _render(0.2, RetrievalSupport.AT_OR_ABOVE_FLOOR, top1=0.95)
    assert S4_STATEMENT not in text
    assert "conflict" in text.lower()


def test_below_floor_with_high_agreement_warns_that_agreement_is_not_enough():
    """§7.2's matrix cell, and the whole reason §7 exists: agreement is
    high, support is low, and a disclaimer reading only agreement would
    announce confidence."""
    text = _render(0.9, RetrievalSupport.BELOW_FLOOR)
    assert S4_STATEMENT in text
    assert MATRIX_HIGH_LOW in text


def test_below_floor_with_low_agreement_says_both():
    text = _render(0.2, RetrievalSupport.BELOW_FLOOR)
    assert S4_STATEMENT in text
    assert "do not agree" in text.lower()


# --- S4 ---------------------------------------------------------------


@pytest.mark.parametrize("agreement", [0.0, 0.2, 0.5, 0.8, 1.0])
def test_S4_every_low_support_disclaimer_states_the_threshold_fact(agreement):
    """S4 is unconditional on the agreement score: DR-3 lets a report be
    generated from weak evidence, so the weak-support statement is
    mandatory in every low-support cell, not only the alarming one."""
    assert S4_STATEMENT in _render(agreement, RetrievalSupport.BELOW_FLOOR)


# --- §7.1's Rule: both signals ----------------------------------------


def test_the_disclaimer_changes_with_agreement_at_a_fixed_support():
    high = _render(0.9, RetrievalSupport.BELOW_FLOOR)
    low = _render(0.1, RetrievalSupport.BELOW_FLOOR)
    assert high != low


def test_the_disclaimer_changes_with_support_at_a_fixed_agreement():
    below = _render(0.9, RetrievalSupport.BELOW_FLOOR)
    above = _render(0.9, RetrievalSupport.AT_OR_ABOVE_FLOOR)
    assert below != above


def test_all_four_cells_are_distinct():
    """If any two collapsed, one signal would have stopped mattering in
    that corner of the matrix."""
    rendered = {
        _render(agreement, support)
        for agreement in (0.9, 0.1)
        for support in RetrievalSupport
    }
    assert len(rendered) == 4


# --- §7.2's Rule: never overclaim -------------------------------------


@pytest.mark.parametrize("agreement", [0.0, 0.5, 1.0])
@pytest.mark.parametrize("support", list(RetrievalSupport))
def test_no_cell_claims_the_archive_holds_no_similar_case(agreement, support):
    """§7.2's closing Rule. The measurement shows the top-1 similarity is
    below the configured floor; it does NOT show that no similar case
    exists. The document's own example: a top-1 of 0.52 under a floor of
    0.60 means a case exists and does not meet the threshold."""
    text = _render(agreement, support).lower()
    for overclaim in (
        "no similar case",
        "no comparable case",
        "the archive holds no",
        "there are no similar",
        "not present in the archive",
    ):
        assert overclaim not in text


def test_the_measurement_is_quoted_not_just_the_verdict():
    """S3 says parameterised, not static. The rendered text has to carry
    this run's own numbers, or the "template" is just four constants."""
    text = _render(0.8, RetrievalSupport.BELOW_FLOOR, top1=0.52)
    assert "0.52" in text
    assert "0.76" in text
    assert "80%" in text


# --- parameter handling -----------------------------------------------


def test_a_missing_agreement_is_treated_as_low_not_high():
    """No retrieved cases means no vote. An absent vote is not evidence
    that the cases agree, so it must not select a high-agreement cell."""
    text = _render(None, RetrievalSupport.BELOW_FLOOR, top1=None)
    assert S4_STATEMENT in text
    assert MATRIX_HIGH_LOW not in text


def test_a_missing_top1_renders_without_a_fabricated_number():
    text = _render(None, RetrievalSupport.BELOW_FLOOR, top1=None)
    assert "0.00" not in text


def test_the_agreement_boundary_is_inclusive():
    at_threshold = _render(AGREEMENT_THRESHOLD, RetrievalSupport.BELOW_FLOOR)
    assert MATRIX_HIGH_LOW in at_threshold


def test_bangla_renders_all_four_cells():
    for agreement in (0.9, 0.1):
        for support in RetrievalSupport:
            text = _render(agreement, support, language="bn")
            assert text.strip()
            assert "{" not in text  # every placeholder was filled


def test_an_unsupported_language_raises_rather_than_falling_back():
    """Same policy as ReportFormatter.format(): silently emitting English
    into a report the LLM was asked to write in another language is a
    worse failure than a loud error."""
    with pytest.raises(ValueError, match="unsupported language"):
        _render(0.8, RetrievalSupport.BELOW_FLOOR, language="fr")


def test_the_two_signals_cannot_be_passed_positionally():
    """`agreement` and `top1_similarity` are both bare floats. Positional
    arguments would let a call site swap them and get a plausible
    disclaimer computed from the wrong signal -- the exact conflation §7
    exists to prevent."""
    with pytest.raises(TypeError):
        render_disclaimer(0.8, RetrievalSupport.BELOW_FLOOR, 0.5, FLOOR, AGREEMENT_THRESHOLD, "en")
