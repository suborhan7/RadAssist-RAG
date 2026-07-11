"""
generate_embeddings.py
====================================================================
ml/embeddings -- Phase 2 batch orchestrator. Reads master_metadata.csv (the
single source of truth), embeds every study's masked frontal image and
report text via the shared BiomedCLIPEmbedder, caches both to
ml/outputs/embeddings/.

This is a thin orchestrator, not where embedding logic lives -- all actual
model/preprocessing logic is in shared/embeddings/biomedclip_embedder.py.
This script's only jobs: read the metadata, decide which paths/texts to
embed, call the embedder, write the outputs with uid alignment.

Uses MASKED images (not raw) -- PHI masking is validated and complete, so
production embeddings should be computed from privacy-protected images.
Falls back to raw with a warning if a masked file is unexpectedly missing.

Output naming (explicit, supersedes Phase 0's narrower image-only cache):
    ml/outputs/embeddings/biomedclip_image_{split}.npy       (N, D) float32
    ml/outputs/embeddings/biomedclip_image_{split}_uids.npy  (N,) int64, aligned
    ml/outputs/embeddings/biomedclip_text_{split}.npy        (M, D) float32
    ml/outputs/embeddings/biomedclip_text_{split}_uids.npy   (M,) int64, aligned

Computing embeddings for all three splits (train/val/test) here does NOT
violate the "touch test once" leakage protocol -- that discipline applies to
building the retrieval KB (train-only) and final evaluation, both later
steps. Raw embedding computation is a representation, not an evaluation look.

Usage:
    python ml/embeddings/generate_embeddings.py \
        --config ml/config/phase0_config.yaml --data-root .
    python ml/embeddings/generate_embeddings.py ... --limit 20   # smoke test
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def _cache_valid(path_arr: Path, path_uids: Path, expected_n: int) -> bool:
    if not (path_arr.exists() and path_uids.exists()):
        return False
    try:
        return len(np.load(path_uids)) == expected_n
    except Exception:
        return False


def embed_split(
    embedder,
    df: pd.DataFrame,
    split: str,
    embeddings_dir: Path,
    data_root: Path,
    kind: str,  # "image" or "text"
) -> dict:
    """Embeds one split's worth of images or text; skips if a valid cache exists."""
    out_arr = embeddings_dir / f"biomedclip_{kind}_{split}.npy"
    out_uids = embeddings_dir / f"biomedclip_{kind}_{split}_uids.npy"

    if kind == "image":
        subset = df[(df["split"] == split) & (df["has_frontal"])].copy()
        paths, uids, fallback_count = [], [], 0
        for _, row in subset.iterrows():
            masked = row.get("masked_image_path")
            if isinstance(masked, str) and (data_root / masked).exists():
                paths.append(str(data_root / masked))
            else:
                raw = row.get("raw_image_path")
                if isinstance(raw, str) and (data_root / raw).exists():
                    print(f"[generate_embeddings] WARN uid={row['study_uid']}: "
                          f"masked image missing, falling back to raw")
                    paths.append(str(data_root / raw))
                    fallback_count += 1
                else:
                    continue  # neither exists -- skip, no path to embed
            uids.append(row["study_uid"])
        if fallback_count:
            print(f"[generate_embeddings] {split}/{kind}: {fallback_count} fell back to raw")
    else:  # text
        subset = df[(df["split"] == split) & df["full_text"].notna()
                     & (df["full_text"].str.len() > 0)].copy()
        paths = subset["full_text"].tolist()  # "paths" here = text strings
        uids = subset["study_uid"].tolist()

    n = len(uids)
    if n == 0:
        print(f"[generate_embeddings] {split}/{kind}: 0 items, skipping")
        return {"split": split, "kind": kind, "n": 0, "cached": False, "elapsed_sec": 0.0}

    if _cache_valid(out_arr, out_uids, n):
        print(f"[generate_embeddings] {split}/{kind}: cache valid ({n} items), skipping")
        return {"split": split, "kind": kind, "n": n, "cached": True, "elapsed_sec": 0.0}

    start = time.perf_counter()
    if kind == "image":
        vecs = embedder.embed_images(paths)
    else:
        vecs = embedder.embed_texts(paths)
    elapsed = time.perf_counter() - start

    embeddings_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_arr, vecs)
    np.save(out_uids, np.array(uids, dtype=np.int64))

    print(f"[generate_embeddings] {split}/{kind}: embedded {n} items in {elapsed:.1f}s "
          f"({elapsed/n:.3f}s/item), dim={vecs.shape[1]}")
    return {"split": split, "kind": kind, "n": n, "cached": False, "elapsed_sec": elapsed}


def run(embedder, metadata_df: pd.DataFrame, embeddings_dir: Path, data_root: Path) -> list[dict]:
    """Core orchestration logic, separated from main() for testability with a fake embedder."""
    results = []
    for split in ("train", "val", "test"):
        for kind in ("image", "text"):
            results.append(embed_split(embedder, metadata_df, split, embeddings_dir, data_root, kind))
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="ml/config/phase0_config.yaml")
    ap.add_argument("--data-root", default=".")
    ap.add_argument("--limit", type=int, default=None,
                     help="process only first N studies per split (dry run)")
    ap.add_argument("--device", default="auto")
    args = ap.parse_args()

    with open(args.config) as fh:
        cfg = yaml.safe_load(fh)
    data_root = Path(args.data_root)
    metadata_dir = Path(cfg["paths"]["metadata_dir"])
    embeddings_dir = data_root / Path(cfg["paths"]["embeddings_dir"])

    df = pd.read_csv(metadata_dir / "master_metadata.csv")
    if args.limit:
        # explicit per-group loop -- does NOT rely on groupby().apply() retaining
        # the grouping column, which pandas >=2.2 drops by default when the
        # applied function returns the group frame unchanged (silent breakage
        # on pandas 3.x otherwise: 'split' disappears from the result).
        parts = [g.head(args.limit) for _, g in df.groupby("split")]
        df = pd.concat(parts, ignore_index=True)
        print(f"[generate_embeddings] --limit {args.limit}: using {len(df)} studies total")

    sys.path.insert(0, str(data_root))
    from shared.embeddings.biomedclip_embedder import BiomedCLIPEmbedder
    embedder = BiomedCLIPEmbedder(device=args.device)

    results = run(embedder, df, embeddings_dir, data_root)

    print("\n[generate_embeddings] summary:")
    summary = pd.DataFrame(results)
    print(summary.to_string(index=False))
    total_embedded = summary.loc[~summary["cached"], "n"].sum()
    total_time = summary["elapsed_sec"].sum()
    print(f"\n[generate_embeddings] total newly embedded: {total_embedded}, "
          f"total time: {total_time:.1f}s")
    print(f"[generate_embeddings] outputs written to: {embeddings_dir}")
    print(f"[generate_embeddings] re-run ml/preprocessing/build_master_metadata.py "
          f"to refresh embedding_cached / processing_stage against these new files.")


if __name__ == "__main__":
    main()