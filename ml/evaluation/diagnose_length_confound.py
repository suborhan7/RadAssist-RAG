"""
ml/evaluation/diagnose_length_confound.py
====================================================================
Phase 21 post-hoc diagnostic, run 2026-09-19 AFTER the pre-registered
n=100 result. Additional reporting only: it does not replace, adjust,
or re-weight any pre-registered number, and it introduces no new
metric.

THE QUESTION. Arm C beats Arm B on ROUGE-L and METEOR but not on
CheXbert macro-F1. Both ROUGE-L F-measure and METEOR are recall-aware,
and METEOR weights recall an order of magnitude above precision
(alpha=0.9). A system that simply emits more text can gain on both
without becoming more clinically correct. This measures whether that
is what happened.

WHAT IS REPORTED, and why each is defensible without inventing a metric:

1. Token counts (mean/median) of generated and reference text, per arm
   and field, plus the generated/reference length ratio. Whitespace
   tokenization, stated plainly -- this is a description of the text,
   not a score.

2. ROUGE-L PRECISION and RECALL reported separately, instead of only
   the F-measure the harness stored. These are components the same
   scorer already computes on the same texts with the same settings
   (rougeL, use_stemmer=True); reporting them separately is
   decomposition, not a new measurement. Verbosity inflates recall and
   deflates precision, so the two components moving in opposite
   directions is the signature being looked for.

3. The same paired bootstrap as the pre-registered contrasts (2000
   resamples, seed 42, percentile CI, one draw applied to both arms) so
   the decomposed numbers are read on the same footing as the numbers
   they decompose.

METEOR is deliberately NOT decomposed: nltk's implementation returns a
single aligned score with its own internal alpha/beta/gamma weighting
and exposes no precision/recall components, so splitting it would mean
reimplementing it -- which is exactly the "invent a new metric" move
this diagnostic avoids. Its length ratio is reported instead.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from rouge_score import rouge_scorer

ARMS = ("full", "labels_only", "empty")
FIELDS = ("findings", "impression")
N_BOOT = 2000
SEED = 42


def load_arm_texts(data_root: Path, arm: str) -> dict[str, dict]:
    text_dir = data_root / f"ml/outputs/evaluation/generation_arm_{arm}/generated_text"
    out = {}
    for p in sorted(text_dir.glob("*.json")):
        out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return out


def ntok(s: str) -> int:
    return len(str(s).split())


def paired_ci(diff: np.ndarray):
    n = len(diff)
    rng = np.random.default_rng(SEED)
    boot = np.empty(N_BOOT)
    for b in range(N_BOOT):
        boot[b] = diff[rng.integers(0, n, n)].mean()
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return float(lo), float(hi), bool(lo > 0 or hi < 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=".")
    args = ap.parse_args()
    data_root = Path(args.data_root)

    texts = {arm: load_arm_texts(data_root, arm) for arm in ARMS}
    uids = sorted(set.intersection(*(set(t) for t in texts.values())))
    print(f"[diagnose_length_confound] shared cases: {len(uids)}")

    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)

    # ---------- 1. token counts ----------
    print()
    print("=" * 92)
    print("TOKEN COUNTS (whitespace tokens)")
    print("=" * 92)
    print(f"{'arm':12} {'field':11} {'gen mean':>9} {'gen med':>8} {'ref mean':>9} {'ref med':>8} {'gen/ref mean':>13}")
    print("-" * 92)
    length_rows = []
    for field in FIELDS:
        ref_counts = np.array([ntok(texts[ARMS[0]][u]["ground_truth"][field]) for u in uids])
        for arm in ARMS:
            gen_counts = np.array([ntok(texts[arm][u]["generated"][field]) for u in uids])
            ratio = float(gen_counts.mean() / ref_counts.mean())
            print(f"{arm:12} {field:11} {gen_counts.mean():9.1f} {np.median(gen_counts):8.1f} "
                  f"{ref_counts.mean():9.1f} {np.median(ref_counts):8.1f} {ratio:13.2f}")
            length_rows.append({
                "arm": arm, "field": field,
                "gen_mean_tokens": float(gen_counts.mean()),
                "gen_median_tokens": float(np.median(gen_counts)),
                "ref_mean_tokens": float(ref_counts.mean()),
                "ref_median_tokens": float(np.median(ref_counts)),
                "gen_over_ref_mean": ratio,
            })
        print("-" * 92)

    # ---------- 2. ROUGE-L decomposed ----------
    comp = {}
    for arm in ARMS:
        for field in FIELDS:
            p, r, f = [], [], []
            for u in uids:
                s = scorer.score(texts[arm][u]["ground_truth"][field],
                                 texts[arm][u]["generated"][field])["rougeL"]
                p.append(s.precision); r.append(s.recall); f.append(s.fmeasure)
            comp[(arm, field)] = {
                "precision": np.array(p), "recall": np.array(r), "fmeasure": np.array(f),
            }

    print()
    print("=" * 92)
    print("ROUGE-L DECOMPOSED (same scorer, same texts, same settings)")
    print("=" * 92)
    print(f"{'arm':12} {'field':11} {'precision':>10} {'recall':>10} {'F-measure':>10}")
    print("-" * 92)
    for field in FIELDS:
        for arm in ARMS:
            c = comp[(arm, field)]
            print(f"{arm:12} {field:11} {c['precision'].mean():10.4f} "
                  f"{c['recall'].mean():10.4f} {c['fmeasure'].mean():10.4f}")
        print("-" * 92)

    # ---------- 3. paired C-B and C-A on each component ----------
    print()
    print("=" * 92)
    print("PAIRED CONTRASTS ON EACH COMPONENT (2000 resamples, seed 42) -- additional reporting")
    print("=" * 92)
    print(f"{'contrast':22} {'field':11} {'component':10} {'diff':>9} {'95% CI':>22} {'excl 0':>7}")
    print("-" * 92)
    contrast_rows = []
    for lower in ("labels_only", "empty"):
        for field in FIELDS:
            for component in ("precision", "recall", "fmeasure"):
                d = comp[("full", field)][component] - comp[(lower, field)][component]
                lo, hi, excl = paired_ci(d)
                print(f"{'full_minus_' + lower:22} {field:11} {component:10} "
                      f"{d.mean():9.4f} [{lo:9.4f},{hi:9.4f}] {str(excl):>7}")
                contrast_rows.append({
                    "contrast": f"full_minus_{lower}", "field": field, "component": component,
                    "mean_difference": float(d.mean()), "ci_lower": lo, "ci_upper": hi,
                    "excludes_zero": excl,
                })
        print("-" * 92)

    out_dir = data_root / "ml/outputs/evaluation"
    pd.DataFrame(length_rows).to_csv(out_dir / "phase21_length_diagnostic.csv", index=False)
    pd.DataFrame(contrast_rows).to_csv(out_dir / "phase21_rougeL_components.csv", index=False)
    print(f"\n[diagnose_length_confound] wrote phase21_length_diagnostic.csv and "
          f"phase21_rougeL_components.csv")


if __name__ == "__main__":
    main()
