"""
ml/evaluation/measure_support_distribution_by_label.py
====================================================================
MEASUREMENT 4 -- distribution of top-1 retrieval similarity across the
positive set, grouped by disease label.

A MEASUREMENT SCRIPT. Reads only. No production module imports it and it
writes nothing.

This reports a DISTRIBUTION. It does not propose, select, or recommend a
per-label floor, and it does not evaluate whether one is warranted -- by
instruction, and because a floor is a Gate B selection that belongs to the
calibration procedure, not to a diagnostic read of its inputs. The
comparison value below is used ONLY to count rows on each side of it.

Set identification (reproducibility)
------------------------------------
`ml/outputs/calibration/top1_similarity_by_label.csv` -- the Gate B run's
own per-image output, one row per positive-set image, produced by querying
the real `iu_cxr_biomedclip_v1_train` ChromaDB collection. Its rows
correspond to the 600 positive rows of
`ml/outputs/calibration/calibration_manifest.csv` (cross-checked below on
study_uid and projection), which is the identifier of record for the set.

The comparison value 0.7603 is the RETRIEVAL_FLOOR selected by the Gate B
run (`gate_b_selected_values.csv`) and currently the settings default. It
is passed as an argument rather than read from settings so this script
states its own comparison point explicitly and cannot silently change
meaning if the setting is recalibrated.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]

CALIBRATION_DIR = _REPO_ROOT / "ml" / "outputs" / "calibration"
MANIFEST = CALIBRATION_DIR / "calibration_manifest.csv"
SUPPORT = CALIBRATION_DIR / "top1_similarity_by_label.csv"

SMALL_STRATUM = 30


def _stats(values: pd.Series, floor: float, name: str) -> dict:
    n = int(values.notna().sum())
    below = int((values < floor).sum())
    return {
        "label": name,
        "n": n,
        "min": values.min(),
        "p25": values.quantile(0.25),
        "median": values.median(),
        "p75": values.quantile(0.75),
        "max": values.max(),
        f"n_below_{floor}": below,
        f"frac_below_{floor}": below / n if n else float("nan"),
        "low_confidence": "YES (n<30)" if n < SMALL_STRATUM else "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--floor", type=float, default=0.7603)
    args = parser.parse_args()

    for path in (MANIFEST, SUPPORT):
        if not path.is_file():
            raise SystemExit(
                f"STOP: {path} is missing. The Gate B positive set cannot be "
                f"reproduced exactly; re-run ml/calibration/build_calibration_sets.py "
                f"and calibrate_modality_gate.py before measuring."
            )

    support = pd.read_csv(SUPPORT)
    manifest = pd.read_csv(MANIFEST)
    positives = manifest[manifest["set"] == "positive"]

    # Cross-check that this file really describes the manifest's positive
    # set, rather than trusting the row count alone.
    support_keys = sorted(
        zip(support["study_uid"].astype("int64"), support["projection"].astype(str))
    )
    manifest_keys = sorted(
        zip(positives["study_uid"].astype("int64"), positives["projection"].astype(str))
    )
    if support_keys != manifest_keys:
        raise SystemExit(
            "STOP: top1_similarity_by_label.csv does not describe the same "
            "(study_uid, projection) set as the manifest's positive rows. The Gate B "
            "set cannot be reproduced exactly."
        )

    print("=" * 78)
    print("MEASUREMENT 4 -- top-1 retrieval similarity distribution by disease label")
    print("=" * 78)
    print(f"positive set identified by: {MANIFEST}  (600 positive rows)")
    print(f"top-1 similarities from:    {SUPPORT}")
    print(f"cross-check on (study_uid, projection): PASS ({len(support_keys)} rows matched)")
    print(f"collection queried at Gate B time: iu_cxr_biomedclip_v1_train")
    print(f"comparison value (Gate B RETRIEVAL_FLOOR): {args.floor}")
    print()
    print(f"rows with a top-1 similarity: {int(support['top1_similarity'].notna().sum())}")
    print(f"distinct labels: {support['primary_label'].nunique()}")
    print()

    rows = [
        _stats(group["top1_similarity"], args.floor, label)
        for label, group in support.groupby("primary_label")
    ]
    table = pd.DataFrame(rows).sort_values("median").reset_index(drop=True)

    print("--- per-label distribution, sorted by median ascending ---")
    print(
        table.to_string(
            index=False,
            float_format=lambda v: f"{v:.4f}",
        )
    )
    print()

    small = table[table["n"] < SMALL_STRATUM]
    print(
        f"--- low-confidence strata: {len(small)} of {len(table)} labels have n<{SMALL_STRATUM} ---"
    )
    print(
        "Every rate from these rows is reported with its n above and must not be read "
        "as a\nstable estimate. Combined they cover "
        f"{int(small['n'].sum())} of {int(table['n'].sum())} images."
    )
    print(small[["label", "n"]].to_string(index=False))
    print()

    pooled = _stats(support["top1_similarity"], args.floor, "ALL LABELS POOLED")
    print("--- pooled across all labels, for comparison ---")
    print(pd.DataFrame([pooled]).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print()

    print("--- same statistics by projection, for comparison ---")
    projection_rows = [
        _stats(group["top1_similarity"], args.floor, projection)
        for projection, group in support.groupby("projection")
    ]
    print(
        pd.DataFrame(projection_rows)
        .sort_values("median")
        .to_string(index=False, float_format=lambda v: f"{v:.4f}")
    )
    print()
    print("No per-label floor is proposed or selected. Distribution only, by instruction.")


if __name__ == "__main__":
    main()
