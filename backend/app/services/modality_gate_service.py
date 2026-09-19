"""
app/services/modality_gate_service.py
====================================================================
ModalityGateService -- requirements M1 to M9 of
docs/methodology/input_admission_projection_gate_architecture_v1.1_FROZEN.md
(§6), plus S1 of §7. The "gate" verb of §3.2's vocabulary lock: check that
the image CONTENT is a chest radiograph.

This is a different service from ImageAdmissionService and must stay one
(§1's closing line, §10's opening lines). Admission finds unsafe and
damaged FILES; the gate finds correct files holding the wrong PICTURE.
§4 spells out why one cannot stand in for the other: the strawberry
photograph that produced a full radiology report was a perfectly correct
JPEG, so no file-level check would ever have stopped it. Its logic is
equally deliberately absent from EmbeddingService (§10) -- this class
consumes an embedding, it does not produce one.

Two entry points, two positions in the pipeline
-----------------------------------------------
§9's design decision keeps both in this one service because both measure
the suitability of the input, while placing them at different points:

  gate()                       M1-M6, after EmbeddingService  -> BLOCKS
  classify_retrieval_support() M7-M9, after RetrievalService   -> NEVER blocks

The asymmetry is DR-1 and DR-3, and it is the point of the design rather
than an inconsistency. A non-radiograph is a wrong input and the pipeline
stops (DR-1: a report about a non-radiograph is a clinical safety
failure, and a warning would depend on the doctor reading it). A chest
radiograph of a rare condition is a CORRECT input for which no retrieved
case meets the support threshold -- the doctor needs that report, so the
pipeline continues and the report states the weak support (DR-3).

No parameter value is written in this file (§11.1's Rule): the prompt
set, the softmax temperature, the modality threshold, and the retrieval
floor all arrive through the constructor from `settings`.
"""
from __future__ import annotations

import math

from app.domain.entities import RetrievalSupport
from app.domain.interfaces import IEmbedder
from app.services.exceptions import NotAChestRadiographError, ProjectionMismatchError


class ModalityGateService:
    """Implements §6 (M1 to M9) and §7's S1."""

    def __init__(
        self,
        embedder: IEmbedder,
        positive_prompts: tuple[str, ...],
        negative_prompts: tuple[str, ...],
        softmax_temperature: float,
        modality_threshold: float,
        retrieval_floor: float,
        projection_reject_threshold: float | None = None,
    ) -> None:
        if not positive_prompts:
            # Not a configuration nicety: with no positive prompt there is
            # no probability mass that means "chest radiograph", so the
            # score would be 0.0 for every input and the gate would reject
            # every upload including real radiographs. Failing at start-up
            # is the only safe behavior -- a gate that silently rejects
            # everything looks identical to a gate that is working.
            raise ValueError("MODALITY_PROMPTS_POSITIVE must contain at least one prompt")
        if softmax_temperature <= 0:
            raise ValueError("MODALITY_SOFTMAX_TEMPERATURE must be greater than zero")

        self._positive_prompts = positive_prompts
        self._negative_prompts = negative_prompts
        self._softmax_temperature = softmax_temperature
        self._modality_threshold = modality_threshold
        self._retrieval_floor = retrieval_floor
        # DR-5 / §6.1: the SECOND threshold on the top-1 similarity. It is a
        # separate value with a separate meaning, and §6.1's Warning forbids
        # joining the two -- one threshold removes the low support band and
        # §7 then has no function.
        #
        # Defaulted to None so the existing unit tests that construct this
        # service without it keep working; with None, check_projection_band()
        # raises rather than silently skipping the control, because a gate
        # that quietly stops gating is the failure mode this whole document
        # exists to prevent.
        self._projection_reject_threshold = projection_reject_threshold
        if (
            projection_reject_threshold is not None
            and projection_reject_threshold >= retrieval_floor
        ):
            # Not a style check. §6.1's three bands only exist while the
            # reject threshold sits strictly below the floor; if they cross,
            # the low support band is empty and DR-5's stated failure has
            # happened silently.
            raise ValueError(
                "PROJECTION_REJECT_THRESHOLD must be strictly below RETRIEVAL_FLOOR; "
                "otherwise the low support band of section 6.1 is empty"
            )

        # --- M6: cache the text vectors at start-up. ---
        # This runs once per process, in app/main.py's lifespan, not per
        # request. The prompt set is fixed configuration, so re-encoding it
        # on every upload would add a text-encoder forward pass to the
        # latency of every single retrieval for an identical result.
        # Positives first, then negatives: _score() relies on that split
        # to know which entries of the softmax output carry
        # "is a chest radiograph" probability mass.
        self._prompt_vectors = [
            embedder.embed_text(prompt)
            for prompt in (*self._positive_prompts, *self._negative_prompts)
        ]

    # ------------------------------------------------------------------
    # M1 to M5 -- the blocking control
    # ------------------------------------------------------------------
    def score(self, image_vector: list[float]) -> float:
        """M1 to M4: the modality score for an already-computed embedding.

        M1 is why this takes a vector and not an image path: the image is
        NOT encoded again. §9 places this call directly after
        EmbeddingService precisely so the vector that is about to be used
        for retrieval is the same vector the gate judges -- re-encoding
        would spend a second forward pass to answer a question about a
        possibly different tensor.
        """
        # M2: cosine similarity against each text vector in the prompt set.
        # Both sides are L2-normalized by the frozen embedder
        # (shared/embeddings/biomedclip_embedder.py returns unit vectors),
        # so the dot product IS the cosine -- no re-normalization here,
        # which would quietly paper over a future embedder that stopped
        # normalizing.
        similarities = [_dot(image_vector, prompt_vector) for prompt_vector in self._prompt_vectors]

        # M4: softmax, then read off the chest-radiograph result.
        probabilities = _softmax(similarities, self._softmax_temperature)
        return sum(probabilities[: len(self._positive_prompts)])

    def gate(self, image_vector: list[float]) -> float:
        """M5: reject the image if the modality score is below the
        threshold. Returns the score on success so the caller can record
        it (DR-2's audit table wants the score "if calculated", and the
        successful path is where a calibration set's true-positive scores
        come from).

        DR-1: this BLOCKS. It does not warn, and version 1 gives no
        override -- an override needs a permission model and an audit
        design, recorded there as future work.
        """
        modality_score = self.score(image_vector)
        if modality_score < self._modality_threshold:
            # No file name, no file size, no image data -- §10's Rule and
            # DR-2's Warning. The score and the threshold are both
            # measurements the doctor is entitled to see.
            raise NotAChestRadiographError(
                f"the uploaded image was not recognised as a chest radiograph "
                f"(modality score {modality_score:.4f}, threshold {self._modality_threshold:.4f})",
                modality_score=modality_score,
            )
        return modality_score

    # ------------------------------------------------------------------
    # M7 to M9 / S1 -- the non-blocking signal
    # ------------------------------------------------------------------
    def classify_retrieval_support(self, top1_similarity: float | None) -> RetrievalSupport:
        """M7 to M9 and S1: compare the top-1 similarity from the
        RetrievalService with the retrieval floor and set the support
        category.

        M9: this does NOT stop the pipeline, and there is no exception
        type or HTTP status for a low result (§10's Note). It returns a
        category, and the report goes on to be generated (DR-3).

        This is computed from the top-1 similarity and the floor and from
        nothing else. §7.1's Warning is that agreement and retrieval
        support are two independent signals that CAN disagree -- five
        cases all below the floor can carry the same label, making
        agreement high while support is low -- so deriving this category
        from the agreement score would collapse the two signals the whole
        of §7 exists to keep apart.

        A `None` top-1 (a retrieval that returned no case at all, e.g.
        every result filtered out by min_similarity) is BELOW_FLOOR: no
        retrieved case meets the threshold, which is exactly what the
        category asserts and exactly what §7.2's disclaimer will say.
        """
        if top1_similarity is None:
            return RetrievalSupport.BELOW_FLOOR
        if top1_similarity >= self._retrieval_floor:
            return RetrievalSupport.AT_OR_ABOVE_FLOOR
        return RetrievalSupport.BELOW_FLOOR

    # ------------------------------------------------------------------
    # M7 to M12 -- the three bands, and the projection mismatch check
    # ------------------------------------------------------------------
    def check_projection_band(self, top1_similarity: float | None) -> RetrievalSupport:
        """M7, M8, M9 and M10: place the top-1 similarity in one of §6.1's
        three bands, blocking on the first.

        | Band        | Condition                          | Action            |
        | Reject      | top-1 < projection reject threshold | raise (M10)      |
        | Low support | reject <= top-1 < retrieval floor   | below_floor      |
        | Normal      | top-1 >= retrieval floor            | at_or_above_floor |

        The two thresholds are read from two separate attributes and
        compared in two separate statements. §6.1's Warning forbids joining
        them: a single value removes the middle band, and §7's whole
        two-signal apparatus -- the disclaimer template, the
        `retrieval_support` column, the support matrix -- then has nothing
        to distinguish.

        This is the /retrieve entry point. Report generation uses
        classify_retrieval_support() below instead, which never raises,
        because a session that reached generation already passed this
        check at retrieval time.

        Raises
        ------
        ProjectionMismatchError
            M10 -- top-1 below the projection reject threshold. M11
            requires the reason code FRONTAL_MISMATCH, not
            DECLARED_LATERAL, and requires that this NOT be
            NotAChestRadiographError.
        """
        if self._projection_reject_threshold is None:
            raise ValueError(
                "PROJECTION_REJECT_THRESHOLD was not configured; the section 6.2 "
                "projection mismatch check cannot run"
            )

        # A retrieval that returned nothing has no top-1 to compare. It
        # cannot be a projection mismatch (nothing was measured against the
        # reject threshold), so it falls through to the support signal,
        # where "no retrieved case meets the threshold" is exactly true.
        if top1_similarity is None:
            return RetrievalSupport.BELOW_FLOOR

        # --- M10: the reject band. ---
        if top1_similarity < self._projection_reject_threshold:
            raise ProjectionMismatchError(
                top1_similarity=top1_similarity,
                reject_threshold=self._projection_reject_threshold,
            )

        # --- M8/M9: the remaining two bands. ---
        return self.classify_retrieval_support(top1_similarity)

    @property
    def projection_reject_threshold(self) -> float | None:
        """Exposed read-only so a caller can record WHICH threshold produced
        a rejection, without re-reading settings and risking a different
        value than this instance used."""
        return self._projection_reject_threshold

    @property
    def retrieval_floor(self) -> float:
        """Exposed read-only so a caller can record WHICH floor produced a
        stored category, without reaching back into settings and risking
        reading a different value than the one this instance used."""
        return self._retrieval_floor

    @property
    def modality_threshold(self) -> float:
        return self._modality_threshold


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _softmax(values: list[float], temperature: float) -> list[float]:
    """Numerically stable softmax with an explicit temperature.

    The max is subtracted before exponentiating -- standard practice, and
    not optional here: the temperature in use is the reciprocal of
    BiomedCLIP's learned logit scale (~85), so the scaled inputs reach
    roughly 40 and a naive exp() would overflow to inf and produce nan
    probabilities for perfectly ordinary inputs.
    """
    scaled = [v / temperature for v in values]
    largest = max(scaled)
    exponentials = [math.exp(v - largest) for v in scaled]
    total = sum(exponentials)
    return [e / total for e in exponentials]
