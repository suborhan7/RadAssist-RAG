"""
ml/calibration/calibrate_modality_gate.py
====================================================================
Steps 4 to 10 of the Gate B calibration procedure in §11.2 of
docs/methodology/input_admission_modality_gate_architecture_v1.0_FROZEN.md.
Consumes the sets built by build_calibration_sets.py and writes the Gate B
tables.

  Step 4   modality score for every image in both sets
  Step 5   false-positive and false-negative rate at each threshold
  Step 6   lateral false-negative diagnosis (and what to do about it)
  Step 7   threshold selection, weighted toward a low false-negative rate
  Step 8   top-1 similarity for the positive set, grouped by disease label
  Step 9   per-label distribution comparison -> one global floor, or one
           floor per label group
  Step 10  record every selected value and every measured rate

The two rules that govern how the output must be read
-----------------------------------------------------
§11.2's closing Rule: "Report the measured rates only. Do not write an
improvement claim before the command output is available." Nothing in this
script asserts, claims, or compares against a prior system; it prints
measurements.

Rule F4: no threshold value may appear in the thesis before this script
has produced real command output for it. The tables this writes ARE that
output.

The gate is exercised through the real services
-----------------------------------------------
The score comes from ModalityGateService and the vectors from the frozen
shared/ embedder -- the same objects the backend runs. A second,
"equivalent" scoring implementation inside a calibration script is how a
calibrated threshold ends up not matching the deployed one.

Usage:
    python ml/calibration/calibrate_modality_gate.py --data-root .
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.services.image_admission_service import ImageAdmissionService  # noqa: E402
from app.services.exceptions import InputAdmissionError  # noqa: E402
from app.services.modality_gate_service import ModalityGateService  # noqa: E402
from shared.embeddings.biomedclip_embedder import BiomedCLIPEmbedder  # noqa: E402


class _EmbedderAdapter:
    """Adapts the shared embedder's batch API to the single-item IEmbedder
    shape ModalityGateService's constructor expects for its M6 prompt
    caching. Same adapter role as backend/app/infrastructure/
    biomedclip_adapter.py, not a second embedding implementation."""

    def __init__(self, embedder: BiomedCLIPEmbedder) -> None:
        self._embedder = embedder

    def embed_image(self, image_path: str) -> list[float]:
        return self._embedder.embed_images([image_path])[0].tolist()

    def embed_text(self, text: str) -> list[float]:
        return self._embedder.embed_texts([text])[0].tolist()


def _score_all(manifest: pd.DataFrame, gate: ModalityGateService, embedder: BiomedCLIPEmbedder,
               admission: ImageAdmissionService, repo_root: Path) -> pd.DataFrame:
    """Step 4, plus the admission outcome for each image.

    Both controls are run, because §6's Note is that they are independent
    and catch different things: a damaged file has no modality score at
    all, and reporting it as a modality-gate success or failure would
    misattribute which control protected the pipeline.
    """
    records = []
    embeddable_paths, embeddable_rows = [], []

    for _, row in manifest.iterrows():
        path = repo_root / str(row["path"])
        raw = path.read_bytes()
        record = dict(row)
        try:
            admission.admit(raw, path.suffix.lower())
            record["admitted"] = True
            record["admission_reason_code"] = ""
            embeddable_paths.append(str(path))
            embeddable_rows.append(len(records))
        except InputAdmissionError as exc:
            record["admitted"] = False
            record["admission_reason_code"] = exc.reason_code
        records.append(record)

    frame = pd.DataFrame(records)
    frame["modality_score"] = np.nan

    if embeddable_paths:
        vectors = embedder.embed_images(embeddable_paths)
        scores = [gate.score(vector.tolist()) for vector in vectors]
        frame.loc[embeddable_rows, "modality_score"] = scores

    return frame


def _rate_table(scored: pd.DataFrame, thresholds: np.ndarray) -> pd.DataFrame:
    """Step 5.

    Rates are computed over the images that HAVE a modality score. Damaged
    files are excluded here and reported separately: they never reached
    the gate, so counting them as gate true-negatives would credit this
    control with rejections the admission control actually made.
    """
    positives = scored[(scored["set"] == "positive") & scored["modality_score"].notna()]
    negatives = scored[(scored["set"] == "negative") & scored["modality_score"].notna()]
    laterals = positives[positives["projection"] == "Lateral"]
    frontals = positives[positives["projection"] == "Frontal"]

    # The false-positive rate is also broken out per negative sub-class.
    # A single pooled FPR would average a near-zero rate on photographs
    # together with a very high rate on other radiographs and report a
    # middling number that describes neither -- and which of the two is
    # driving it is the single most important thing this table has to say
    # about whether the gate is fit for its purpose.
    subclasses = sorted(negatives["subclass"].unique())

    rows = []
    for threshold in thresholds:
        row = {
            "threshold": round(float(threshold), 4),
            # A positive REJECTED by the gate is a false negative: a true
            # chest radiograph the system refused. DR-1's named
            # consequence, and the rate Step 7 says to weight most.
            "false_negative_rate": float((positives["modality_score"] < threshold).mean()),
            "fnr_frontal": float((frontals["modality_score"] < threshold).mean()),
            "fnr_lateral": float((laterals["modality_score"] < threshold).mean()),
            # A negative ACCEPTED by the gate is a false positive: the
            # strawberry defect getting through.
            "false_positive_rate": float((negatives["modality_score"] >= threshold).mean()),
            "n_positive": int(len(positives)),
            "n_negative": int(len(negatives)),
        }
        for subclass in subclasses:
            subset = negatives[negatives["subclass"] == subclass]
            row[f"fpr_{subclass}"] = float((subset["modality_score"] >= threshold).mean())
        rows.append(row)
    return pd.DataFrame(rows)


def _select_threshold(rates: pd.DataFrame, fnr_budget: float) -> tuple[float, str]:
    """Step 7: "Give more importance to a low false-negative rate, because
    a rejected true radiograph stops the clinical work."

    Encoded as a BUDGET on the false-negative rate rather than as an
    objective to minimize: take the highest threshold whose false-negative
    rate stays within `fnr_budget`, and break ties on the lowest
    false-positive rate.

    A pure "minimize the false-negative rate first, then the false-positive
    rate" reading was tried and rejected against this data, and the reason
    is worth recording because it is not obvious in the abstract. The
    false-negative rate on this positive set reaches exactly 0.0000 at
    thresholds around 0.01, so an FNR-first rule selects a threshold near
    zero and never looks at the false-positive rate at all -- it selected
    0.01, at which 31% of the negative set passes the gate. A control that
    admits a third of all non-radiographs does not implement DR-1, and
    "give more importance to" is a weighting instruction, not a licence to
    ignore the other rate entirely.

    The budget makes the trade-off an explicit, recorded input rather than
    an accident of where the FNR curve happens to bottom out. It is
    reported in the Gate B table as a selection input, and main() prints
    the selection under several budgets so the sensitivity is visible
    rather than buried.
    """
    within_budget = rates[rates["false_negative_rate"] <= fnr_budget]
    if within_budget.empty:
        # No threshold meets the budget. Report the failure rather than
        # silently relaxing it -- a budget quietly widened until something
        # fits is not a measurement.
        best = rates["false_negative_rate"].min()
        raise ValueError(
            f"no threshold achieves a false-negative rate within the budget "
            f"{fnr_budget}; the lowest observed rate is {best:.4f}"
        )
    best_fpr = within_budget["false_positive_rate"].min()
    candidates = within_budget[within_budget["false_positive_rate"] <= best_fpr]
    chosen = float(candidates["threshold"].max())
    reason = (
        f"highest threshold whose false-negative rate stays within the budget "
        f"{fnr_budget}; among those, the lowest false-positive rate ({best_fpr:.4f})"
    )
    return chosen, reason


def _support_table(scored: pd.DataFrame, repo_root: Path, top_k: int) -> pd.DataFrame:
    """Step 8: top-1 similarity for every positive-set image, grouped by
    disease label.

    Queried against the REAL ChromaDB collection the backend retrieves
    from, so the distribution is the one the retrieval floor will actually
    be compared against in production.

    The top voted label's agreement is recorded alongside the top-1
    similarity, which Step 8 does not ask for. It is measured here because
    §7.1's Warning is a claim about the JOINT behavior of the two signals
    -- that agreement can be high while support is low -- and a claim about
    a joint distribution cannot be checked from either marginal. With both
    columns in one table, main() can report how many held-out radiographs
    actually land in each cell of §7.2's support matrix, which turns that
    Warning from a stated risk into a measured frequency.
    """
    from app.infrastructure.chroma_store import ChromaVectorStore
    from app.services.label_voting_service import LabelVotingService

    store = ChromaVectorStore(
        persist_path=settings.CHROMA_PERSIST_PATH,
        collection_name=settings.CHROMA_COLLECTION_NAME,
    )
    embedder = BiomedCLIPEmbedder()
    # The SAME voter the backend uses, not a reimplementation of the vote.
    voter = LabelVotingService()

    positives = scored[(scored["set"] == "positive") & scored["modality_score"].notna()]
    paths = [str(repo_root / p) for p in positives["path"]]
    vectors = embedder.embed_images(paths)

    rows = []
    for (_, row), vector in zip(positives.iterrows(), vectors):
        cases = store.query(vector.tolist(), top_k)
        # SimilaritySearchPolicy is a no-op here (min_similarity 0.0, and
        # chroma already returns top_k in rank order), so the vote runs on
        # exactly the case list the backend would vote on.
        voted = voter.vote(cases)
        rows.append(
            {
                "study_uid": row["study_uid"],
                "projection": row["projection"],
                "primary_label": row["primary_label"],
                "top1_similarity": cases[0].similarity if cases else np.nan,
                "top_voted_label": voted[0].label if voted else "",
                "agreement": voted[0].agreement if voted else np.nan,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default=".")
    parser.add_argument("--top-k", type=int, default=5)
    # Step 7's "give more importance to a low false-negative rate",
    # expressed as an explicit budget. See _select_threshold() for why the
    # instruction is not read as a pure minimization. 0.02 = at most 2% of
    # genuine chest radiographs may be refused.
    parser.add_argument("--fnr-budget", type=float, default=0.02)
    args = parser.parse_args()

    repo_root = Path(args.data_root).resolve()
    out_dir = repo_root / "ml" / "outputs" / "calibration"
    manifest = pd.read_csv(out_dir / "calibration_manifest.csv")

    embedder = BiomedCLIPEmbedder()
    gate = ModalityGateService(
        embedder=_EmbedderAdapter(embedder),
        positive_prompts=settings.modality_prompts_positive,
        negative_prompts=settings.modality_prompts_negative,
        softmax_temperature=settings.MODALITY_SOFTMAX_TEMPERATURE,
        modality_threshold=settings.MODALITY_THRESHOLD,
        retrieval_floor=settings.RETRIEVAL_FLOOR,
    )
    admission = ImageAdmissionService(
        allowed_extensions=settings.upload_allowed_extensions,
        max_bytes=settings.UPLOAD_MAX_BYTES,
        min_bytes=settings.UPLOAD_MIN_BYTES,
        min_dimension_px=settings.IMAGE_MIN_DIMENSION_PX,
        max_dimension_px=settings.IMAGE_MAX_DIMENSION_PX,
        max_pixels=settings.IMAGE_MAX_PIXELS,
    )

    print("=" * 72)
    print("Gate B calibration -- input_admission_modality_gate_architecture_v1.0")
    print("=" * 72)
    print(f"prompt set (positive): {settings.modality_prompts_positive}")
    print(f"prompt set (negative): {settings.modality_prompts_negative}")
    print(f"softmax temperature:   {settings.MODALITY_SOFTMAX_TEMPERATURE!r}")

    # ---- Step 4 -----------------------------------------------------
    scored = _score_all(manifest, gate, embedder, admission, repo_root)
    scored.to_csv(out_dir / "modality_scores.csv", index=False)
    print(f"\n[Step 4] modality scores -> {out_dir / 'modality_scores.csv'}")

    print("\n[Step 4] admission control outcome by sub-class:")
    print(scored.groupby(["set", "subclass"])["admitted"].agg(["sum", "count"]).to_string())

    print("\n[Step 4] modality score distribution by sub-class:")
    described = (
        scored[scored["modality_score"].notna()]
        .groupby(["set", "subclass"])["modality_score"]
        .describe()[["count", "mean", "std", "min", "25%", "50%", "75%", "max"]]
    )
    print(described.to_string())

    # ---- Step 5 -----------------------------------------------------
    thresholds = np.round(np.arange(0.0, 1.0001, 0.01), 4)
    rates = _rate_table(scored, thresholds)
    rates.to_csv(out_dir / "threshold_rates.csv", index=False)
    print(f"\n[Step 5] rate table -> {out_dir / 'threshold_rates.csv'}")
    print(rates[rates["threshold"].isin([0.1, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99])].to_string(index=False))

    # ---- Step 6 -----------------------------------------------------
    provisional = rates[np.isclose(rates["threshold"], settings.MODALITY_THRESHOLD)]
    print("\n[Step 6] lateral vs frontal false-negative rate at the provisional threshold "
          f"({settings.MODALITY_THRESHOLD}):")
    if provisional.empty:
        print("  provisional threshold is not on the evaluated grid")
    else:
        row = provisional.iloc[0]
        print(f"  frontal FNR = {row['fnr_frontal']:.4f}    lateral FNR = {row['fnr_lateral']:.4f}")
        if row["fnr_lateral"] > row["fnr_frontal"]:
            print("  Lateral films score lower, as Step 2 anticipated. Step 6's remedy is to ADD")
            print("  a lateral prompt to MODALITY_PROMPTS_POSITIVE -- NOT to lower the threshold,")
            print("  which would weaken the control for all inputs.")
        else:
            print("  Lateral films do not show an elevated false-negative rate. Step 6's")
            print("  additional lateral prompt is not indicated by this measurement.")

    print("\n[Step 5] false-positive rate by negative sub-class:")
    fpr_columns = [c for c in rates.columns if c.startswith("fpr_")]
    print(
        rates[rates["threshold"].isin([0.5, 0.6, 0.9, 0.99])][["threshold"] + fpr_columns]
        .to_string(index=False)
    )

    # ---- Step 7 -----------------------------------------------------
    print("\n[Step 7] threshold selection under several false-negative budgets:")
    for budget in (0.005, 0.01, 0.02, 0.05):
        try:
            candidate, _ = _select_threshold(rates, budget)
        except ValueError as exc:
            print(f"  budget {budget:<6} -> {exc}")
            continue
        row = rates[np.isclose(rates["threshold"], candidate)].iloc[0]
        print(
            f"  budget {budget:<6} -> threshold {candidate:<6} "
            f"FNR {row['false_negative_rate']:.4f} "
            f"(frontal {row['fnr_frontal']:.4f} / lateral {row['fnr_lateral']:.4f})  "
            f"FPR {row['false_positive_rate']:.4f}"
        )

    selected_threshold, reason = _select_threshold(rates, args.fnr_budget)
    selected_row = rates[np.isclose(rates["threshold"], selected_threshold)].iloc[0]
    print(f"\n[Step 7] selected MODALITY_THRESHOLD = {selected_threshold}")
    print(f"  rule: {reason}")
    print(f"  at this threshold: FNR = {selected_row['false_negative_rate']:.4f} "
          f"(frontal {selected_row['fnr_frontal']:.4f} / lateral {selected_row['fnr_lateral']:.4f}), "
          f"FPR = {selected_row['false_positive_rate']:.4f}")
    for column in fpr_columns:
        print(f"    {column} = {selected_row[column]:.4f}")

    # ---- Steps 8 and 9 ----------------------------------------------
    support = _support_table(scored, repo_root, args.top_k)
    support.to_csv(out_dir / "top1_similarity_by_label.csv", index=False)
    print(f"\n[Step 8] top-1 similarity -> {out_dir / 'top1_similarity_by_label.csv'}")

    by_label = (
        support.groupby("primary_label")["top1_similarity"]
        .describe()[["count", "mean", "std", "min", "25%", "50%", "max"]]
        .sort_values("mean")
    )
    print("\n[Step 8] top-1 similarity distribution by disease label:")
    print(by_label.to_string())

    print("\n[Step 8] top-1 similarity distribution by projection:")
    print(support.groupby("projection")["top1_similarity"].describe()[
        ["count", "mean", "std", "min", "25%", "50%", "max"]].to_string())

    # Step 9's decision: does one global floor mark the rare labels as
    # uniformly weak? Answered by comparing each label's median against the
    # candidate global floor, restricted to labels with enough images for
    # the comparison to mean anything.
    #
    # The floor itself is the 10th percentile of the positive set's top-1
    # similarity: a floor is a statement about what counts as ORDINARY
    # retrieval support, so it is set where the weakest tenth of genuine
    # radiographs fall, not at a rate optimum -- there is no second class
    # to trade off against here, unlike the threshold in Step 7.
    global_floor = float(np.nanpercentile(support["top1_similarity"], 10))
    populous = by_label[by_label["count"] >= 10]
    below = populous[populous["50%"] < global_floor]

    print(f"\n[Step 9] candidate global RETRIEVAL_FLOOR = {global_floor:.4f}")
    print("  (10th percentile of the positive set's top-1 similarity)")
    print(f"  labels with n>=10 whose MEDIAN top-1 falls below this floor: {len(below)}")
    if len(below):
        print(below.to_string())
        print("  Step 9's condition is met: these labels would be marked uniformly weak by one")
        print("  global floor. Step 9 directs selecting one floor PER LABEL GROUP instead.")
    else:
        print("  No label's median falls below the candidate floor, so the distributions are")
        print("  similar in Step 9's sense and ONE GLOBAL FLOOR is the selection.")

    # ---- §7.1's Warning, as a measured frequency ---------------------
    # Not one of §11.2's numbered steps. §7.1 asserts that agreement and
    # retrieval support are independent signals that can disagree, and
    # builds the whole of §7 on that; this reports how often the
    # disagreement actually happens on held-out data, so the design's
    # premise is evidenced rather than assumed.
    matrix = support.dropna(subset=["top1_similarity", "agreement"]).copy()
    matrix["support"] = np.where(
        matrix["top1_similarity"] >= global_floor, "at_or_above_floor", "below_floor"
    )
    matrix["agreement_band"] = np.where(
        matrix["agreement"] >= settings.DISCLAIMER_AGREEMENT_THRESHOLD, "high", "low"
    )
    print(
        f"\n[§7.1] support matrix occupancy on the positive set "
        f"(floor {global_floor:.4f}, agreement threshold "
        f"{settings.DISCLAIMER_AGREEMENT_THRESHOLD}):"
    )
    print(
        pd.crosstab(matrix["support"], matrix["agreement_band"])
        .reindex(index=["at_or_above_floor", "below_floor"], columns=["high", "low"], fill_value=0)
        .to_string()
    )
    warned = matrix[(matrix["support"] == "below_floor") & (matrix["agreement_band"] == "high")]
    print(
        f"  §7.1's warned-about cell (HIGH agreement, LOW support): {len(warned)} of "
        f"{len(matrix)} held-out radiographs ({len(warned) / max(len(matrix), 1):.1%}).\n"
        f"  These are the cases where a disclaimer reading only the agreement score would\n"
        f"  report confidence on evidence that does not meet the support threshold."
    )

    # ---- Step 10 ----------------------------------------------------
    gate_b = pd.DataFrame(
        [
            {"setting": "MODALITY_PROMPTS_POSITIVE",
             "selected_value": "|".join(settings.modality_prompts_positive),
             "evidence": "initial set, §11.1; Step 6 check reported above"},
            {"setting": "MODALITY_PROMPTS_NEGATIVE",
             "selected_value": "|".join(settings.modality_prompts_negative),
             "evidence": "initial set, §11.1"},
            {"setting": "MODALITY_SOFTMAX_TEMPERATURE",
             "selected_value": f"{settings.MODALITY_SOFTMAX_TEMPERATURE!r}",
             "evidence": "reciprocal of BiomedCLIP's learned logit_scale (85.2322769165039)"},
            {"setting": "MODALITY_THRESHOLD",
             "selected_value": f"{selected_threshold}",
             "evidence": f"Step 7; {reason}; FNR={selected_row['false_negative_rate']:.4f} "
                         f"(frontal {selected_row['fnr_frontal']:.4f} / lateral "
                         f"{selected_row['fnr_lateral']:.4f}), "
                         f"FPR={selected_row['false_positive_rate']:.4f}, "
                         f"n_pos={int(selected_row['n_positive'])}, n_neg={int(selected_row['n_negative'])}"},
            {"setting": "(selection input) FNR budget",
             "selected_value": f"{args.fnr_budget}",
             "evidence": "Step 7's 'give more importance to a low false-negative rate', "
                         "as an explicit budget; see _select_threshold()"},
            {"setting": "RETRIEVAL_FLOOR",
             "selected_value": f"{global_floor:.4f}",
             "evidence": f"Step 9; 10th percentile of positive-set top-1 similarity "
                         f"(n={int(support['top1_similarity'].notna().sum())}); "
                         f"{len(below)} populous labels below it -> "
                         f"{'per-label floors indicated' if len(below) else 'one global floor'}"},
        ]
    )
    gate_b.to_csv(out_dir / "gate_b_selected_values.csv", index=False)
    print(f"\n[Step 10] Gate B selections -> {out_dir / 'gate_b_selected_values.csv'}")
    print(gate_b.to_string(index=False))

    missing = {"other_radiograph_modality"} - set(scored["subclass"])
    if missing:
        print(f"\nGAP: negative-set sub-class(es) absent: {sorted(missing)}. The false-positive")
        print("rate above does not cover them.")


if __name__ == "__main__":
    main()
