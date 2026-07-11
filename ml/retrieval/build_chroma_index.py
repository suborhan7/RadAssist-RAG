"""
build_chroma_index.py
====================================================================
ml/retrieval -- Phase 3, step 2. Loads train_metadata.csv + the cached
BiomedCLIP train embeddings, validates everything in-memory, and ONLY THEN
deletes the old collection and creates/populates a new one. Never generates
embeddings; never re-derives split membership (train_metadata.csv already
encodes that decision, made in Phase 1 and filtered in step 1).

Validation runs to completion BEFORE any ChromaDB mutation -- a mid-run
failure must never leave zero working collections. Use --dry-run to run all
checks and print the would-be summary without touching the database.

Usage:
    python ml/retrieval/build_chroma_index.py \
        --config ml/config/phase0_config.yaml --data-root . --dry-run
    python ml/retrieval/build_chroma_index.py \
        --config ml/config/phase0_config.yaml --data-root .
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

EMBEDDING_DIM = 512
PIPELINE_VERSION = "v1"


@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_collection_name(dataset: str, embedding_model: str, embedding_version: str, split: str) -> str:
    name = f"{dataset}_{embedding_model}_{embedding_version}_{split}".lower()
    return name


def validate_collection_name(name: str) -> list[str]:
    errors = []
    if not (3 <= len(name) <= 63):
        errors.append(f"collection name length {len(name)} not in [3,63]: '{name}'")
    if not (name[0].isalnum() and name[-1].isalnum()):
        errors.append(f"collection name must start/end alphanumeric: '{name}'")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    bad_chars = set(name) - allowed
    if bad_chars:
        errors.append(f"collection name has disallowed characters {bad_chars}: '{name}'")
    return errors


def validate(
    train_df: pd.DataFrame, embeddings: np.ndarray, embed_uids: np.ndarray, collection_name: str,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    # 1. every row is train split (defense in depth -- file was pre-filtered)
    non_train = train_df[train_df["split"] != "train"]
    if len(non_train) > 0:
        errors.append(f"{len(non_train)} rows in train_metadata.csv are NOT split=='train': "
                       f"uids={non_train['study_uid'].tolist()[:10]}")

    # 2. set-equality between metadata uids and embedding-cache uids
    meta_uids = set(train_df["study_uid"].tolist())
    cache_uids = set(embed_uids.tolist())
    only_in_meta = meta_uids - cache_uids
    only_in_cache = cache_uids - meta_uids
    if only_in_meta:
        errors.append(f"{len(only_in_meta)} uids in train_metadata.csv missing from embedding "
                       f"cache: {sorted(only_in_meta)[:10]}")
    if only_in_cache:
        warnings.append(f"{len(only_in_cache)} uids in embedding cache not in train_metadata.csv "
                         f"(will not be indexed): {sorted(only_in_cache)[:10]}")

    # 3. no duplicate study_uid
    dup_meta = train_df["study_uid"][train_df["study_uid"].duplicated()].tolist()
    if dup_meta:
        errors.append(f"duplicate study_uid in train_metadata.csv: {dup_meta[:10]}")
    dup_cache = pd.Series(embed_uids)[pd.Series(embed_uids).duplicated()].tolist()
    if dup_cache:
        errors.append(f"duplicate uid in embedding cache: {dup_cache[:10]}")

    # 4. no missing required fields
    for field_name in ("masked_image_path", "primary_label", "study_uid"):
        n_missing = train_df[field_name].isna().sum()
        if n_missing > 0:
            errors.append(f"{n_missing} rows missing required field '{field_name}'")

    # 5. embedding array health (re-checks Phase 2's health check at index time,
    #    since cache files could be corrupted/edited between phases)
    if embeddings.shape[1] != EMBEDDING_DIM:
        errors.append(f"embedding dimension {embeddings.shape[1]} != expected {EMBEDDING_DIM}")
    if not np.isfinite(embeddings).all():
        errors.append("embedding cache contains non-finite values (NaN/Inf)")
    norms = np.linalg.norm(embeddings, axis=1)
    zero_vecs = int((norms < 1e-8).sum())
    if zero_vecs > 0:
        errors.append(f"{zero_vecs} degenerate zero-norm embedding vectors found")
    norm_dev = float(np.abs(norms - 1.0).max()) if len(norms) else 0.0
    if norm_dev > 1e-2:
        warnings.append(f"embedding norms deviate from 1.0 by up to {norm_dev:.4f}")

    # 6. collection name validity
    name_errors = validate_collection_name(collection_name)
    errors.extend(name_errors)

    return ValidationResult(passed=len(errors) == 0, errors=errors, warnings=warnings)


def build_metadata_records(train_df: pd.DataFrame, cfg: dict, indexed_at: str) -> list[dict]:
    records = []
    for _, row in train_df.iterrows():
        records.append({
            "study_uid": str(row["study_uid"]),
            "patient_uid": str(row.get("patient_uid", "")),
            "image_path": str(row["masked_image_path"]),
            "projection": "Frontal",
            "primary_label": str(row["primary_label"]),
            "label_set": str(row.get("label_set", "")),
            "is_normal": bool(row["primary_label"] == "Normal"),
            "findings": str(row.get("findings_clean", "") or ""),
            "impression": str(row.get("impression_clean", "") or ""),
            "dataset": "IU_XRay",
            "embedding_model": str(row.get("embedding_model", "biomedclip")),
            "embedding_version": str(row.get("embedding_version", "v1")),
            "split": "train",
            "cluster_id": int(row.get("cluster_id", -1)) if pd.notna(row.get("cluster_id")) else -1,
            "indexed_at": indexed_at,
        })
    return records


def run_indexing(
    train_df: pd.DataFrame, embeddings: np.ndarray, embed_uids: np.ndarray,
    collection_name: str, chroma_client, cfg: dict, dry_run: bool,
) -> dict:
    """Core logic, separated from main() for testability with a fake chroma_client."""
    start = time.perf_counter()
    validation = validate(train_df, embeddings, embed_uids, collection_name)

    for w in validation.warnings:
        print(f"[build_chroma_index] WARNING: {w}")
    for e in validation.errors:
        print(f"[build_chroma_index] ERROR: {e}")

    if not validation.passed:
        print(f"[build_chroma_index] VALIDATION FAILED -- aborting. "
              f"Existing collection (if any) left untouched.")
        return {
            "validation_passed": False, "warnings": validation.warnings,
            "errors": validation.errors, "num_indexed": 0,
        }

    print(f"[build_chroma_index] validation passed "
          f"({len(validation.warnings)} warning(s), 0 errors)")

    # align embeddings to train_df row order by uid (never assume implicit order match)
    uid_to_idx = {int(u): i for i, u in enumerate(embed_uids)}
    ordered_idx = [uid_to_idx[int(u)] for u in train_df["study_uid"]]
    ordered_embeddings = embeddings[ordered_idx]

    indexed_at = datetime.now(timezone.utc).isoformat()
    metadatas = build_metadata_records(train_df, cfg, indexed_at)
    ids = [m["study_uid"] for m in metadatas]

    if dry_run:
        print(f"[build_chroma_index] DRY RUN -- would index {len(ids)} records into "
              f"collection '{collection_name}'. No changes made.")
        elapsed = time.perf_counter() - start
        return _build_summary(collection_name, cfg, train_df, len(ids), 0, 0,
                               EMBEDDING_DIM, validation, elapsed, dry_run=True)

    # delete old collection ONLY after validation passed
    existing = [c.name for c in chroma_client.list_collections()]
    if collection_name in existing:
        chroma_client.delete_collection(collection_name)
        print(f"[build_chroma_index] deleted existing collection '{collection_name}'")

    collection = chroma_client.create_collection(
        name=collection_name, metadata={"hnsw:space": "cosine"},
    )

    batch_size = 256
    for i in range(0, len(ids), batch_size):
        collection.upsert(
            ids=ids[i:i + batch_size],
            embeddings=ordered_embeddings[i:i + batch_size].tolist(),
            metadatas=metadatas[i:i + batch_size],
        )

    actual_count = collection.count()
    if actual_count != len(ids):
        raise RuntimeError(f"post-insert count mismatch: expected {len(ids)}, "
                            f"collection reports {actual_count}")
    print(f"[build_chroma_index] indexed {actual_count} records, verified via collection.count()")

    elapsed = time.perf_counter() - start
    return _build_summary(collection_name, cfg, train_df, actual_count, 0, 0,
                           EMBEDDING_DIM, validation, elapsed, dry_run=False)


def _build_summary(collection_name, cfg, train_df, num_indexed, failed, duplicates,
                    dim, validation, elapsed, dry_run) -> dict:
    class_dist = train_df["primary_label"].value_counts().to_dict()
    cluster_col = train_df.get("cluster_id")
    n_clusters = int(cluster_col.nunique()) if cluster_col is not None else 0
    return {
        "collection_name": collection_name,
        "dataset": "IU_XRay",
        "embedding_model": cfg.get("embedding_model", "biomedclip"),
        "embedding_version": cfg.get("embedding_version", "v1"),
        "pipeline_version": PIPELINE_VERSION,
        "split": "train",
        "source_row_count": len(train_df),
        "num_indexed": num_indexed,
        "failed_records": failed,
        "duplicate_count": duplicates,
        "embedding_dimension": dim,
        "class_distribution": class_dist,
        "distinct_neardup_clusters_represented": n_clusters,
        "validation_passed": validation.passed,
        "warnings": validation.warnings,
        "dry_run": dry_run,
        "execution_time_sec": round(elapsed, 3),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="ml/config/phase0_config.yaml")
    ap.add_argument("--data-root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.config) as fh:
        cfg = yaml.safe_load(fh)
    data_root = Path(args.data_root)
    metadata_dir = Path(cfg["paths"]["metadata_dir"])
    embeddings_dir = data_root / Path(cfg["paths"]["embeddings_dir"])
    retrieval_out = data_root / "ml/outputs/retrieval"
    retrieval_out.mkdir(parents=True, exist_ok=True)
    logs_dir = data_root / "ml/outputs/logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    train_df = pd.read_csv(metadata_dir / "train_metadata.csv")
    embeddings = np.load(embeddings_dir / "biomedclip_image_train.npy")
    embed_uids = np.load(embeddings_dir / "biomedclip_image_train_uids.npy")

    collection_name = build_collection_name("iu_cxr", "biomedclip", "v1", "train")

    import chromadb
    chroma_client = chromadb.PersistentClient(path=str(retrieval_out / "chroma_db"))

    summary = run_indexing(train_df, embeddings, embed_uids, collection_name,
                            chroma_client, cfg, args.dry_run)

    summary_path = retrieval_out / "index_summary.json"
    with open(summary_path, "w") as fh:
        json.dump(summary, fh, indent=2)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    log_path = logs_dir / f"chroma_indexing_{timestamp}.log"
    with open(log_path, "w") as fh:
        fh.write(json.dumps(summary, indent=2))

    print(f"\n[build_chroma_index] summary written to {summary_path}")
    print(f"[build_chroma_index] log written to {log_path}")
    print(json.dumps(summary, indent=2, default=str))

    if not summary.get("validation_passed", False):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
