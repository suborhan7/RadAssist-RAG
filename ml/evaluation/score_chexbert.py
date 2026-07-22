"""
ml/evaluation/score_chexbert.py
====================================================================
Phase 20 Tier 3: CheXbert-based clinical-label F1 on the same 460
completed cases Tier 1/2 already scored. Isolated-venv only
(ml/evaluation/.venv-bertscore/) -- same environment Tier 2 uses,
reused here rather than building a third one (Steps 1-2 confirmed
CheXbert's checkpoint load is not gated by CVE-2025-32434 the way
PubMedBERT was, so the main env would also technically work, but this
keeps evaluation-only, heavyweight ML dependencies out of the
production backend's environment, consistent with why the isolated
venv exists at all).

Reconstructs the exact bert_labeler architecture and tokenization
logic from stanfordmlgroup/CheXbert's own source (fetched verbatim and
verified against a real structural load in Steps 1-2: 227/227 state-dict
keys matched exactly) rather than cloning the whole external repo.
CONDITIONS order and the raw-index -> class-name mapping
({0: Blank, 1: Positive, 2: Negative, 3: Uncertain}) are copied
verbatim from the real constants.py, not reconstructed from the paper's
prose -- getting either wrong would silently mislabel every condition.

Step 3 decisions (each with a stated reason, not a silent default):
  a. Uncertain -> collapsed into Positive for binary present/absent
     scoring. Checked against CheXbert's OWN paper's primary metric
     first (Smit et al. 2020 Sec 3.5's "weighted-F1" explicitly scores
     uncertain-extraction as its own weighted component, not excluded)
     -- found NOT to match, so this is a stated deviation, not a
     replication of the source paper's own metric. Instead it matches
     a real, verified precedent in the actual downstream-evaluation use
     case (comparing generated vs reference report text, not
     benchmarking a labeler against radiologists): Miura et al. 2021
     (NAACL, "Improving Factual Completeness and Consistency..."),
     whose own published eval_prf.py (github.com/ysmiura/ifcc) collapses
     uncertain -> positive by default (an --uncertain flag exists to
     treat it as its own class, off by default). Confirmed by reading
     that real file directly, not assumed.
  b. Findings and impression scored SEPARATELY, not concatenated --
     consistent with Tier 1/2's field-level breakdown throughout this
     phase, and avoids conflating two clinically distinct report
     sections into one label vector.
  c. Both micro-F1 (pooled across all 14 conditions x all cases) and
     macro-F1 (per-condition F1, averaged over 14 conditions) are
     computed and reported; macro is the headline, since 14 highly
     imbalanced conditions (e.g. Fracture/Pleural Other are rare) would
     otherwise let micro-F1 be dominated by a few common labels --
     the same class-imbalance concern Phase 0 raised for macro-over-
     micro in its own encoder-eval gate.

Step 4 (this phase's now-standard validity discipline after the Tier 2
BERTScore finding): a mismatched-pairs random baseline, reusing the
same fixed-derangement approach and seed (42) as Tier 2's, computed
before trusting the real F1 as meaningful.

Step 5: bootstrap CIs via Phase 0's exact configuration (2,000
resamples, seed 42, 95% CI, percentile method, plain case-level
resampling) -- for both real and baseline pairings, plus a paired
diff CI on real-minus-baseline macro-F1.

F1 edge case: a condition with zero true-or-predicted positives within
a given (possibly bootstrap-resampled) case set has an undefined
precision/recall; this script follows the common zero_division=0
convention (matching sklearn's default) rather than excluding the
label from that resample's macro average, for simplicity and
consistency across all resamples.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from transformers import BertModel, BertTokenizer

CHECKPOINT_PATH = (
    r"C:\Users\user2\.cache\huggingface\hub\models--StanfordAIMI--RRG_scorers"
    r"\snapshots\6646433b3ad83a10f6e141db76d0ece44312b236\chexbert.pth"
)

# Verbatim from stanfordmlgroup/CheXbert's src/constants.py -- order matters,
# it is the real order of the model's 14 linear heads.
CONDITIONS = [
    "Enlarged Cardiomediastinum", "Cardiomegaly", "Lung Opacity",
    "Lung Lesion", "Edema", "Consolidation", "Pneumonia", "Atelectasis",
    "Pneumothorax", "Pleural Effusion", "Pleural Other", "Fracture",
    "Support Devices", "No Finding",
]
CLASS_MAPPING = {0: "Blank", 1: "Positive", 2: "Negative", 3: "Uncertain"}
GROUND_TRUTH_FIELDS = ("findings", "impression")
MISMATCH_SEED = 42  # same seed used throughout this phase


class bert_labeler(nn.Module):
    """Verbatim reconstruction of stanfordmlgroup/CheXbert's src/models/bert_labeler.py,
    verified in Steps 1-2 to strict-load the real checkpoint with 227/227 keys matched."""

    def __init__(self, p=0.1):
        super(bert_labeler, self).__init__()
        self.bert = BertModel.from_pretrained("bert-base-uncased")
        self.dropout = nn.Dropout(p)
        hidden_size = self.bert.pooler.dense.in_features
        self.linear_heads = nn.ModuleList([nn.Linear(hidden_size, 4, bias=True) for _ in range(13)])
        self.linear_heads.append(nn.Linear(hidden_size, 2, bias=True))

    def forward(self, source_padded, attention_mask):
        final_hidden = self.bert(source_padded, attention_mask=attention_mask)[0]
        cls_hidden = final_hidden[:, 0, :].squeeze(dim=1)
        cls_hidden = self.dropout(cls_hidden)
        return [self.linear_heads[i](cls_hidden) for i in range(14)]


def load_model(device: torch.device) -> bert_labeler:
    model = bert_labeler()
    ckpt = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True)
    state_dict = ckpt["model_state_dict"]
    from collections import OrderedDict
    stripped = OrderedDict((k[len("module."):] if k.startswith("module.") else k, v)
                            for k, v in state_dict.items())
    model.load_state_dict(stripped, strict=True)
    model.to(device)
    model.eval()
    return model


def tokenize_texts(texts: list[str], tokenizer: BertTokenizer) -> list[list[int]]:
    """Verbatim logic from stanfordmlgroup/CheXbert's src/bert_tokenizer.py."""
    out = []
    for text in texts:
        tokenized = tokenizer.tokenize(text)
        if tokenized:
            ids = tokenizer.encode_plus(tokenized)["input_ids"]
            if len(ids) > 512:
                ids = ids[:511] + [tokenizer.sep_token_id]
        else:
            ids = [tokenizer.cls_token_id, tokenizer.sep_token_id]
        out.append(ids)
    return out


def run_labeler(texts: list[str], model: bert_labeler, tokenizer: BertTokenizer,
                 device: torch.device, batch_size: int = 16) -> np.ndarray:
    """Returns an (n_texts, 14) array of class indices (0-3), via the model's own
    argmax -- no CLASS_MAPPING applied yet."""
    token_ids = tokenize_texts(texts, tokenizer)
    all_preds = np.zeros((len(texts), 14), dtype=np.int64)
    for start in range(0, len(texts), batch_size):
        batch_ids = token_ids[start:start + batch_size]
        max_len = max(len(ids) for ids in batch_ids)
        padded = torch.zeros((len(batch_ids), max_len), dtype=torch.long)
        attn = torch.zeros((len(batch_ids), max_len), dtype=torch.long)
        for i, ids in enumerate(batch_ids):
            padded[i, :len(ids)] = torch.tensor(ids, dtype=torch.long)
            attn[i, :len(ids)] = 1
        padded, attn = padded.to(device), attn.to(device)
        with torch.no_grad():
            out = model(padded, attn)
        for j in range(14):
            all_preds[start:start + batch_size, j] = out[j].argmax(dim=1).cpu().numpy()
    return all_preds


def to_present_binary(class_indices: np.ndarray) -> np.ndarray:
    """Step 3a: Positive AND Uncertain both collapse to 'present' (1);
    Blank and Negative both collapse to 'absent' (0)."""
    return np.isin(class_indices, [1, 3]).astype(np.int64)


def f1_micro_macro(gen: np.ndarray, ref: np.ndarray) -> tuple[float, float, np.ndarray]:
    """gen, ref: (n_cases, 14) binary presence matrices. Returns (micro_f1, macro_f1, per_label_f1)."""
    tp = ((gen == 1) & (ref == 1)).sum(axis=0).astype(np.float64)
    fp = ((gen == 1) & (ref == 0)).sum(axis=0).astype(np.float64)
    fn = ((gen == 0) & (ref == 1)).sum(axis=0).astype(np.float64)

    def _f1(tp_, fp_, fn_):
        prec = tp_ / (tp_ + fp_) if (tp_ + fp_) > 0 else 0.0
        rec = tp_ / (tp_ + fn_) if (tp_ + fn_) > 0 else 0.0
        return 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

    per_label_f1 = np.array([_f1(tp[i], fp[i], fn[i]) for i in range(len(CONDITIONS))])
    macro_f1 = float(per_label_f1.mean())
    micro_f1 = _f1(tp.sum(), fp.sum(), fn.sum())
    return micro_f1, macro_f1, per_label_f1


def _derangement(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    fixed = np.where(perm == np.arange(n))[0]
    for i in fixed:
        j = (i + 1) % n
        perm[i], perm[j] = perm[j], perm[i]
    assert not np.any(perm == np.arange(n))
    return perm


def bootstrap_ci(values_fn, n_cases: int, n_boot: int, seed: int, alpha: float = 0.05):
    """values_fn(idx) -> scalar, given a (possibly repeated) array of case indices."""
    rng = np.random.default_rng(seed)
    boot = np.empty(n_boot, dtype=np.float64)
    for b in range(n_boot):
        idx = rng.integers(0, n_cases, size=n_cases)
        boot[b] = values_fn(idx)
    lo, hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return lo, hi


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=".")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    data_root = Path(args.data_root)
    out_dir = data_root / "ml/outputs/evaluation/generation"
    text_dir = out_dir / "generated_text"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[score_chexbert] device={device}")
    tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
    model = load_model(device)
    print("[score_chexbert] model loaded, 227/227 keys (verified in Steps 1-2)")

    case_files = sorted(text_dir.glob("*.json"))
    study_uids = [p.stem for p in case_files]
    n = len(study_uids)
    print(f"[score_chexbert] {n} completed cases")

    results = {}
    for field in GROUND_TRUTH_FIELDS:
        gen_texts, ref_texts = [], []
        for path in case_files:
            data = json.loads(path.read_text())
            gen_texts.append(data["generated"][field])
            ref_texts.append(data["ground_truth"][field])

        print(f"[score_chexbert] labeling '{field}' generated texts ({n})...")
        gen_classes = run_labeler(gen_texts, model, tokenizer, device)
        print(f"[score_chexbert] labeling '{field}' reference texts ({n})...")
        ref_classes = run_labeler(ref_texts, model, tokenizer, device)

        gen_bin = to_present_binary(gen_classes)
        ref_bin = to_present_binary(ref_classes)

        micro_f1, macro_f1, per_label_f1 = f1_micro_macro(gen_bin, ref_bin)
        print(f"[score_chexbert] {field}: micro_f1={micro_f1:.4f}  macro_f1={macro_f1:.4f} (headline)")

        # Step 4: mismatched-pairs random baseline (same derangement scheme as Tier 2)
        perm = _derangement(n, MISMATCH_SEED)
        ref_bin_shuffled = ref_bin[perm]
        base_micro_f1, base_macro_f1, base_per_label_f1 = f1_micro_macro(gen_bin, ref_bin_shuffled)
        print(f"[score_chexbert] {field} random baseline: micro_f1={base_micro_f1:.4f}  macro_f1={base_macro_f1:.4f}")

        # Step 5: bootstrap CIs, Phase 0's exact config
        def macro_of_idx(idx, g=gen_bin, r=ref_bin):
            return f1_micro_macro(g[idx], r[idx])[1]

        def micro_of_idx(idx, g=gen_bin, r=ref_bin):
            return f1_micro_macro(g[idx], r[idx])[0]

        def base_macro_of_idx(idx, g=gen_bin, r=ref_bin_shuffled):
            return f1_micro_macro(g[idx], r[idx])[1]

        def diff_macro_of_idx(idx, g=gen_bin, r=ref_bin, rb=ref_bin_shuffled):
            return f1_micro_macro(g[idx], r[idx])[1] - f1_micro_macro(g[idx], rb[idx])[1]

        macro_lo, macro_hi = bootstrap_ci(macro_of_idx, n, args.n_boot, args.seed)
        micro_lo, micro_hi = bootstrap_ci(micro_of_idx, n, args.n_boot, args.seed)
        base_macro_lo, base_macro_hi = bootstrap_ci(base_macro_of_idx, n, args.n_boot, args.seed)
        diff_lo, diff_hi = bootstrap_ci(diff_macro_of_idx, n, args.n_boot, args.seed)
        excludes_zero = diff_lo > 0 or diff_hi < 0

        print(f"[score_chexbert] {field} macro_f1 95% CI=[{macro_lo:.4f}, {macro_hi:.4f}]")
        print(f"[score_chexbert] {field} micro_f1 95% CI=[{micro_lo:.4f}, {micro_hi:.4f}]")
        print(f"[score_chexbert] {field} baseline macro_f1 95% CI=[{base_macro_lo:.4f}, {base_macro_hi:.4f}]")
        print(f"[score_chexbert] {field} real-minus-baseline macro_f1 diff 95% CI=[{diff_lo:.4f}, {diff_hi:.4f}]"
              f"  excludes_zero={excludes_zero}")

        results[field] = {
            "n": n,
            "micro_f1": micro_f1, "micro_f1_ci": [micro_lo, micro_hi],
            "macro_f1": macro_f1, "macro_f1_ci": [macro_lo, macro_hi],
            "per_label_f1": dict(zip(CONDITIONS, per_label_f1.tolist())),
            "random_baseline_micro_f1": base_micro_f1,
            "random_baseline_macro_f1": base_macro_f1,
            "random_baseline_macro_f1_ci": [base_macro_lo, base_macro_hi],
            "real_minus_baseline_macro_f1_diff": macro_f1 - base_macro_f1,
            "real_minus_baseline_macro_f1_diff_ci": [diff_lo, diff_hi],
            "real_minus_baseline_excludes_zero": bool(excludes_zero),
        }

        pd.DataFrame({
            "study_uid": study_uids,
            **{f"gen_{c}": gen_bin[:, i] for i, c in enumerate(CONDITIONS)},
            **{f"ref_{c}": ref_bin[:, i] for i, c in enumerate(CONDITIONS)},
        }).to_csv(out_dir / f"tier3_chexbert_{field}_labels.csv", index=False)

    out_path = out_dir / "tier3_chexbert_summary.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"[score_chexbert] wrote {out_path}")


if __name__ == "__main__":
    main()
