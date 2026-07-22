"""
ml/evaluation/bootstrap_tier1_ci.py
====================================================================
Phase 20 Step 7: bootstrap CIs on Tier 1 metrics, reusing Phase 0's
exact confirmed configuration (analyze_results.py) -- 2,000 resamples,
seed 42, 95% CI via plain percentile method. Deliberately PLAIN
case-level resampling, not class-stratified: Phase 0 stratified by
primary_label specifically to compare retrieval quality ACROSS encoders
per class; Phase 20 evaluates one system's generation quality against
ground truth with no per-class comparison being made, and there is no
existing per-case label scheme for these 477 cases to stratify by
without inventing one. A per-class breakdown remains a valid follow-up
on the raw per-case CSV if it turns out to be interesting later -- not
something the core bootstrap needs to build in now.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def bootstrap_mean_ci(values: np.ndarray, n_boot: int, rng: np.random.Generator, alpha: float = 0.05):
    n = len(values)
    boot_means = np.empty(n_boot, dtype=np.float64)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boot_means[b] = values[idx].mean()
    lo = float(np.percentile(boot_means, 100 * alpha / 2))
    hi = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return float(values.mean()), lo, hi


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=".")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    data_root = Path(args.data_root)
    results_path = data_root / "ml/outputs/evaluation/generation/per_case_results.csv"
    df = pd.read_csv(results_path)

    completed = df[df["status"] == "completed"].copy()
    print(f"[bootstrap_tier1_ci] {len(completed)} completed cases out of {len(df)} total")
    print(f"[bootstrap_tier1_ci] n_boot={args.n_boot}, seed={args.seed}, 95% CI, plain (non-stratified) case-level resampling")
    print()

    rng = np.random.default_rng(args.seed)
    metric_cols = [c for c in df.columns if c.endswith(("_bleu", "_rouge_l", "_meteor"))]

    rows = []
    for col in metric_cols:
        values = completed[col].dropna().to_numpy()
        mean, lo, hi = bootstrap_mean_ci(values, args.n_boot, rng, alpha=0.05)
        width = hi - lo
        rows.append({"metric": col, "n": len(values), "mean": mean, "ci_lower": lo, "ci_upper": hi, "ci_width": width})
        print(f"{col:20s} n={len(values):3d}  mean={mean:7.3f}  95% CI=[{lo:7.3f}, {hi:7.3f}]  width={width:6.3f}")

    summary = pd.DataFrame(rows)
    out_path = data_root / "ml/outputs/evaluation/generation/tier1_bootstrap_summary.csv"
    summary.to_csv(out_path, index=False)
    print()
    print(f"[bootstrap_tier1_ci] wrote {out_path}")


if __name__ == "__main__":
    main()
