"""
ml/evaluation/contrast_arms.py
====================================================================
Phase 21 §6.3: the pre-registered between-arm contrast family.

Twelve intervals: {CheXbert macro-F1, ROUGE-L, METEOR} x {C-B, C-A}
x {findings, impression}. §6.2's table marks exactly these three
metrics for contrasts; BLEU and BERTScore are excluded on documented,
pre-existing negative findings about the METRICS, established before
these arms existed and without knowledge of this phase's outcome.

PRIMARY ENDPOINT (§6.3, fixed before any run):
    CheXbert macro-F1 on `impression`, Arm C (full) minus Arm B
    (labels_only), paired bootstrap 95% CI excluding zero in the
    positive direction.
Every other interval is secondary and exploratory, reported as a
family -- with twelve intervals, at least one crossing zero by chance
is likely, which is exactly what designating a primary endpoint in
advance exists to control.

PAIRING. The same resampled case indices are applied to BOTH arms
within each bootstrap iteration. Resampling the arms independently
would throw away the pairing the shared case set exists to provide and
would inflate the interval. macro-F1 is a corpus-level statistic, so it
is RECOMPUTED per resample from that resample's label matrices rather
than averaged from per-case values -- a per-case macro-F1 does not
exist.

f1_micro_macro is IMPORTED from score_chexbert rather than
reimplemented, so the contrast cannot silently drift from the metric
definition the standalone scores were computed with.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_chexbert import CONDITIONS, f1_micro_macro  # noqa: E402

FIELDS = ("findings", "impression")
N_BOOT = 2000
SEED = 42
ALPHA = 0.05


TAG = ""  # set from --tag in main(); see run_generation_eval.py's --tag


def _arm_dir(data_root: Path, arm: str) -> Path:
    return data_root / f"ml/outputs/evaluation/generation_arm_{arm}{TAG}"


def _percentile_ci(boot: np.ndarray) -> tuple[float, float]:
    lo, hi = np.percentile(boot, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])
    return float(lo), float(hi)


def shared_completed_uids(data_root: Path, arms: list[str]) -> list[str]:
    sets = []
    for arm in arms:
        df = pd.read_csv(_arm_dir(data_root, arm) / "per_case_results.csv", dtype={"study_uid": str})
        sets.append(set(df.loc[df["status"] == "completed", "study_uid"]))
    return sorted(set.intersection(*sets))


def tier1_paired(data_root: Path, upper: str, lower: str, uids: list[str], metric: str, field: str):
    """Per-case paired difference, bootstrapped on the mean."""
    col = f"{field}_{metric}"
    vals = {}
    for arm in (upper, lower):
        df = pd.read_csv(_arm_dir(data_root, arm) / "per_case_results.csv", dtype={"study_uid": str})
        df = df.set_index("study_uid").loc[uids]
        vals[arm] = df[col].to_numpy(dtype=np.float64)

    diff = vals[upper] - vals[lower]
    n = len(diff)
    rng = np.random.default_rng(SEED)
    boot = np.empty(N_BOOT, dtype=np.float64)
    for b in range(N_BOOT):
        idx = rng.integers(0, n, size=n)
        boot[b] = diff[idx].mean()
    lo, hi = _percentile_ci(boot)
    return {
        "n": n,
        "mean_upper": float(vals[upper].mean()),
        "mean_lower": float(vals[lower].mean()),
        "mean_difference": float(diff.mean()),
        "ci_95": [lo, hi],
        "excludes_zero": bool(lo > 0 or hi < 0),
    }


def _load_label_matrix(data_root: Path, arm: str, field: str, uids: list[str]):
    path = _arm_dir(data_root, arm) / f"tier3_chexbert_{field}_labels.csv"
    if not path.is_file():
        raise SystemExit(f"[contrast_arms] missing Tier 3 labels for arm {arm}: {path}")
    df = pd.read_csv(path, dtype={"study_uid": str}).set_index("study_uid").loc[uids]
    gen = df[[f"gen_{c}" for c in CONDITIONS]].to_numpy(dtype=np.int64)
    ref = df[[f"ref_{c}" for c in CONDITIONS]].to_numpy(dtype=np.int64)
    return gen, ref


def tier3_paired(data_root: Path, upper: str, lower: str, uids: list[str], field: str):
    gen_u, ref_u = _load_label_matrix(data_root, upper, field, uids)
    gen_l, ref_l = _load_label_matrix(data_root, lower, field, uids)

    # The reference labels are CheXbert run over the SAME ground-truth text in
    # both arms, so they must match exactly. If they do not, the two arms were
    # scored against different references and no contrast between them means
    # anything -- fail rather than average over the discrepancy.
    if not np.array_equal(ref_u, ref_l):
        n_bad = int((ref_u != ref_l).any(axis=1).sum())
        raise SystemExit(
            f"[contrast_arms] ABORT: reference label matrices differ between "
            f"{upper} and {lower} on field {field} for {n_bad} case(s). "
            "The arms were scored against different ground truth."
        )

    ref = ref_u
    n = len(uids)
    point_u = f1_micro_macro(gen_u, ref)[1]
    point_l = f1_micro_macro(gen_l, ref)[1]

    rng = np.random.default_rng(SEED)
    boot = np.empty(N_BOOT, dtype=np.float64)
    for b in range(N_BOOT):
        idx = rng.integers(0, n, size=n)  # ONE draw, applied to both arms
        boot[b] = f1_micro_macro(gen_u[idx], ref[idx])[1] - f1_micro_macro(gen_l[idx], ref[idx])[1]
    lo, hi = _percentile_ci(boot)
    return {
        "n": n,
        "macro_f1_upper": float(point_u),
        "macro_f1_lower": float(point_l),
        "mean_difference": float(point_u - point_l),
        "ci_95": [lo, hi],
        "excludes_zero": bool(lo > 0 or hi < 0),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=".")
    ap.add_argument("--upper", default="full")
    ap.add_argument("--lower", nargs="+", default=["labels_only", "empty"])
    ap.add_argument("--tag", default=None,
                    help="Output-directory suffix, matching run_generation_eval.py's --tag.")
    ap.add_argument("--skip-tier3", action="store_true",
                    help="Tier 1 contrasts only (for when Tier 3 labels are not yet computed).")
    args = ap.parse_args()

    global TAG
    TAG = "" if args.tag is None else f"_{args.tag}"
    data_root = Path(args.data_root)
    arms = [args.upper, *args.lower]
    uids = shared_completed_uids(data_root, arms)
    print(f"[contrast_arms] shared completed cases across {arms}: {len(uids)}")

    results: dict = {
        "primary_endpoint": {
            "definition": "CheXbert macro-F1 on impression, full minus labels_only, "
                          "paired bootstrap 95% CI excluding zero in the positive direction",
            "pre_registered": "Phase 21 §6.3, before any run",
        },
        "n_shared_cases": len(uids),
        "n_boot": N_BOOT,
        "seed": SEED,
        "contrasts": {},
    }

    rows = []
    for lower in args.lower:
        key = f"{args.upper}_minus_{lower}"
        results["contrasts"][key] = {}
        for field in FIELDS:
            for metric in ("rouge_l", "meteor"):
                r = tier1_paired(data_root, args.upper, lower, uids, metric, field)
                results["contrasts"][key][f"{field}_{metric}"] = r
                rows.append((key, field, metric, r))
            if not args.skip_tier3:
                r = tier3_paired(data_root, args.upper, lower, uids, field)
                results["contrasts"][key][f"{field}_chexbert_macro_f1"] = r
                rows.append((key, field, "chexbert_macro_f1", r))

    print()
    print("=" * 98)
    header = f"{'contrast':26} {'field':11} {'metric':20} {'diff':>9} {'95% CI':>22} {'excl 0':>7}"
    print(header)
    print("=" * 98)
    for key, field, metric, r in rows:
        lo, hi = r["ci_95"]
        is_primary = (
            metric == "chexbert_macro_f1"
            and field == "impression"
            and key == "full_minus_labels_only"
        )
        star = "  *PRIMARY" if is_primary else ""
        print(f"{key:26} {field:11} {metric:20} {r['mean_difference']:9.4f} "
              f"[{lo:9.4f},{hi:9.4f}] {str(r['excludes_zero']):>7}{star}")
    print("=" * 98)

    out = data_root / f"ml/outputs/evaluation/phase21_arm_contrasts{TAG}.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"[contrast_arms] wrote {out}")


if __name__ == "__main__":
    main()
