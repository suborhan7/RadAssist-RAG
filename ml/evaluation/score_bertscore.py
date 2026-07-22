"""
ml/evaluation/score_bertscore.py
====================================================================
Phase 20 Tier 2: BERTScore (P/R/F1) on the same findings/impression
pairs Tier 1 already scored. Deliberately standalone and NOT wired into
run_generation_eval.py -- it reads that script's saved per-case
generated text (Decision 10, `generated_text/{study_uid}.json`) rather
than driving the API again, and it MUST be run from the isolated
`ml/evaluation/.venv-bertscore/` environment (torch==2.6.0), never the
main project .venv, per Step 3's finding: no safetensors mirror exists
for the standard biomedical BERT checkpoints, so loading one under
transformers' current CVE-2025-32434 check requires torch>=2.6, which
would otherwise force an unwanted production torch upgrade (BiomedCLIP
depends on the main .venv's torch==2.5.1). See requirements-bertscore.txt
for the exact working dependency set and the tokenizer-overflow bug that
also had to be pinned around.

Model: microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext
(already cached locally from the Step 3 smoke test). Not present in
bert_score's own tuned `model2layers` table (that table only covers
general-domain checkpoints), so there is no benchmarked "best" layer
for it specifically. Its config confirms a standard BERT-base
architecture (12 layers, 768 hidden) -- identical depth to
"bert-base-uncased", whose own tuned choice is layer 9. Using layer 9
here is a reasoned choice based on matching architecture, not an
arbitrary pick, but it is NOT independently re-validated for the
biomedical domain the way the general-domain table's numbers were.
No idf/baseline rescaling is applied (no baseline file exists for a
custom, unregistered model_type) -- these are raw cosine-similarity
P/R/F1 scores, not baseline-rescaled ones; do not compare them directly
against rescaled scores from other papers without accounting for that.

Run with the isolated venv's interpreter, e.g.:
    ml/evaluation/.venv-bertscore/Scripts/python.exe ml/evaluation/score_bertscore.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from bert_score import score as bertscore_score

GROUND_TRUTH_FIELDS = ("findings", "impression")
MODEL_TYPE = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext"
NUM_LAYERS = 9  # matches bert-base-uncased's tuned layer -- see docstring
MISMATCH_SEED = 42  # same seed used everywhere else in this phase, for consistency


def _derangement(n: int, seed: int) -> np.ndarray:
    """A fixed random permutation of range(n) with no fixed points (perm[i] != i
    for all i) -- guarantees every 'mismatched' pair is genuinely a different
    case's reference, not an accidental self-pairing that would leak the real
    signal into the random baseline."""
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    fixed = np.where(perm == np.arange(n))[0]
    for i in fixed:
        j = (i + 1) % n
        perm[i], perm[j] = perm[j], perm[i]
    assert not np.any(perm == np.arange(n)), "derangement failed to remove all fixed points"
    return perm


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=".")
    args = ap.parse_args()

    data_root = Path(args.data_root)
    out_dir = data_root / "ml/outputs/evaluation/generation"
    text_dir = out_dir / "generated_text"

    case_files = sorted(text_dir.glob("*.json"))
    print(f"[score_bertscore] {len(case_files)} saved generated-text cases found in {text_dir}")

    study_uids = []
    hyps = {f: [] for f in GROUND_TRUTH_FIELDS}
    refs = {f: [] for f in GROUND_TRUTH_FIELDS}
    for path in case_files:
        data = json.loads(path.read_text())
        study_uids.append(path.stem)
        for f in GROUND_TRUTH_FIELDS:
            hyps[f].append(data["generated"][f])
            refs[f].append(data["ground_truth"][f])

    per_field_scores = {}
    for f in GROUND_TRUTH_FIELDS:
        print(f"[score_bertscore] scoring field '{f}' ({len(hyps[f])} pairs) with {MODEL_TYPE} (layer {NUM_LAYERS})...")
        precision, recall, f1 = bertscore_score(
            hyps[f], refs[f],
            model_type=MODEL_TYPE, num_layers=NUM_LAYERS,
            rescale_with_baseline=False, verbose=False,
        )
        per_field_scores[f] = (precision.tolist(), recall.tolist(), f1.tolist())

    rows = []
    for i, study_uid in enumerate(study_uids):
        row = {"study_uid": study_uid}
        for f in GROUND_TRUTH_FIELDS:
            precision, recall, f1 = per_field_scores[f]
            row[f"{f}_bertscore_p"] = precision[i]
            row[f"{f}_bertscore_r"] = recall[i]
            row[f"{f}_bertscore_f1"] = f1[i]
        rows.append(row)

    results_df = pd.DataFrame(rows)
    out_path = out_dir / "tier2_bertscore_results.csv"
    results_df.to_csv(out_path, index=False)
    print(f"[score_bertscore] wrote {out_path}")

    print()
    print(f"[score_bertscore] summary (n={len(results_df)}):")
    for f in GROUND_TRUTH_FIELDS:
        for metric in ("p", "r", "f1"):
            col = f"{f}_bertscore_{metric}"
            print(f"  {col:24s} mean={results_df[col].mean():.4f}  std={results_df[col].std():.4f}")

    # Mismatched-pairs random baseline -- same spirit as Phase 0's "beats
    # random" gate. Each hypothesis is scored against a DIFFERENT case's
    # real reference (a fixed derangement, seed 42), so a genuinely
    # unrelated report pair's BERTScore is known before treating 0.84 as
    # meaningful. Uses the exact same model/layer/rescale settings as the
    # real scoring above, so the only thing that differs is pairing.
    print()
    print("[score_bertscore] computing mismatched-pairs random baseline (derangement, seed=42)...")
    baseline_rows = []
    baseline_summary = {}
    n = len(study_uids)
    perm = _derangement(n, MISMATCH_SEED)
    for f in GROUND_TRUTH_FIELDS:
        mismatched_refs = [refs[f][j] for j in perm]
        print(f"[score_bertscore] scoring mismatched '{f}' baseline ({n} pairs)...")
        precision, recall, f1 = bertscore_score(
            hyps[f], mismatched_refs,
            model_type=MODEL_TYPE, num_layers=NUM_LAYERS,
            rescale_with_baseline=False, verbose=False,
        )
        baseline_summary[f] = {
            "p_mean": float(precision.mean()), "r_mean": float(recall.mean()), "f1_mean": float(f1.mean()),
        }
        for i, study_uid in enumerate(study_uids):
            baseline_rows.append({
                "study_uid": study_uid, "field": f,
                "mismatched_with_study_uid": study_uids[perm[i]],
                "bertscore_p": float(precision[i]), "bertscore_r": float(recall[i]), "bertscore_f1": float(f1[i]),
            })

    baseline_df = pd.DataFrame(baseline_rows)
    baseline_path = out_dir / "tier2_bertscore_random_baseline.csv"
    baseline_df.to_csv(baseline_path, index=False)
    print(f"[score_bertscore] wrote {baseline_path}")

    print()
    print("[score_bertscore] real vs. mismatched-pairs baseline (F1):")
    for f in GROUND_TRUTH_FIELDS:
        real_f1 = results_df[f"{f}_bertscore_f1"].mean()
        base_f1 = baseline_summary[f]["f1_mean"]
        print(f"  {f:12s} real={real_f1:.4f}  random_baseline={base_f1:.4f}  gap={real_f1 - base_f1:+.4f}")


if __name__ == "__main__":
    main()
