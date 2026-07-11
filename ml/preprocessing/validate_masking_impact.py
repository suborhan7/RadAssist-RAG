"""
validate_masking_impact.py
====================================================================
ml/preprocessing -- sanity check for phi_masking.py.

Embeds a sample of images before and after masking (BiomedCLIP) and reports
cosine similarity between the pair. High similarity confirms masking only
removed peripheral text and left the diagnostically relevant (lung-field)
content intact. A low-similarity outlier flags a mask that likely overlapped
real anatomy and should be inspected manually.

Reuses embed_images() from ml/evaluation/run_encoder_eval.py -- no duplicate
BiomedCLIP-loading code.

Usage:
    python ml/preprocessing/validate_masking_impact.py \
        --config ml/config/phase0_config.yaml --data-root . --n-sample 30
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="ml/config/phase0_config.yaml")
    ap.add_argument("--data-root", default=".")
    ap.add_argument("--n-sample", type=int, default=30)
    ap.add_argument("--flag-below", type=float, default=0.90,
                     help="similarity below this triggers a manual-review flag")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(args.data_root) / "ml" / "evaluation"))
    from run_encoder_eval import embed_images  # reuse, no duplicate BiomedCLIP loader

    with open(args.config) as fh:
        cfg = yaml.safe_load(fh)
    data_root = Path(args.data_root)
    metadata_dir = Path(cfg["paths"]["metadata_dir"])
    img_root = data_root / cfg["paths"]["image_root"]
    masked_dir = data_root / "ml/datasets/masked"

    idx = pd.read_csv(metadata_dir / "study_index.csv")
    frontal = idx[idx["has_frontal"]].copy()

    # only images that actually have a masked counterpart on disk
    frontal["masked_exists"] = frontal["frontal_filename"].apply(
        lambda f: (masked_dir / f).exists())
    candidates = frontal[frontal["masked_exists"]]
    if candidates.empty:
        raise SystemExit("No masked images found -- run phi_masking.py first.")

    sample = candidates.sample(min(args.n_sample, len(candidates)), random_state=42)

    orig_paths = [img_root / f for f in sample["frontal_filename"]]
    masked_paths = [masked_dir / f for f in sample["frontal_filename"]]

    orig_emb = embed_images("biomedclip", orig_paths, args.device)
    masked_emb = embed_images("biomedclip", masked_paths, args.device)

    sims = (orig_emb * masked_emb).sum(axis=1)  # both L2-normalized -> dot == cosine
    result = sample[["uid", "frontal_filename"]].copy()
    result["cosine_similarity"] = sims
    result["flagged_for_review"] = sims < args.flag_below

    print(f"[validate_masking] n={len(result)}  "
          f"mean similarity={sims.mean():.4f}  min={sims.min():.4f}  max={sims.max():.4f}")
    n_flagged = int(result["flagged_for_review"].sum())
    print(f"[validate_masking] flagged (<{args.flag_below}): {n_flagged}/{len(result)}")
    if n_flagged:
        print(result[result.flagged_for_review].to_string(index=False))
        print("[validate_masking] inspect these masked images manually -- "
              "low similarity suggests the mask may have overlapped anatomy, "
              "not just peripheral text.")
    else:
        print("[validate_masking] no flags -- masking appears confined to "
              "non-diagnostic regions across the sample.")


if __name__ == "__main__":
    main()
