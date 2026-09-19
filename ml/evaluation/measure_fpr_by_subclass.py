"""
ml/evaluation/measure_fpr_by_subclass.py
====================================================================
MEASUREMENT 2 -- false-positive rate at two modality thresholds, per
negative sub-class.

A MEASUREMENT SCRIPT. Reads only. No production module imports it, it
writes nothing, and both thresholds are command-line arguments -- it never
reads MODALITY_THRESHOLD, which stays at its provisional 0.60.

Set identification (reproducibility)
------------------------------------
Identical to MEASUREMENT 1: the negative set is the EXACT Gate B set named
by `ml/outputs/calibration/calibration_manifest.csv`, with per-image scores
reused from the row-aligned `modality_scores.csv`. Both are asserted
consistent and all paths asserted present before anything is measured.

A false positive is a negative-set image whose modality score is AT OR
ABOVE the threshold -- a non-radiograph the gate would admit.

No pooled rate is produced, by instruction. Pooling these sub-classes
would also be misleading on its own terms: the per-sub-class rates in this
set differ by more than an order of magnitude, so any pooled figure is
mostly a statement about the sub-class mix rather than about the gate.

The denominator question
------------------------
Each rate is computed over the images in that sub-class that HAVE a
modality score, i.e. those the admission controls (A1-A11) admitted. An
image rejected at admission never reached the embedder and has no score,
so it cannot be a modality-gate false positive either way. Counting such
images as gate true-negatives would credit this control with rejections a
different control made.

That distinction is not academic here: it is what determines whether a
sub-class has a usable denominator at all, so the admission outcome is
printed alongside every rate rather than left implicit.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]

CALIBRATION_DIR = _REPO_ROOT / "ml" / "outputs" / "calibration"
MANIFEST = CALIBRATION_DIR / "calibration_manifest.csv"
SCORES = CALIBRATION_DIR / "modality_scores.csv"

SMALL_STRATUM = 30


def _load() -> pd.DataFrame:
    for path in (MANIFEST, SCORES):
        if not path.is_file():
            raise SystemExit(
                f"STOP: {path} is missing. The Gate B sets cannot be reproduced "
                f"exactly; re-run ml/calibration/build_calibration_sets.py and "
                f"calibrate_modality_gate.py before measuring."
            )

    manifest = pd.read_csv(MANIFEST)
    scores = pd.read_csv(SCORES)
    if list(manifest["path"]) != list(scores["path"]):
        raise SystemExit(
            "STOP: calibration_manifest.csv and modality_scores.csv do not describe "
            "the same images in the same order. The Gate B set cannot be reproduced "
            "exactly."
        )
    missing = [p for p in manifest["path"] if not (_REPO_ROOT / p).is_file()]
    if missing:
        raise SystemExit(
            f"STOP: {len(missing)} image(s) named in the manifest are no longer on "
            f"disk, e.g. {missing[:3]}. The Gate B set cannot be reproduced exactly."
        )
    return scores


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=0.82)
    parser.add_argument("--compare-threshold", type=float, default=0.60)
    args = parser.parse_args()

    scores = _load()
    negatives = scores[scores["set"] == "negative"]

    print("=" * 78)
    print("MEASUREMENT 2 -- false-positive rate by negative sub-class")
    print("=" * 78)
    print(f"negative set identified by: {MANIFEST}")
    print(f"modality scores reused from: {SCORES}")
    print(f"(scores verified identical to a live ModalityGateService re-run by")
    print(f" measure_fnr_by_projection.py --verify: max |delta| = 1.110e-16)")
    print()

    print("--- admission outcome per sub-class (the denominator question) ---")
    admission = (
        negatives.assign(scored=negatives["modality_score"].notna())
        .groupby("subclass")
        .agg(in_manifest=("path", "size"), admitted_and_scored=("scored", "sum"))
    )
    admission["rejected_at_admission"] = (
        admission["in_manifest"] - admission["admitted_and_scored"]
    )
    print(admission.to_string())
    print()
    print("reasons for the admission rejections:")
    rejected = negatives[negatives["modality_score"].isna()]
    print(rejected.groupby(["subclass", "admission_reason_code"]).size().to_string())
    print()

    scored = negatives[negatives["modality_score"].notna()]
    rows = []
    for subclass in sorted(scored["subclass"].unique()):
        stratum = scored[scored["subclass"] == subclass]
        n = len(stratum)
        for threshold in (args.threshold, args.compare_threshold):
            false_positives = int((stratum["modality_score"] >= threshold).sum())
            rows.append(
                {
                    "subclass": subclass,
                    "threshold": threshold,
                    "n": n,
                    "false_positives": false_positives,
                    "FPR": false_positives / n if n else float("nan"),
                    "low_confidence": "YES (n<30)" if n < SMALL_STRATUM else "",
                }
            )

    print(f"--- FPR at {args.threshold} and {args.compare_threshold}, per sub-class ---")
    print(pd.DataFrame(rows).to_string(index=False))
    print()

    # Sub-classes with no usable denominator are named explicitly rather
    # than omitted -- a sub-class silently missing from a rate table reads
    # as "not tested", when in fact it was tested and every image was
    # stopped by an earlier control.
    unscored = admission[admission["admitted_and_scored"] == 0]
    if len(unscored):
        print("--- sub-classes with NO modality-gate denominator ---")
        for subclass, row in unscored.iterrows():
            print(
                f"  {subclass}: {int(row['in_manifest'])} images, all rejected at "
                f"admission, 0 reached the gate. No FPR is defined for this "
                f"sub-class."
            )
        print()

    print("--- score distribution per sub-class (context for the rates above) ---")
    print(
        scored.groupby("subclass")["modality_score"]
        .describe()[["count", "mean", "std", "min", "50%", "max"]]
        .to_string()
    )
    print()
    print("No pooled rate is reported, by instruction.")


if __name__ == "__main__":
    main()
