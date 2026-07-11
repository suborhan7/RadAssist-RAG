"""
analyze_results.py
====================================================================
Phase 0, step 3b  --  the actual decision layer.

Consumes the per-query CSVs written by run_encoder_eval.py (outputs/per_query/
*.csv) and computes what point estimates alone cannot: whether the observed
gaps between encoders are distinguishable from noise.

Two things happen here that a bare comparison table cannot give you:

1. Class-stratified bootstrap CIs on the MACRO metrics (resampling queries
   WITHIN each primary_label class, then recomputing the macro mean each
   resample -- this preserves the "average over classes" structure instead of
   just resampling all queries pooled, which would let large classes dominate
   the CI the same way they dominate a plain average).

2. PAIRED bootstrap on the difference between two encoders (e.g. biomedclip -
   random). Paired is correct here because every encoder was evaluated on the
   exact same query set -- using the same bootstrap resample for both sides of
   a comparison cancels shared query-level variance and gives a tighter,
   correct estimate of whether encoder A truly beats encoder B, rather than
   just independently overlapping two noisy point estimates.

Applies the three pre-registered gates from the Phase 0 protocol:
    Gate 1: BiomedCLIP macro Recall@5 clears `random`,      95% CI excludes 0
    Gate 2: BiomedCLIP macro Recall@5 AND nDCG@10 clear `clip_generic`, CI excludes 0
    Gate 3: per-class wins concentrate on real findings, not just Normal/Other

Outputs:
    outputs/gate_decision_table.csv   -- the actual GO/NO-GO evidence
    outputs/manual_review_sample.csv  -- stratified sample for the qualitative check
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import yaml


NON_FINDING_CLASSES = {"Other Abnormality", "Support Devices"}  # excluded from Gate 3's "real findings" view


def stratified_bootstrap_macro(
    df: pd.DataFrame, metric: str, n_boot: int, rng: np.random.Generator
) -> np.ndarray:
    """
    Resample queries WITHIN each primary_label class (with replacement),
    recompute the macro mean (mean of per-class means) each time.
    Returns an array of n_boot macro-metric values.
    """
    groups = {cls: g[metric].to_numpy() for cls, g in df.groupby("primary_label")}
    out = np.empty(n_boot, dtype=np.float64)
    for b in range(n_boot):
        class_means = []
        for vals in groups.values():
            idx = rng.integers(0, len(vals), size=len(vals))
            class_means.append(vals[idx].mean())
        out[b] = float(np.mean(class_means))
    return out


def paired_stratified_bootstrap_diff(
    df_a: pd.DataFrame, df_b: pd.DataFrame, metric: str, n_boot: int, rng: np.random.Generator
) -> np.ndarray:
    """
    Same resample indices applied to BOTH encoders (paired), within each class,
    then macro-diff = macro(A) - macro(B) per resample. df_a/df_b must share the
    same uid set and ordering per class.
    """
    a_groups = {cls: g.sort_values("uid")[metric].to_numpy() for cls, g in df_a.groupby("primary_label")}
    b_groups = {cls: g.sort_values("uid")[metric].to_numpy() for cls, g in df_b.groupby("primary_label")}
    classes = list(a_groups.keys())
    out = np.empty(n_boot, dtype=np.float64)
    for b in range(n_boot):
        a_means, b_means = [], []
        for cls in classes:
            n = len(a_groups[cls])
            idx = rng.integers(0, n, size=n)   # same resample -> paired
            a_means.append(a_groups[cls][idx].mean())
            b_means.append(b_groups[cls][idx].mean())
        out[b] = float(np.mean(a_means) - np.mean(b_means))
    return out


def ci(arr: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
    lo = float(np.percentile(arr, 100 * alpha / 2))
    hi = float(np.percentile(arr, 100 * (1 - alpha / 2)))
    return lo, hi


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase0_config.yaml")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--manual-sample-n", type=int, default=40)
    args = ap.parse_args()

    with open(args.config) as fh:
        cfg = yaml.safe_load(fh)
    out_dir = Path(cfg["paths"]["out_dir"])
    metadata_dir = Path(cfg["paths"]["metadata_dir"])
    splits_dir = Path(cfg["paths"]["splits_dir"])
    pq_dir = out_dir / "per_query"
    rng = np.random.default_rng(args.seed)

    encoders = cfg["eval"]["encoders"]
    data: Dict[str, pd.DataFrame] = {}
    for enc in encoders:
        p = pq_dir / f"{enc}.csv"
        if not p.exists():
            raise FileNotFoundError(
                f"{p} missing. Run run_encoder_eval.py first (it now writes per-query CSVs).")
        data[enc] = pd.read_csv(p)

    key_metrics = ["recall@5", "ndcg@10"]

    # ---- Gate 1 & 2: paired bootstrap on the differences that matter -------
    comparisons = []
    if "biomedclip" in data and "random" in data:
        comparisons.append(("biomedclip", "random", "Gate 1"))
    if "biomedclip" in data and "clip_generic" in data:
        comparisons.append(("biomedclip", "clip_generic", "Gate 2"))

    rows: List[dict] = []
    for a, b, gate in comparisons:
        for metric in key_metrics:
            diffs = paired_stratified_bootstrap_diff(data[a], data[b], metric, args.n_boot, rng)
            lo, hi = ci(diffs)
            point_delta = float(diffs.mean())
            excludes_zero = lo > 0 or hi < 0
            rows.append({
                "gate": gate, "encoder_a": a, "encoder_b": b, "metric": metric,
                "delta": round(point_delta, 4), "ci_lower": round(lo, 4), "ci_upper": round(hi, 4),
                "ci_excludes_zero": excludes_zero,
                "direction": "A>B" if point_delta > 0 else "A<B",
            })

    gate_df = pd.DataFrame(rows)
    gate_df.to_csv(out_dir / "gate_decision_table.csv", index=False)

    print("=" * 78)
    print(f"BOOTSTRAP GATE DECISION TABLE  (n_boot={args.n_boot}, class-stratified, paired)")
    print("=" * 78)
    print(gate_df.to_string(index=False))

    gate1_pass = gate_df[(gate_df.gate == "Gate 1") & (gate_df.metric == "recall@5")]
    gate1_ok = (not gate1_pass.empty) and bool(
        gate1_pass.iloc[0]["ci_excludes_zero"] and gate1_pass.iloc[0]["direction"] == "A>B")

    gate2_rows = gate_df[gate_df.gate == "Gate 2"]
    gate2_ok = (not gate2_rows.empty) and bool(
        (gate2_rows["ci_excludes_zero"] & (gate2_rows["direction"] == "A>B")).all())

    print("\n" + "-" * 78)
    print(f"Gate 1 (BiomedCLIP > random, macro Recall@5, CI excludes 0): "
          f"{'PASS' if gate1_ok else 'FAIL / INCONCLUSIVE'}")
    print(f"Gate 2 (BiomedCLIP > clip_generic, macro Recall@5 AND nDCG@10, CI excludes 0): "
          f"{'PASS' if gate2_ok else 'FAIL / INCONCLUSIVE'}")
    print("Gate 3 (wins concentrate on real findings, not just Normal/Other) "
          "must be checked manually against encoder_comparison_perclass.csv")
    print("-" * 78)

    # ---- Gate 3 support: flag per-class table rows for real findings -------
    perclass_path = out_dir / "encoder_comparison_perclass.csv"
    if perclass_path.exists():
        pc = pd.read_csv(perclass_path)
        pc["is_real_finding"] = ~pc["primary_label"].isin(NON_FINDING_CLASSES | {"Normal"})
        real = pc[pc["is_real_finding"] & pc["encoder"].isin(["biomedclip", "clip_generic", "random"])]
        pivot = real.pivot_table(index="primary_label", columns="encoder", values="recall@5")
        if "biomedclip" in pivot.columns:
            print("\nGate 3 support — macro Recall@5 on real (non-Normal, non-grab-bag) classes:")
            print(pivot.round(3).to_string())
            if "random" in pivot.columns:
                wins = (pivot["biomedclip"] > pivot["random"]).sum()
                print(f"BiomedCLIP beats random on {wins}/{len(pivot)} real-finding classes "
                      f"(point estimates; small per-class n, read qualitatively).")

    # ---- Manual clinical relevance sample -----------------------------------
    if "biomedclip" in data:
        idx = pd.read_csv(metadata_dir / "study_index.csv")
        splits = pd.read_csv(splits_dir / "splits.csv")
        study_df = idx.merge(splits, on="uid")
        reports_path_candidates = [Path(cfg["paths"]["reports_csv"])]
        text_lookup = None
        for rp in reports_path_candidates:
            if rp.exists():
                rep = pd.read_csv(rp)[["uid", "findings", "impression"]]
                text_lookup = rep.set_index("uid")
                break

        val_pq = data["biomedclip"]
        n_classes = val_pq["primary_label"].nunique()
        per_class_n = max(1, args.manual_sample_n // n_classes)
        # explicit per-group loop -- does NOT rely on groupby().apply() retaining
        # the grouping column, which pandas >=2.2 drops by default when the
        # applied function returns the group frame unchanged (silent breakage
        # otherwise: primary_label disappears from the result on pandas 3.x).
        parts = []
        for cls, g in val_pq.groupby("primary_label"):
            parts.append(g.sample(min(len(g), per_class_n), random_state=args.seed))
        sample = pd.concat(parts, ignore_index=True).head(args.manual_sample_n)

        review_rows = []
        for _, r in sample.iterrows():
            row = {"query_uid": int(r["uid"]), "query_primary_label": r["primary_label"],
                   "recall@5": r["recall@5"], "ndcg@10": r["ndcg@10"]}
            if text_lookup is not None and int(r["uid"]) in text_lookup.index:
                row["query_findings"] = text_lookup.loc[int(r["uid"]), "findings"]
            row["manual_relevance_0_1_2"] = ""  # fill in by hand: 0=irrelevant,1=partial,2=clearly relevant
            row["notes"] = ""
            review_rows.append(row)

        review_df = pd.DataFrame(review_rows)
        review_df.to_csv(out_dir / "manual_review_sample.csv", index=False)
        print(f"\nWrote {out_dir/'manual_review_sample.csv'} "
              f"({len(review_df)} queries) for the qualitative relevance check.")
        print("Open it, look up each query's top-5 BiomedCLIP neighbors (or extend this "
              "script to pull them from the cached embeddings), and rate 0/1/2 by eye.")

    print("\nDone. gate_decision_table.csv is the evidence to cite in the thesis — "
          "not the raw point-estimate table from run_encoder_eval.py.")


if __name__ == "__main__":
    main()
