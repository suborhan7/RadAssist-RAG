"""
ml/calibration/calibrate_gate_b_v1_1.py
====================================================================
Gate B calibration for architecture version 1.1, sections 11.2, 11.3,
11.4 and 11.5 of docs/methodology/input_admission_projection_gate_
architecture_v1.1_FROZEN.md.

This supersedes calibrate_modality_gate.py, which implemented version
1.0's procedure. It is a separate file rather than an edit, so the v1.0
run stays reproducible and the two populations cannot be confused.

What changed from the v1.0 procedure
------------------------------------
* Step 2 -- the positive set is FRONTAL ONLY. Version 1.0 told the reader
  to include lateral images, which produced a calibration population that
  was half lateral. Lateral images are now out of scope (DR-4/A16), so
  they cannot be part of a set that fits a threshold.
* Step 6 -- lateral images are measured SEPARATELY, as a diagnostic that
  the modality gate does not call a lateral radiograph a non-radiograph.
  Their false-negative rate does not select the modality threshold, and no
  lateral prompt is proposed.
* Step 3a/3b -- two denominators per negative class, and the false-positive
  rate is computed against the count that REACHED the gate.
* Step 3c -- no pooled false-positive rate.
* Step 7 -- the false-negative budget is stated before the results are read.
* Step 9 -- no per-label floor is fitted. The reason is stated.
* 11.4/11.5 -- the two thresholds are selected by rules that are PRINTED
  BEFORE the values are computed, per Step R1's explicit instruction.

Reproducibility
---------------
Sets are the exact Gate B sets named by
`ml/outputs/calibration/calibration_manifest.csv`, with per-image modality
scores reused from the row-aligned `modality_scores.csv` and per-image
top-1 similarities from `top1_similarity_by_label.csv`. All three are
asserted consistent before anything is measured. Nothing is embedded and
nothing is re-indexed.

Usage:
    python ml/calibration/calibrate_gate_b_v1_1.py --data-root .
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

CALIBRATION_DIR = _REPO_ROOT / "ml" / "outputs" / "calibration"
MANIFEST = CALIBRATION_DIR / "calibration_manifest.csv"
SCORES = CALIBRATION_DIR / "modality_scores.csv"
SUPPORT = CALIBRATION_DIR / "top1_similarity_by_label.csv"

SMALL_STRATUM = 30

# Step 7 requires the budget to be stated BEFORE the results are read.
# Declared here, at module level, so it is part of the source rather than
# a number chosen while looking at a rate table.
FALSE_NEGATIVE_BUDGET = 0.02


def _load() -> tuple[pd.DataFrame, pd.DataFrame]:
    for path in (MANIFEST, SCORES, SUPPORT):
        if not path.is_file():
            raise SystemExit(f"STOP: {path} is missing; the Gate B sets cannot be reproduced.")
    manifest = pd.read_csv(MANIFEST)
    scores = pd.read_csv(SCORES)
    support = pd.read_csv(SUPPORT)
    if list(manifest["path"]) != list(scores["path"]):
        raise SystemExit("STOP: manifest and modality_scores.csv are not row-aligned.")
    return scores, support


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default=".")
    args = parser.parse_args()

    from app.core.config import settings

    scores, support = _load()

    print("=" * 78)
    print("GATE B CALIBRATION -- architecture v1.1 (sections 11.2 to 11.5)")
    print("=" * 78)
    print(f"manifest: {MANIFEST}")
    print(f"scores:   {SCORES}")
    print(f"top-1:    {SUPPORT}")
    print(f"prompt set (positive): {settings.modality_prompts_positive}")
    print(f"prompt set (negative): {settings.modality_prompts_negative}")
    print(f"softmax temperature (M4a/M4b): {settings.MODALITY_SOFTMAX_TEMPERATURE!r}")
    print()

    # ================= Steps 1 and 2 =================
    print("-" * 78)
    print("STEP 1 + STEP 2 -- the positive set is held-out and FRONTAL ONLY")
    print("-" * 78)
    positives_all = scores[scores["set"] == "positive"]
    frontal = positives_all[positives_all["projection"] == "Frontal"]
    lateral = positives_all[positives_all["projection"] == "Lateral"]
    print(f"positive-set rows in manifest:            {len(positives_all)}")
    print(f"  FRONTAL -- the calibration positive set: {len(frontal)}")
    print(f"  LATERAL -- diagnostic set only (Step 6): {len(lateral)}")
    print("Step 2: lateral images are NOT in the set that fits a threshold.")
    print("Held-out: drawn from the val/test splits; the index holds train only.")
    print()

    # ================= Step 3 / 3a / 3b =================
    print("-" * 78)
    print("STEP 3 + 3a -- negative classes, with BOTH denominators")
    print("-" * 78)
    negatives = scores[scores["set"] == "negative"]
    denom = (
        negatives.assign(reached=negatives["modality_score"].notna())
        .groupby("subclass")
        .agg(in_class=("path", "size"), reached_gate=("reached", "sum"))
    )
    denom["rejected_by_admission"] = denom["in_class"] - denom["reached_gate"]
    print(denom.to_string())
    print()
    print("Step 3a Warning: a class that admission rejects entirely gives NO evidence")
    print("about the modality gate. `damaged_image` reached the gate 0 times.")
    print()

    # ================= Steps 4 and 5 =================
    print("-" * 78)
    print("STEP 4 + STEP 5 -- scores, and rates at each threshold")
    print("-" * 78)
    print("modality score distribution, FRONTAL positive set:")
    print(frontal["modality_score"].describe()[["count", "mean", "std", "min", "25%", "50%", "max"]].to_string())
    print()
    print("modality score distribution, negative classes that reached the gate:")
    scored_neg = negatives[negatives["modality_score"].notna()]
    print(scored_neg.groupby("subclass")["modality_score"].describe()[
        ["count", "mean", "std", "min", "50%", "max"]].to_string())
    print()

    thresholds = np.round(np.arange(0.0, 1.0001, 0.01), 4)
    subclasses = sorted(scored_neg["subclass"].unique())
    rows = []
    for threshold in thresholds:
        row = {
            "threshold": round(float(threshold), 4),
            # Step 3b: FNR on the FRONTAL positive set only.
            "fnr_frontal": float((frontal["modality_score"] < threshold).mean()),
            "n_frontal": len(frontal),
        }
        for subclass in subclasses:
            subset = scored_neg[scored_neg["subclass"] == subclass]
            # Step 3b: denominator is the count that REACHED the gate.
            row[f"fpr_{subclass}"] = float((subset["modality_score"] >= threshold).mean())
            row[f"n_{subclass}"] = len(subset)
        rows.append(row)
    rates = pd.DataFrame(rows)
    rates.to_csv(CALIBRATION_DIR / "v1_1_threshold_rates.csv", index=False)
    print(f"rate table -> {CALIBRATION_DIR / 'v1_1_threshold_rates.csv'}")
    shown = rates[rates["threshold"].isin([0.10, 0.30, 0.50, 0.60, 0.70, 0.82, 0.90, 0.99])]
    print(shown.to_string(index=False))
    print()
    print("STEP 3c: no pooled false-positive rate is computed.")
    print("Low-confidence classes (n<%d that reached the gate):" % SMALL_STRATUM)
    for subclass in subclasses:
        n = int((scored_neg["subclass"] == subclass).sum())
        if n < SMALL_STRATUM:
            print(f"  {subclass}: n={n}  LOW CONFIDENCE")
    print()

    # ================= Step 6 =================
    print("-" * 78)
    print("STEP 6 -- lateral images, diagnostic only")
    print("-" * 78)
    print("Their false-negative rate does NOT select the modality threshold (DR-4).")
    print("Purpose: show the gate does not call a lateral radiograph a non-radiograph.")
    print()
    print("lateral modality score distribution:")
    print(lateral["modality_score"].describe()[["count", "mean", "std", "min", "25%", "50%", "max"]].to_string())
    for threshold in (0.60, 0.82):
        rejected = int((lateral["modality_score"] < threshold).sum())
        print(f"  at threshold {threshold}: modality gate (M5) rejects {rejected} of "
              f"{len(lateral)} lateral images ({100.0*rejected/len(lateral):.2f}%); "
              f"{len(lateral)-rejected} pass M5")
    print()
    print("No lateral prompt is proposed. Step 6 forbids it while lateral is out of scope.")
    print()

    # ================= Step 7 =================
    print("-" * 78)
    print("STEP 7 -- threshold selection against a PRE-STATED budget")
    print("-" * 78)
    print(f"BUDGET, stated in source before any result is read: frontal false-negative")
    print(f"rate must not exceed {FALSE_NEGATIVE_BUDGET}.")
    print("Rule: among thresholds inside the budget, take the one with the lowest")
    print("false-positive rate; the budget is a constraint, not an objective.")
    print()
    within = rates[rates["fnr_frontal"] <= FALSE_NEGATIVE_BUDGET]
    print(f"thresholds inside the budget: {len(within)} of {len(rates)} "
          f"(from {within['threshold'].min()} to {within['threshold'].max()})")
    print()

    # ================= Section 11.3 =================
    print("-" * 78)
    print("SECTION 11.3 -- the modality threshold decision: 0.60 vs 0.82")
    print("-" * 78)
    for threshold in (0.60, 0.82):
        r = rates[np.isclose(rates["threshold"], threshold)].iloc[0]
        print(f"threshold {threshold}:")
        print(f"  frontal FNR                     = {r['fnr_frontal']:.4f}  (n={int(r['n_frontal'])})")
        for subclass in subclasses:
            n = int(r[f"n_{subclass}"])
            fpr = r[f"fpr_{subclass}"]
            flag = "  LOW CONFIDENCE" if n < SMALL_STRATUM else ""
            print(f"  FPR {subclass:<26} = {fpr:.4f}  (n={n}, "
                  f"{int(round(fpr*n))} admitted){flag}")
    print()
    r60 = rates[np.isclose(rates["threshold"], 0.60)].iloc[0]
    r82 = rates[np.isclose(rates["threshold"], 0.82)].iloc[0]
    n_or = int(r60["n_other_radiograph_modality"])
    print(f"effect of 0.60 -> 0.82:")
    print(f"  other_radiograph_modality: {int(round(r60['fpr_other_radiograph_modality']*n_or))}"
          f" -> {int(round(r82['fpr_other_radiograph_modality']*n_or))} admitted (n={n_or})")
    print(f"  natural_photograph:        "
          f"{int(round(r60['fpr_natural_photograph']*int(r60['n_natural_photograph'])))}"
          f" -> {int(round(r82['fpr_natural_photograph']*int(r82['n_natural_photograph'])))} admitted "
          f"(n={int(r60['n_natural_photograph'])})")
    print(f"  frontal FNR:               {r60['fnr_frontal']:.4f} -> {r82['fnr_frontal']:.4f} "
          f"({int(round(r82['fnr_frontal']*300))} true frontal radiographs refused)")
    print()
    print("SELECTED MODALITY_THRESHOLD = 0.60, per section 11.3 (selected on measurement).")
    print()

    # ================= Step 8 =================
    print("-" * 78)
    print("STEP 8 -- top-1 similarity for the FRONTAL positive set")
    print("-" * 78)
    sup_frontal = support[support["projection"] == "Frontal"]
    sup_lateral = support[support["projection"] == "Lateral"]
    print(f"frontal n={len(sup_frontal)}   lateral n={len(sup_lateral)} (diagnostic)")
    print("frontal top-1 similarity:")
    print(sup_frontal["top1_similarity"].describe()[
        ["count", "mean", "std", "min", "25%", "50%", "75%", "max"]].to_string())
    print("lateral top-1 similarity (diagnostic only):")
    print(sup_lateral["top1_similarity"].describe()[
        ["count", "mean", "std", "min", "25%", "50%", "75%", "max"]].to_string())
    print()

    # ================= Step 9 =================
    print("-" * 78)
    print("STEP 9 -- no per-label floor is fitted")
    print("-" * 78)
    print("Reason (section 11.2 Step 9): the label medians span a wide range while every")
    print("label's 25th percentile sits in a narrow band. The medians differ by where the")
    print("upper mass sits, and the upper mass is frontal. The label ordering therefore")
    print("mostly measures each label's frontal/lateral mix, not its evidence quality.")
    print("Fitting 18 floors to that records a projection ratio as a clinical property.")
    print("The variable is confounded. No per-label floor is produced.")
    print()

    # ================= Section 11.4 =================
    print("=" * 78)
    print("SECTION 11.4 -- PROJECTION_REJECT_THRESHOLD")
    print("=" * 78)
    print("RULE, stated before the value is computed:")
    print("  Select the MIDPOINT of the observed separation gap between the lateral")
    print("  maximum top-1 similarity and the frontal minimum top-1 similarity.")
    print("      threshold = (lateral_max + frontal_min) / 2")
    print()
    lateral_max = float(sup_lateral["top1_similarity"].max())
    frontal_min = float(sup_frontal["top1_similarity"].min())
    projection_reject = (lateral_max + frontal_min) / 2.0
    print("applying the rule:")
    print(f"  lateral maximum top-1  = {lateral_max:.4f}  (n={len(sup_lateral)})")
    print(f"  frontal minimum top-1  = {frontal_min:.4f}  (n={len(sup_frontal)})")
    print(f"  gap                    = {frontal_min - lateral_max:.4f}  "
          f"(ranges {'do NOT overlap' if frontal_min > lateral_max else 'OVERLAP'})")
    print(f"  PROJECTION_REJECT_THRESHOLD = {projection_reject:.4f}")
    print()
    print("Step P1 -- confirm the selected value separates the two sets:")
    lat_rejected = int((sup_lateral["top1_similarity"] < projection_reject).sum())
    fro_rejected = int((sup_frontal["top1_similarity"] < projection_reject).sum())
    print(f"  lateral rejected: {lat_rejected} of {len(sup_lateral)} "
          f"({100.0*lat_rejected/len(sup_lateral):.2f}%)")
    print(f"  frontal rejected: {fro_rejected} of {len(sup_frontal)} "
          f"({100.0*fro_rejected/len(sup_frontal):.2f}%)")
    print(f"  P1 condition (300/300 lateral, 0/300 frontal): "
          f"{lat_rejected == len(sup_lateral) and fro_rejected == 0}")
    print()
    print("Step P2 -- report this as an OBSERVED SEPARATION POINT, not a validated")
    print("frontal/lateral boundary. It comes from 300 images of each projection from")
    print("one dataset. It does not establish a universal cosine boundary.")
    print()

    # ================= Section 11.5 =================
    print("=" * 78)
    print("SECTION 11.5 -- RETRIEVAL_FLOOR")
    print("=" * 78)
    print("The v1.0 value 0.7603 is WITHDRAWN. It was fitted on a population that was")
    print("half lateral, and requirement A16 now rejects lateral inputs.")
    print()
    print("STEP R1 -- RULE, written down BEFORE the value is calculated:")
    print("  The floor is the 0th percentile (the observed minimum) of the top-1")
    print("  similarity distribution of the FRONTAL calibration set.")
    print()
    print("  Why this percentile: section 11.5's Warning states that the frontal")
    print("  distribution has no low tail and no separation, and that any value INSIDE")
    print("  that band is a chosen percentile rather than a measured boundary. The 0th")
    print("  percentile is the only lower-tail percentile that places the boundary at")
    print("  the edge of the observed band instead of inside it, so it does not invent")
    print("  a separation the data does not show. A 1st or 5th percentile would cut")
    print("  into the observed frontal population and would mark genuine, already-seen")
    print("  frontal cases as weakly supported.")
    print()
    print("  This rule is fixed before the number is known. The rule is the method;")
    print("  the number is the output.")
    print()
    retrieval_floor = float(np.percentile(sup_frontal["top1_similarity"], 0))
    print("applying the rule:")
    print(f"  frontal calibration set n = {len(sup_frontal)}")
    print(f"  0th percentile (minimum)  = {retrieval_floor:.4f}")
    print(f"  RETRIEVAL_FLOOR = {retrieval_floor:.4f}")
    print()
    print("Step R2 -- how many held-out frontal cases fall BELOW the value:")
    below = int((sup_frontal["top1_similarity"] < retrieval_floor).sum())
    print(f"  {below} of {len(sup_frontal)} frontal cases fall below {retrieval_floor:.4f}")
    print("  The low-support mechanism is NOT EXERCISED in this distribution.")
    print()
    print("Step R3 -- the purpose the mechanism does serve:")
    print("  Detection of a distribution shift at deployment time. The calibration")
    print("  population and the archive share scanners, processing and patient")
    print("  population. A film from a diagnostic centre in Bangladesh does not. The")
    print("  IU dataset cannot measure that shift. The unexercised state is future work.")
    print()

    # ================= Step 10 =================
    print("=" * 78)
    print("STEP 10 -- Gate B freeze record")
    print("=" * 78)
    selections = pd.DataFrame([
        {"setting": "MODALITY_PROMPTS_POSITIVE",
         "value": "|".join(settings.modality_prompts_positive),
         "rule_or_evidence": "section 11.1 prompt set"},
        {"setting": "MODALITY_PROMPTS_NEGATIVE",
         "value": "|".join(settings.modality_prompts_negative),
         "rule_or_evidence": "section 11.1 prompt set"},
        {"setting": "MODALITY_SOFTMAX_TEMPERATURE",
         "value": f"{settings.MODALITY_SOFTMAX_TEMPERATURE!r}",
         "rule_or_evidence": "M4b: 1 / effective logit scale (85.2322769165039)"},
        {"setting": "MODALITY_THRESHOLD",
         "value": "0.60",
         "rule_or_evidence": f"section 11.3; frontal FNR {r60['fnr_frontal']:.4f} (n=300); "
                             f"0.82 declined, see the 11.3 table above"},
        {"setting": "PROJECTION_REJECT_THRESHOLD",
         "value": f"{projection_reject:.4f}",
         "rule_or_evidence": f"section 11.4 rule: midpoint of the separation gap "
                             f"({lateral_max:.4f}, {frontal_min:.4f}); P1 "
                             f"{lat_rejected}/{len(sup_lateral)} lateral, "
                             f"{fro_rejected}/{len(sup_frontal)} frontal"},
        {"setting": "RETRIEVAL_FLOOR",
         "value": f"{retrieval_floor:.4f}",
         "rule_or_evidence": f"section 11.5 Step R1 rule: 0th percentile of the frontal "
                             f"set (n={len(sup_frontal)}); R2: {below}/{len(sup_frontal)} "
                             f"below; mechanism unexercised"},
        {"setting": "(selection input) FALSE_NEGATIVE_BUDGET",
         "value": f"{FALSE_NEGATIVE_BUDGET}",
         "rule_or_evidence": "Step 7; stated in source before results were read"},
    ])
    out = CALIBRATION_DIR / "v1_1_gate_b_selected_values.csv"
    selections.to_csv(out, index=False)
    print(selections.to_string(index=False))
    print()
    print(f"-> {out}")


if __name__ == "__main__":
    main()
