"""
ml/evaluation/diagnose_chexbert_components.py
====================================================================
Phase 21 post-hoc diagnostic (§6.7 constraints apply: EXPLORATORY,
never merged into a paragraph with pre-registered analysis).

THE QUESTION. At n=477 the C-B CheXbert macro-F1 contrast on
`findings` newly clears (+0.0587, CI [0.0165, 0.0978]). Arm C writes
3.1x Arm B's findings length, and CheXbert extracts conditions from
text: a longer report mentions more conditions, which can raise recall
and therefore F1 without the report being more correct. The ROUGE-L
decomposition already showed exactly that pattern on this field --
findings recall +0.2207 clearing, findings precision -0.0058 not
clearing.

This applies the identical decomposition to CheXbert. macro-precision
and macro-recall are the components the F1 is already built from:
per-condition tp/(tp+fp) and tp/(tp+fn), averaged over the same 14
conditions with the same denominator. Reporting them separately is
decomposition, not a new metric -- the same standard §6.9 used to
decline restricted macro-F1, which WOULD have been a transformation.

PAIRING is identical to contrast_arms.py: one index draw per
iteration applied to both arms, 2000 resamples, seed 42, percentile
CI. macro-P and macro-R are corpus-level like macro-F1, so both are
recomputed per resample rather than averaged from per-case values.

A recall-only gain with precision failing to clear would mean the one
contrast that newly clears at n=477 is length-driven, exactly as the
findings ROUGE-L gain was.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_chexbert import CONDITIONS  # noqa: E402

N_BOOT = 2000
SEED = 42


def macro_p_r_f(gen: np.ndarray, ref: np.ndarray) -> tuple[float, float, float]:
    """Macro precision, recall and F1 over the same 14 conditions.

    Mirrors score_chexbert.f1_micro_macro's per-label arithmetic exactly --
    same tp/fp/fn definition, same zero-denominator convention, same
    14-condition denominator -- and simply stops before collapsing
    precision and recall into F1.
    """
    tp = ((gen == 1) & (ref == 1)).sum(axis=0).astype(np.float64)
    fp = ((gen == 1) & (ref == 0)).sum(axis=0).astype(np.float64)
    fn = ((gen == 0) & (ref == 1)).sum(axis=0).astype(np.float64)

    prec = np.where((tp + fp) > 0, tp / np.maximum(tp + fp, 1), 0.0)
    rec = np.where((tp + fn) > 0, tp / np.maximum(tp + fn, 1), 0.0)
    f1 = np.where((prec + rec) > 0, 2 * prec * rec / np.maximum(prec + rec, 1e-12), 0.0)
    return float(prec.mean()), float(rec.mean()), float(f1.mean())


def load_labels(data_root: Path, arm: str, field: str, tag: str, uids: list[str]):
    path = (data_root / f"ml/outputs/evaluation/generation_arm_{arm}{tag}"
            / f"tier3_chexbert_{field}_labels.csv")
    df = pd.read_csv(path, dtype={"study_uid": str}).set_index("study_uid").loc[uids]
    gen = df[[f"gen_{c}" for c in CONDITIONS]].to_numpy(dtype=np.int64)
    ref = df[[f"ref_{c}" for c in CONDITIONS]].to_numpy(dtype=np.int64)
    return gen, ref


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=".")
    ap.add_argument("--upper", default="full")
    ap.add_argument("--lower", default="labels_only")
    ap.add_argument("--tag", default=None)
    args = ap.parse_args()

    data_root = Path(args.data_root)
    tag = "" if args.tag is None else f"_{args.tag}"

    sets = []
    for arm in (args.upper, args.lower):
        df = pd.read_csv(
            data_root / f"ml/outputs/evaluation/generation_arm_{arm}{tag}/per_case_results.csv",
            dtype={"study_uid": str})
        sets.append(set(df.loc[df["status"] == "completed", "study_uid"]))
    uids = sorted(set.intersection(*sets))
    print(f"[diagnose_chexbert_components] shared completed cases: {len(uids)}")

    rows = []
    print()
    print("=" * 94)
    print(f"CheXbert macro components, {args.upper} vs {args.lower}, n={len(uids)}  -- EXPLORATORY")
    print("=" * 94)
    print(f"{'field':11} {'component':10} {'upper':>8} {'lower':>8} {'diff':>9} {'95% CI':>22} {'excl 0':>7}")
    print("-" * 94)

    for field in ("findings", "impression"):
        gen_u, ref_u = load_labels(data_root, args.upper, field, tag, uids)
        gen_l, ref_l = load_labels(data_root, args.lower, field, tag, uids)
        assert np.array_equal(ref_u, ref_l), "reference label matrices differ between arms"
        ref = ref_u
        n = len(uids)

        pu, ru, fu = macro_p_r_f(gen_u, ref)
        pl, rl, fl = macro_p_r_f(gen_l, ref)

        rng = np.random.default_rng(SEED)
        boot = {"precision": np.empty(N_BOOT), "recall": np.empty(N_BOOT), "f1": np.empty(N_BOOT)}
        for b in range(N_BOOT):
            idx = rng.integers(0, n, size=n)  # ONE draw, both arms
            a_p, a_r, a_f = macro_p_r_f(gen_u[idx], ref[idx])
            b_p, b_r, b_f = macro_p_r_f(gen_l[idx], ref[idx])
            boot["precision"][b] = a_p - b_p
            boot["recall"][b] = a_r - b_r
            boot["f1"][b] = a_f - b_f

        for comp, up, lo_val in (("precision", pu, pl), ("recall", ru, rl), ("f1", fu, fl)):
            lo, hi = np.percentile(boot[comp], [2.5, 97.5])
            excl = bool(lo > 0 or hi < 0)
            print(f"{field:11} {comp:10} {up:8.4f} {lo_val:8.4f} {up - lo_val:9.4f} "
                  f"[{lo:9.4f},{hi:9.4f}] {str(excl):>7}")
            rows.append({
                "field": field, "component": comp,
                f"macro_{comp}_upper": up, f"macro_{comp}_lower": lo_val,
                "difference": up - lo_val, "ci_lower": float(lo), "ci_upper": float(hi),
                "excludes_zero": excl,
            })
        print("-" * 94)

    out = data_root / f"ml/outputs/evaluation/phase21_chexbert_components{tag}.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\n[diagnose_chexbert_components] wrote {out}")


if __name__ == "__main__":
    main()
