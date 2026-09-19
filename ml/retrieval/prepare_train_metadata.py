"""
prepare_train_metadata.py
====================================================================
ml/retrieval -- Phase 3, step 1. Single responsibility: filter the frozen
master_metadata.csv down to the subset of train-split studies that are
actually indexable (have a frontal image AND a cached embedding), and write
train_metadata.csv.

This module does NOT decide split membership -- that was already decided in
Phase 1 (leakage-safe splitting) and is frozen. It only filters an existing
column. It does NOT touch embeddings or ChromaDB.

Usage:
    python ml/retrieval/prepare_train_metadata.py \
        --config ml/config/phase0_config.yaml --data-root .
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="ml/config/phase0_config.yaml")
    ap.add_argument("--data-root", default=".")
    args = ap.parse_args()

    with open(args.config) as fh:
        cfg = yaml.safe_load(fh)
    data_root = Path(args.data_root)
    metadata_dir = Path(cfg["paths"]["metadata_dir"])

    src_path = metadata_dir / "master_metadata.csv"
    df = pd.read_csv(src_path)

    before = len(df)
    filtered = df[
        (df["split"] == "train")
        & (df["has_frontal"])
        & (df["embedding_cached"])
    ].copy()

    # Section 15 of input_admission_projection_gate_architecture_v1.1:
    # resolve the projection of the image that is actually indexed, so
    # build_chroma_index.py can read it from the data row instead of
    # writing a literal.
    #
    # Resolved from `frontal_filename` -- the specific image Phase 2
    # embedded and the indexer will store -- joined against the dataset's
    # own projections CSV. Not derived from `has_frontal`, and not assumed
    # from the fact that build_study_index.py filtered for frontal: both of
    # those would re-assert the selection rule rather than describe the
    # image, which is the substitution section 15 exists to remove.
    projections = pd.read_csv(data_root / cfg["paths"]["projections_csv"])
    projection_by_filename = dict(zip(projections["filename"], projections["projection"]))
    filtered["projection"] = filtered["frontal_filename"].map(projection_by_filename)

    unresolved = int(filtered["projection"].isna().sum())
    if unresolved:
        # Loud, not silent. An unresolved projection means the indexed
        # filename is not in the projections CSV, which would make the
        # stored metadata describe an image the dataset does not know
        # about. Writing NaN into Chroma is how "nan" strings reached the
        # evidence cards before (see chroma_result_mapper.py).
        raise SystemExit(
            f"[prepare_train_metadata] {unresolved} row(s) have a frontal_filename that "
            f"is absent from the projections CSV; their projection cannot be resolved. "
            f"Refusing to write a metadata file the indexer would turn into 'nan'."
        )

    # sanity: masked_image_path must be present for every row we're about to
    # hand to the indexer, since Phase 2 embedded from masked images.
    missing_masked = filtered["masked_image_path"].isna().sum()
    if missing_masked > 0:
        print(f"[prepare_train_metadata] WARNING: {missing_masked} rows have "
              f"embedding_cached=True but no masked_image_path -- these will "
              f"fail Chroma indexing validation. Investigate before proceeding.")

    out_path = metadata_dir / "train_metadata.csv"
    filtered.to_csv(out_path, index=False)

    print(f"[prepare_train_metadata] source rows (master_metadata.csv): {before}")
    print(f"[prepare_train_metadata] filtered to indexable train rows: {len(filtered)}")
    print(f"[prepare_train_metadata]   dropped (not train split): "
          f"{(df['split'] != 'train').sum()}")
    print(f"[prepare_train_metadata]   dropped (no frontal): "
          f"{((df['split'] == 'train') & (~df['has_frontal'])).sum()}")
    print(f"[prepare_train_metadata]   dropped (no cached embedding): "
          f"{((df['split'] == 'train') & (df['has_frontal']) & (~df['embedding_cached'])).sum()}")
    print(f"[prepare_train_metadata] wrote {out_path}")


if __name__ == "__main__":
    main()
