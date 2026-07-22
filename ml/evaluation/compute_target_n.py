"""
ml/evaluation/compute_target_n.py
====================================================================
Ad hoc precision-target calculation for Phase 20 Step 7 follow-up:
given the 98 real completed cases' observed bootstrap CI widths, how
many total completed cases would be needed to bring each impression
metric's 95% CI width down to ~20% of its mean (the tightness findings
already has)?

Method: the percentile-bootstrap CI for a sample mean has width driven
by the standard error of the mean, which scales as 1/sqrt(n) regardless
of the underlying per-case metric's distribution shape (CLT applies to
the sampling distribution of the mean itself). This is verified
empirically below (not assumed) by recomputing the bootstrap at two
smaller real subsample sizes drawn from the same 98 cases and checking
the width actually follows width(n) ~= width(98) * sqrt(98/n) before
using that relationship to extrapolate upward.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

def bootstrap_width(values: np.ndarray, n_boot: int, rng: np.random.Generator, alpha: float = 0.05) -> float:
    n = len(values)
    boot_means = np.empty(n_boot, dtype=np.float64)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boot_means[b] = values[idx].mean()
    lo = np.percentile(boot_means, 100 * alpha / 2)
    hi = np.percentile(boot_means, 100 * (1 - alpha / 2))
    return float(hi - lo)

data_root = Path(".")
df = pd.read_csv(data_root / "ml/outputs/evaluation/generation/per_case_results.csv")
completed = df[df["status"] == "completed"].copy()
n_full = len(completed)

impression_metrics = ["impression_bleu", "impression_rouge_l", "impression_meteor"]
findings_metrics = ["findings_bleu", "findings_rouge_l", "findings_meteor"]

print(f"[compute_target_n] {n_full} completed cases (source: per_case_results.csv)")
print()

# --- Step A: empirically verify the 1/sqrt(n) width-scaling assumption ---
print("[compute_target_n] Verifying width ~ 1/sqrt(n) scaling on real subsamples (not assumed):")
rng_check = np.random.default_rng(42)
for col in impression_metrics:
    full_vals = completed[col].dropna().to_numpy()
    w_full = bootstrap_width(full_vals, 2000, np.random.default_rng(42))
    row = f"  {col:20s} width(n={n_full})={w_full:6.4f}"
    for sub_n in (70, 50):
        idx = rng_check.choice(n_full, size=sub_n, replace=False)
        sub_vals = full_vals[idx]
        w_sub = bootstrap_width(sub_vals, 2000, np.random.default_rng(42))
        predicted = w_full * np.sqrt(n_full / sub_n)
        row += f"  | width(n={sub_n})={w_sub:6.4f} (predicted from n={n_full}: {predicted:6.4f})"
    print(row)
print()

# --- Step B: compute mean + real bootstrap width per impression metric, then target N ---
print(f"[compute_target_n] Target: 95% CI width <= 20% of mean (findings' real tightness)")
print()
results = []
for col in impression_metrics:
    vals = completed[col].dropna().to_numpy()
    mean = float(vals.mean())
    width_98 = bootstrap_width(vals, 2000, np.random.default_rng(42))
    rel_width_98 = width_98 / mean
    target_width = 0.20 * mean
    n_required = n_full * (width_98 / target_width) ** 2
    results.append((col, mean, width_98, rel_width_98, n_required))
    print(f"  {col:20s} mean={mean:7.4f}  width(n={n_full})={width_98:7.4f} ({rel_width_98*100:5.1f}% of mean)"
          f"  -> N required for 20%: {n_required:8.1f}")

print()
max_n = max(r[4] for r in results)
binding = [r[0] for r in results if r[4] == max_n][0]
print(f"[compute_target_n] Binding constraint: {binding} requires the most completed cases ({max_n:.0f}).")
print(f"[compute_target_n] Eligible pool ceiling: 477 total eligible cases.")

# additional cases needed, accounting for the observed 2% failure rate (98/100 completed)
failure_rate = 1 - (98 / 100)
for col, mean, width_98, rel_width_98, n_required in results:
    additional_completed = max(0.0, n_required - n_full)
    additional_sampled = additional_completed / (1 - failure_rate)
    total_sampled_from_pool = 100 + additional_sampled
    print(f"  {col:20s} additional completed needed: {additional_completed:7.1f}"
          f"  -> additional cases to sample (at 2% failure rate): {additional_sampled:7.1f}"
          f"  -> total sampled from 477-pool: {total_sampled_from_pool:7.1f}")
