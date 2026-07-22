"""
ml/evaluation/bootstrap_tier2_ci.py
====================================================================
Bootstrap CIs on Tier 2 (BERTScore) scores, reusing the exact same
configuration as Tier 1 (bootstrap_tier1_ci.py) and Phase 0's
analyze_results.py before that -- 2,000 resamples, seed 42, 95% CI via
plain percentile method, plain (non-stratified) case-level resampling --
for internal consistency within Phase 20, not recomputed differently
per tier.
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
    results_path = data_root / "ml/outputs/evaluation/generation/tier2_bertscore_results.csv"
    df = pd.read_csv(results_path)

    print(f"[bootstrap_tier2_ci] {len(df)} scored cases")
    print(f"[bootstrap_tier2_ci] n_boot={args.n_boot}, seed={args.seed}, 95% CI, plain (non-stratified) case-level resampling")
    print()

    rng = np.random.default_rng(args.seed)
    metric_cols = [c for c in df.columns if c.startswith(("findings_bertscore", "impression_bertscore"))]

    rows = []
    for col in metric_cols:
        values = df[col].dropna().to_numpy()
        mean, lo, hi = bootstrap_mean_ci(values, args.n_boot, rng, alpha=0.05)
        width = hi - lo
        rows.append({"metric": col, "n": len(values), "mean": mean, "ci_lower": lo, "ci_upper": hi, "ci_width": width})
        print(f"{col:24s} n={len(values):3d}  mean={mean:7.4f}  95% CI=[{lo:7.4f}, {hi:7.4f}]  width={width:6.4f}")

    summary = pd.DataFrame(rows)
    out_path = data_root / "ml/outputs/evaluation/generation/tier2_bootstrap_summary.csv"
    summary.to_csv(out_path, index=False)
    print()
    print(f"[bootstrap_tier2_ci] wrote {out_path}")


if __name__ == "__main__":
    main()
