"""
build_manual_review_detail.py
====================================================================
Phase 0, step 3c  --  turns manual_review_sample.csv into a query-vs-neighbor
sheet you can actually rate by eye, instead of a query list you'd have to
look up neighbors for by hand.

Reuses the BiomedCLIP embeddings already cached by run_encoder_eval.py
(outputs/embeddings/biomedclip_{train,val}.npy) -- no re-embedding, CPU-only,
runs in seconds.

Reproduces the EXACT same filter/order pipeline run_encoder_eval.py used to
build train/val, so row i of the cached embedding array is guaranteed to
correspond to row i of the train/val dataframe here. If this ever drifts
out of sync with run_encoder_eval.py, the neighbor lookup would silently be
wrong -- keep the two in lockstep if either is edited.

For each of the sampled queries in manual_review_sample.csv, retrieves its
real top-5 BiomedCLIP neighbors from the train KB and writes one row per
(query, rank) pair with both reports' text side by side, the label-overlap
count (your relevance proxy), and a blank column to fill in by hand.

Output:
    outputs/manual_review_detail.csv   -- 36 queries x top-5 = ~180 rows

Usage:
    python scripts/build_manual_review_detail.py --config config/phase0_config.yaml --data-root .
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase0_config.yaml")
    ap.add_argument("--data-root", default=".")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    with open(args.config) as fh:
        cfg = yaml.safe_load(fh)
    out_dir = Path(cfg["paths"]["out_dir"])
    metadata_dir = Path(cfg["paths"]["metadata_dir"])
    splits_dir = Path(cfg["paths"]["splits_dir"])
    data_root = Path(args.data_root)
    emb_dir = Path(cfg["paths"]["embeddings_dir"])

    sample_path = out_dir / "manual_review_sample.csv"
    if not sample_path.exists():
        raise FileNotFoundError(f"{sample_path} missing. Run analyze_results.py first.")
    sample = pd.read_csv(sample_path)

    train_emb_path = emb_dir / "biomedclip_train.npy"
    val_emb_path = emb_dir / "biomedclip_val.npy"
    if not train_emb_path.exists() or not val_emb_path.exists():
        raise FileNotFoundError(
            f"Cached embeddings not found at {emb_dir}. "
            "Run run_encoder_eval.py first (it caches biomedclip embeddings there).")

    # --- reproduce the EXACT train/val row order run_encoder_eval.py used ---
    idx = pd.read_csv(metadata_dir / "study_index.csv")
    splits = pd.read_csv(splits_dir / "splits.csv")
    df = idx.merge(splits, on="uid")
    df = df[df["has_frontal"]].copy()
    train = df[df["split"] == "train"].reset_index(drop=True)
    val = df[df["split"] == "val"].reset_index(drop=True)

    train_emb = np.load(train_emb_path)
    val_emb = np.load(val_emb_path)
    if len(train) != train_emb.shape[0] or len(val) != val_emb.shape[0]:
        raise RuntimeError(
            f"Alignment mismatch: train {len(train)} vs embeddings {train_emb.shape[0]}, "
            f"val {len(val)} vs embeddings {val_emb.shape[0]}. "
            "study_index.csv / splits.csv may have changed since the embeddings were cached "
            "-- rerun run_encoder_eval.py to refresh the cache.")

    uid_to_val_row = {uid: i for i, uid in enumerate(val["uid"])}
    train_uid_arr = train["uid"].to_numpy()

    label_cols = [c for c in idx.columns if c not in (
        "uid", "primary_label", "label_set", "num_labels",
        "has_frontal", "frontal_filename", "exclude_flag")]
    label_lookup = idx.set_index("uid")[label_cols]

    reports_path = data_root / cfg["paths"]["reports_csv"]
    rep = pd.read_csv(reports_path)[["uid", "findings", "impression"]].set_index("uid")

    def text_of(uid: int) -> tuple[str, str]:
        if uid in rep.index:
            row = rep.loc[uid]
            return (str(row["findings"]) if pd.notna(row["findings"]) else "",
                    str(row["impression"]) if pd.notna(row["impression"]) else "")
        return "", ""

    rows = []
    missing = []
    for _, qrow in sample.iterrows():
        q_uid = int(qrow["query_uid"])
        if q_uid not in uid_to_val_row:
            missing.append(q_uid)
            continue
        v_i = uid_to_val_row[q_uid]
        sims = val_emb[v_i] @ train_emb.T
        top_idx = np.argsort(-sims)[: args.top_k]

        q_find, q_impr = text_of(q_uid)
        q_labels = set(label_lookup.loc[q_uid][label_lookup.loc[q_uid] == 1].index) if q_uid in label_lookup.index else set()

        for rank, t_i in enumerate(top_idx, start=1):
            r_uid = int(train_uid_arr[t_i])
            r_find, r_impr = text_of(r_uid)
            r_labels = set(label_lookup.loc[r_uid][label_lookup.loc[r_uid] == 1].index) if r_uid in label_lookup.index else set()
            overlap = q_labels & r_labels

            rows.append({
                "query_uid": q_uid,
                "query_primary_label": qrow["query_primary_label"],
                "query_findings": q_find,
                "query_impression": q_impr,
                "rank": rank,
                "similarity": round(float(sims[t_i]), 4),
                "retrieved_uid": r_uid,
                "retrieved_primary_label": label_lookup.loc[r_uid].idxmax() if r_uid in label_lookup.index else "",
                "retrieved_findings": r_find,
                "retrieved_impression": r_impr,
                "label_overlap_count": len(overlap),
                "overlapping_labels": ";".join(sorted(overlap)),
                "proxy_relevant": len(overlap) > 0,
                "human_relevance_0_1_2": "",   # <-- fill this in by hand: 0/1/2
            })

    if missing:
        print(f"[warn] {len(missing)} sampled query uids not found in val split "
              f"(sample file may be stale): {missing}")

    detail = pd.DataFrame(rows)
    out_path = out_dir / "manual_review_detail.csv"
    detail.to_csv(out_path, index=False)

    print(f"[build_manual_review_detail] {detail['query_uid'].nunique()} queries "
          f"x top-{args.top_k} = {len(detail)} rows -> {out_path}")
    print(f"[build_manual_review_detail] proxy_relevant already computed from label overlap; "
          f"fill in human_relevance_0_1_2 by reading query_findings vs retrieved_findings "
          f"(0=unrelated, 1=partially related, 2=clearly the same kind of case).")
    print(f"[build_manual_review_detail] {int(detail['proxy_relevant'].sum())}/{len(detail)} "
          f"pairs are proxy-relevant (label overlap > 0) -- see how often you agree.")


if __name__ == "__main__":
    main()
