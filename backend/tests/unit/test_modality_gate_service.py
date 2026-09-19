"""
Unit tests for ModalityGateService -- requirements M1 to M12 of
input_admission_projection_gate_architecture_v1.1_FROZEN.md §6, and S1
of §7.

M1-M6 are the blocking modality gate (§6). M7-M9 are the three bands
(§6.1) and M10-M12 are the projection mismatch check (§6.2), both new in
v1.1 and covered at the end of this file.

The embedder is a fake returning fixed, hand-chosen unit vectors, so the
softmax and the comparisons can be checked exactly. The real BiomedCLIP
behavior is measured by the Gate B calibration (ml/calibration/) and
exercised end to end by the T1-T21 acceptance gate; duplicating that here
would make these tests slow without making them sharper.
"""
from __future__ import annotations

import math

import pytest

from app.domain.entities import RetrievalSupport
from app.services.exceptions import NotAChestRadiographError, ProjectionMismatchError
from app.services.modality_gate_service import ModalityGateService

POSITIVE = ("a chest radiograph",)
NEGATIVE = ("a photograph of an object", "an abdominal radiograph")


class FakeEmbedder:
    """Returns one basis vector per prompt, in call order, and counts the
    calls so M6's caching can be asserted."""

    def __init__(self, dimensions: int = 4) -> None:
        self.dimensions = dimensions
        self.text_calls: list[str] = []

    def embed_text(self, text: str) -> list[float]:
        index = len(self.text_calls)
        self.text_calls.append(text)
        return [1.0 if i == index else 0.0 for i in range(self.dimensions)]

    def embed_image(self, image_path: str) -> list[float]:  # pragma: no cover - never used
        raise AssertionError("M1: the gate must not encode the image")


def _gate(threshold: float = 0.6, floor: float = 0.76, temperature: float = 1.0) -> ModalityGateService:
    return ModalityGateService(
        embedder=FakeEmbedder(),
        positive_prompts=POSITIVE,
        negative_prompts=NEGATIVE,
        softmax_temperature=temperature,
        modality_threshold=threshold,
        retrieval_floor=floor,
    )


# --- M6 ---------------------------------------------------------------


def test_M6_text_vectors_are_encoded_once_at_construction():
    embedder = FakeEmbedder()
    gate = ModalityGateService(
        embedder=embedder,
        positive_prompts=POSITIVE,
        negative_prompts=NEGATIVE,
        softmax_temperature=1.0,
        modality_threshold=0.6,
        retrieval_floor=0.76,
    )
    assert embedder.text_calls == [*POSITIVE, *NEGATIVE]

    for _ in range(5):
        gate.score([1.0, 0.0, 0.0, 0.0])

    assert embedder.text_calls == [*POSITIVE, *NEGATIVE], "prompts were re-encoded per request"


def test_M6_positive_prompts_are_cached_before_negative_ones():
    """Not cosmetic: score() sums the softmax over the FIRST
    len(positive_prompts) entries, so the order is load-bearing. If it
    ever changed, the gate would silently score images against a negative
    prompt and reject every radiograph."""
    embedder = FakeEmbedder()
    ModalityGateService(embedder, POSITIVE, NEGATIVE, 1.0, 0.6, 0.76)
    assert embedder.text_calls[: len(POSITIVE)] == list(POSITIVE)


# --- M1 ---------------------------------------------------------------


def test_M1_the_gate_never_encodes_the_image():
    """FakeEmbedder.embed_image raises. Reaching it at all is the failure."""
    gate = _gate()
    gate.score([1.0, 0.0, 0.0, 0.0])
    gate.classify_retrieval_support(0.9)


# --- M2 / M4 ----------------------------------------------------------


def test_M2_and_M4_produce_a_plain_softmax_over_the_cosine_similarities():
    """With unit basis vectors as prompts, the cosine against prompt i is
    just component i of the image vector, so the expected score can be
    written out by hand rather than reproduced from the implementation."""
    gate = _gate(temperature=1.0)
    vector = [0.5, 0.25, 0.125, 0.0]

    exponentials = [math.exp(v) for v in vector[:3]]
    expected = exponentials[0] / sum(exponentials)

    assert gate.score(vector) == pytest.approx(expected)


def test_M4_score_is_a_probability():
    gate = _gate()
    for vector in ([1.0, 0, 0, 0], [0, 1.0, 0, 0], [0.3, 0.3, 0.3, 0.0]):
        assert 0.0 <= gate.score(vector) <= 1.0


def test_temperature_sharpens_the_distribution_without_reordering_it():
    """The temperature is a Gate B parameter, and this is the property
    that makes it safe to calibrate: it changes how confident the score
    is, never which prompt wins."""
    vector = [0.45, 0.28, 0.31, 0.0]
    warm = _gate(temperature=1.0).score(vector)
    cold = _gate(temperature=0.01).score(vector)
    assert cold > warm
    assert warm > 1 / 3  # still the argmax at temperature 1


def test_softmax_does_not_overflow_at_a_realistic_temperature():
    """The deployed temperature is ~1/85, which scales cosines to ~40. A
    softmax without the max-subtraction would overflow to inf and return
    nan here."""
    gate = _gate(temperature=1.0 / 85.2322769165039)
    score = gate.score([0.45, 0.28, 0.31, 0.0])
    assert not math.isnan(score)
    assert 0.0 <= score <= 1.0


# --- M5 / DR-1 --------------------------------------------------------


def test_M5_blocks_below_the_threshold():
    gate = _gate(threshold=0.9, temperature=0.01)
    with pytest.raises(NotAChestRadiographError) as caught:
        gate.gate([0.0, 1.0, 0.0, 0.0])  # matches a NEGATIVE prompt
    assert caught.value.modality_score < 0.9
    assert caught.value.reason_code == "MODALITY_BELOW_THRESHOLD"
    assert caught.value.stage == "modality_gate"


def test_M5_passes_at_or_above_the_threshold_and_returns_the_score():
    gate = _gate(threshold=0.9, temperature=0.01)
    score = gate.gate([1.0, 0.0, 0.0, 0.0])
    assert score >= 0.9


def test_M5_boundary_is_inclusive():
    """"Reject if the score is LESS THAN the threshold" -- a score exactly
    equal to the threshold passes. Stated because an off-by-one here
    silently rejects a class of borderline radiographs."""
    gate = _gate(threshold=0.6, temperature=1.0)
    vector = [0.5, 0.25, 0.125, 0.0]
    exact = gate.score(vector)
    at_boundary = _gate(threshold=exact, temperature=1.0)
    assert at_boundary.gate(vector) == pytest.approx(exact)


def test_the_rejection_message_carries_no_file_information():
    """§10's Rule. The gate is never given a file name or path; this
    confirms the message is built from measurements only."""
    gate = _gate(threshold=0.9, temperature=0.01)
    with pytest.raises(NotAChestRadiographError) as caught:
        gate.gate([0.0, 1.0, 0.0, 0.0])
    message = str(caught.value)
    assert "modality score" in message and "threshold" in message
    for forbidden in (".png", ".jpg", ".jpeg", "/", "\\"):
        assert forbidden not in message


# --- M7 / M8 / M9 / S1 ------------------------------------------------


def test_S1_classifies_support_from_the_top1_similarity_and_the_floor():
    gate = _gate(floor=0.76)
    assert gate.classify_retrieval_support(0.90) is RetrievalSupport.AT_OR_ABOVE_FLOOR
    assert gate.classify_retrieval_support(0.76) is RetrievalSupport.AT_OR_ABOVE_FLOOR
    assert gate.classify_retrieval_support(0.75) is RetrievalSupport.BELOW_FLOOR


def test_M9_low_support_never_raises():
    """DR-3 and §10's Note: a low retrieval support is not an error. It
    has no exception type and no HTTP status."""
    gate = _gate(floor=0.99)
    assert gate.classify_retrieval_support(0.01) is RetrievalSupport.BELOW_FLOOR
    assert gate.classify_retrieval_support(None) is RetrievalSupport.BELOW_FLOOR


def test_no_retrieved_case_is_below_the_floor_not_an_error():
    """A retrieval that returned nothing has no top-1 to compare. "No
    retrieved case meets the threshold" is exactly true, and is what the
    disclaimer will say."""
    assert _gate().classify_retrieval_support(None) is RetrievalSupport.BELOW_FLOOR


def test_support_is_not_derived_from_agreement():
    """§7's central constraint, as a signature property:
    classify_retrieval_support takes the top-1 similarity and nothing
    else, so there is no path by which the agreement score could
    influence it."""
    import inspect

    parameters = set(inspect.signature(_gate().classify_retrieval_support).parameters)
    assert parameters == {"top1_similarity"}


# --- construction guards ----------------------------------------------


def test_an_empty_positive_prompt_set_fails_at_construction():
    """A gate with no positive prompt scores 0.0 for everything and
    rejects every upload -- indistinguishable from a working gate at a
    glance, so it must fail loudly at start-up."""
    with pytest.raises(ValueError, match="MODALITY_PROMPTS_POSITIVE"):
        ModalityGateService(FakeEmbedder(), (), NEGATIVE, 1.0, 0.6, 0.76)


@pytest.mark.parametrize("temperature", [0.0, -1.0])
def test_a_non_positive_temperature_fails_at_construction(temperature):
    with pytest.raises(ValueError, match="MODALITY_SOFTMAX_TEMPERATURE"):
        ModalityGateService(FakeEmbedder(), POSITIVE, NEGATIVE, temperature, 0.6, 0.76)


def test_multiple_positive_prompts_sum_their_probability_mass():
    """§11.2 Step 6 anticipates adding a lateral prompt. When it is added,
    the score must be the total probability that the image is a chest
    radiograph -- not just the first prompt's share, which would make the
    gate STRICTER after adding a prompt intended to make it fairer to
    laterals."""
    two_positives = ModalityGateService(
        embedder=FakeEmbedder(),
        positive_prompts=("a chest radiograph", "a lateral chest radiograph"),
        negative_prompts=("a photograph of an object",),
        softmax_temperature=1.0,
        modality_threshold=0.6,
        retrieval_floor=0.76,
    )
    one_positive = _gate(temperature=1.0)
    vector = [0.4, 0.4, 0.1, 0.0]
    assert two_positives.score(vector) > one_positive.score(vector)


# ======================================================================
# §6.1 / §6.2 -- the three bands and the projection mismatch (new in v1.1)
# ======================================================================

REJECT = 0.87
FLOOR = 0.89


def _banded(reject: float = REJECT, floor: float = FLOOR) -> ModalityGateService:
    return ModalityGateService(
        embedder=FakeEmbedder(),
        positive_prompts=POSITIVE,
        negative_prompts=NEGATIVE,
        softmax_temperature=1.0,
        modality_threshold=0.6,
        retrieval_floor=floor,
        projection_reject_threshold=reject,
    )


# --- M8: the three bands ----------------------------------------------


def test_M8_normal_band_is_at_or_above_the_retrieval_floor():
    gate = _banded()
    assert gate.check_projection_band(0.95) is RetrievalSupport.AT_OR_ABOVE_FLOOR
    assert gate.check_projection_band(FLOOR) is RetrievalSupport.AT_OR_ABOVE_FLOOR


def test_M8_low_support_band_sits_between_the_two_thresholds():
    """The middle band is the whole reason DR-5 uses two thresholds. A
    value here must CONTINUE (no exception) and be categorised
    below_floor."""
    gate = _banded()
    assert gate.check_projection_band(0.88) is RetrievalSupport.BELOW_FLOOR
    assert gate.check_projection_band(REJECT) is RetrievalSupport.BELOW_FLOOR


def test_M8_reject_band_is_below_the_projection_reject_threshold():
    gate = _banded()
    with pytest.raises(ProjectionMismatchError):
        gate.check_projection_band(REJECT - 0.0001)


def test_M8_the_three_bands_are_contiguous_and_exhaustive():
    """Swept across the whole range, every value lands in exactly one of
    the three bands, and the boundaries are where §6.1's table puts them.
    A gap or an overlap here would mean some top-1 similarity had no
    defined behaviour at all."""
    gate = _banded()
    for value in [0.0, 0.5, 0.86, 0.869, 0.87, 0.875, 0.889, 0.89, 0.9, 1.0]:
        if value < REJECT:
            with pytest.raises(ProjectionMismatchError):
                gate.check_projection_band(value)
        elif value < FLOOR:
            assert gate.check_projection_band(value) is RetrievalSupport.BELOW_FLOOR
        else:
            assert gate.check_projection_band(value) is RetrievalSupport.AT_OR_ABOVE_FLOOR


# --- DR-5 / §6.1's Warning --------------------------------------------


def test_the_two_thresholds_must_not_be_joined():
    """§6.1's Warning: "A single threshold removes the low support band,
    and section 7 then has no function."

    Constructing a gate whose reject threshold is at or above the floor
    is exactly that collapse, so it fails loudly at construction rather
    than producing a service with a silently empty middle band.
    """
    with pytest.raises(ValueError, match="strictly below RETRIEVAL_FLOOR"):
        ModalityGateService(
            embedder=FakeEmbedder(), positive_prompts=POSITIVE, negative_prompts=NEGATIVE,
            softmax_temperature=1.0, modality_threshold=0.6,
            retrieval_floor=0.89, projection_reject_threshold=0.89,
        )
    with pytest.raises(ValueError, match="strictly below RETRIEVAL_FLOOR"):
        ModalityGateService(
            embedder=FakeEmbedder(), positive_prompts=POSITIVE, negative_prompts=NEGATIVE,
            softmax_temperature=1.0, modality_threshold=0.6,
            retrieval_floor=0.80, projection_reject_threshold=0.90,
        )


def test_an_unconfigured_reject_threshold_raises_rather_than_skipping_the_check():
    """A gate that quietly stops gating is the failure mode this whole
    document exists to prevent, so a missing threshold is an error and
    never a silent pass-through."""
    gate = _gate()  # constructed without a projection reject threshold
    assert gate.projection_reject_threshold is None
    with pytest.raises(ValueError, match="PROJECTION_REJECT_THRESHOLD"):
        gate.check_projection_band(0.5)


# --- M10 / M11 / M12 ---------------------------------------------------


def test_M11_the_mismatch_uses_its_own_type_and_reason_code():
    """M11: use FRONTAL_MISMATCH, not DECLARED_LATERAL, and not
    NotAChestRadiographError."""
    from app.services.exceptions import LateralProjectionError

    gate = _banded()
    with pytest.raises(ProjectionMismatchError) as caught:
        gate.check_projection_band(0.5)
    assert caught.value.reason_code == "FRONTAL_MISMATCH"
    assert caught.value.stage == "projection_mismatch"
    assert not isinstance(caught.value, NotAChestRadiographError)
    assert not isinstance(caught.value, LateralProjectionError)


def test_M10_carries_the_measurement_that_caused_the_rejection():
    """DR-2 records the evidence for the calibration, and the raise site
    is the only place that holds both numbers."""
    gate = _banded()
    with pytest.raises(ProjectionMismatchError) as caught:
        gate.check_projection_band(0.42)
    assert caught.value.top1_similarity == pytest.approx(0.42)
    assert caught.value.reject_threshold == pytest.approx(REJECT)


def test_M12_the_message_states_a_doubt_and_carries_an_i18n_key():
    """M12: the message must not tell the doctor the image is wrong. The
    English wording lives behind the i18n key (§10.1), so what is checked
    here is that a key is carried and that the internal message states the
    measurement rather than a verdict about the image."""
    gate = _banded()
    with pytest.raises(ProjectionMismatchError) as caught:
        gate.check_projection_band(0.42)
    assert caught.value.message_key == "error.projection.frontalMismatch"
    message = str(caught.value)
    assert "top-1 similarity" in message and "reject threshold" in message
    for verdict in ("wrong", "invalid", "not a chest"):
        assert verdict not in message.lower()


def test_no_retrieved_case_is_not_a_projection_mismatch():
    """A retrieval that returned nothing has no top-1 to compare against
    the reject threshold, so it cannot be a mismatch. It falls through to
    the support signal, where "no retrieved case meets the threshold" is
    exactly true."""
    gate = _banded()
    assert gate.check_projection_band(None) is RetrievalSupport.BELOW_FLOOR


def test_the_band_check_reuses_the_one_support_classification():
    """S1 has a single implementation. The band check must delegate to it
    rather than re-deriving the floor comparison, so /retrieve's category
    and the report's stored category cannot drift."""
    gate = _banded()
    for value in (0.88, 0.95):
        assert gate.check_projection_band(value) is gate.classify_retrieval_support(value)
