"""
build_master_metadata.py
====================================================================
ml/preprocessing -- final Phase 1 step. Consolidates every prior artifact
(study_index, study_index_clean, splits, phi_masking_log, projections) into
ONE canonical study-level file: ml/datasets/metadata/master_metadata.csv

This is the single source of truth every downstream module reads from --
embedding, retrieval, evaluation, backend ingestion, and the future
longitudinal-history module. No downstream module should re-join the
underlying files itself.

Idempotent: safe to re-run after any upstream stage changes. `created_at` is
preserved from the previous run if a prior master_metadata.csv exists for a
given uid; `updated_at` always reflects the current run.

`processing_stage` and `embedding_cached` are COMPUTED from what artifacts
actually exist on disk, not manually tracked -- this is deliberate (see
docs/methodology/development_log.md): a batch-generated CSV cannot safely
hold live operational state like ChromaDB-indexed status, which belongs in
the backend's Postgres tables once built. Those live states are NOT included
here; this file only ever reflects filesystem-observable pipeline progress.

Usage:
    python ml/preprocessing/build_master_metadata.py \
        --config ml/config/phase0_config.yaml --data-root .
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PIPELINE_VERSION = "v1"       # bump manually when preprocessing/taxonomy/splitting logic changes
EMBEDDING_MODEL = "biomedclip"
EMBEDDING_VERSION = "v1"      # bump manually if the model or embedding process changes


def compute_processing_stage(row: pd.Series) -> str:
    """Derived from filesystem-observable state only -- never manually set."""
    if not row["raw_image_path_exists"]:
        return "Missing"
    if row["embedding_cached"]:
        return "Embedded"
    if row["masked_image_path_exists"]:
        return "Masked"
    return "Raw"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="ml/config/phase0_config.yaml")
    ap.add_argument("--data-root", default=".")
    args = ap.parse_args()

    with open(args.config) as fh:
        cfg = yaml.safe_load(fh)
    data_root = Path(args.data_root)
    metadata_dir = Path(cfg["paths"]["metadata_dir"])
    splits_dir = Path(cfg["paths"]["splits_dir"])
    embeddings_dir = data_root / Path(cfg["paths"]["embeddings_dir"])
    img_root = data_root / cfg["paths"]["image_root"]
    masked_dir = data_root / "ml/datasets/masked"
    logs_dir = data_root / "ml/outputs/logs"

    # ---- source artifacts ---------------------------------------------
    idx = pd.read_csv(metadata_dir / "study_index.csv")
    clean = pd.read_csv(metadata_dir / "study_index_clean.csv")[
        ["uid", "findings_clean", "impression_clean", "has_findings", "full_text"]
    ]
    splits = pd.read_csv(splits_dir / "splits.csv")
    projections = pd.read_csv(data_root / cfg["paths"]["projections_csv"])

    phi_log_path = logs_dir / "phi_masking_log.csv"
    if phi_log_path.exists():
        phi_log = pd.read_csv(phi_log_path).rename(columns={
            "image_id": "uid",
            "num_regions_detected": "phi_regions_detected",
            "masking_applied": "phi_masking_applied",
        })[["uid", "phi_regions_detected", "phi_masking_applied"]]
    else:
        phi_log = pd.DataFrame(columns=["uid", "phi_regions_detected", "phi_masking_applied"])

    # ---- per-study image list / projections available -------------------
    proj_agg = (
        projections.groupby("uid")
        .agg(image_ids=("filename", lambda s: ";".join(s)),
             projections_available=("projection", lambda s: ";".join(sorted(set(s)))),
             num_images=("filename", "count"))
        .reset_index()
    )

    # ---- assemble ---------------------------------------------------------
    label_cols = [c for c in idx.columns if c not in (
        "uid", "primary_label", "label_set", "num_labels",
        "has_frontal", "frontal_filename", "exclude_flag")]

    df = idx.merge(proj_agg, on="uid", how="left")
    df = df.merge(clean, on="uid", how="left")
    df = df.merge(splits, on="uid", how="left")
    df = df.merge(phi_log, on="uid", how="left")

    df["study_uid"] = df["uid"]
    df["patient_uid"] = "SYN-" + df["uid"].astype(str)  # synthetic 1:1; see schema notes

    df["raw_image_path"] = df["frontal_filename"].apply(
        lambda f: str(Path(cfg["paths"]["image_root"]) / f) if pd.notna(f) else None)

    df["raw_image_path_exists"] = df["frontal_filename"].apply(
        lambda f: (img_root / f).exists() if pd.notna(f) else False)
    df["masked_image_path_exists"] = df["frontal_filename"].apply(
        lambda f: (masked_dir / f).exists() if pd.notna(f) else False)

    # masked_image_path only populated when a masked file actually exists on disk --
    # not merely when a frontal_filename is defined (avoids implying masking ran
    # when it hasn't yet).
    df["masked_image_path"] = df.apply(
        lambda r: "ml/datasets/masked/" + r["frontal_filename"]
        if r["masked_image_path_exists"] else None, axis=1)

    # embedding_cached: does this uid's embedding actually exist in the cached
    # per-split .npy arrays? Cheap existence check via the split-level cache files.
    cached_uids: set[int] = set()
    # embedding_cached: does this uid appear in the uid-aligned image-embedding
    # cache written by ml/embeddings/generate_embeddings.py? Uses the explicit
    # companion _uids.npy array for exact per-uid alignment (supersedes the
    # earlier row-count-guess approach from the Phase 0 scratch cache, which
    # assumed cache order matched a re-derived dataframe filter -- fragile).
    for split_name in ("train", "val", "test"):
        uids_path = embeddings_dir / f"{EMBEDDING_MODEL}_image_{split_name}_uids.npy"
        found = uids_path.exists()
        print(f"[build_master_metadata] checking embedding cache: {uids_path}  exists={found}")
        if found:
            n_uids = np.load(uids_path)
            print(f"[build_master_metadata]   -> {len(n_uids)} uids loaded from this file")
            cached_uids.update(n_uids.tolist())
    df["embedding_cached"] = df["uid"].isin(cached_uids)

    df["processing_stage"] = df.apply(compute_processing_stage, axis=1)

    df["embedding_model"] = EMBEDDING_MODEL
    df["embedding_version"] = EMBEDDING_VERSION
    df["pipeline_version"] = PIPELINE_VERSION

    now = datetime.now(timezone.utc).isoformat()
    df["updated_at"] = now

    # preserve created_at across regenerations if a prior file exists
    out_path = metadata_dir / "master_metadata.csv"
    if out_path.exists():
        prior = pd.read_csv(out_path)[["study_uid", "created_at"]]
        df = df.merge(prior, on="study_uid", how="left")
        df["created_at"] = df["created_at"].fillna(now)
    else:
        df["created_at"] = now

    final_cols = (
        ["study_uid", "patient_uid", "image_ids", "projections_available", "num_images",
         "has_frontal", "frontal_filename", "raw_image_path", "masked_image_path",
         "phi_masking_applied", "phi_regions_detected",
         "primary_label", "label_set"] + label_cols +
        ["findings_clean", "impression_clean", "has_findings", "full_text",
         "split", "cluster_id", "exclude_flag",
         "embedding_model", "embedding_version", "embedding_cached", "processing_stage",
         "pipeline_version", "created_at", "updated_at"]
    )
    df_final = df[final_cols].sort_values("study_uid")
    df_final.to_csv(out_path, index=False)

    print(f"[build_master_metadata] studies: {len(df_final)}")
    print(f"[build_master_metadata] processing_stage distribution:")
    print(df_final["processing_stage"].value_counts().to_string())
    print(f"[build_master_metadata] embedding_cached: {df_final['embedding_cached'].sum()} "
          f"/ {len(df_final)}")
    print(f"[build_master_metadata] phi_masking_applied: "
          f"{df_final['phi_masking_applied'].sum(skipna=True):.0f} "
          f"(NaN = masking not yet run for that study)")
    print(f"[build_master_metadata] wrote {out_path}")


if __name__ == "__main__":
    main()