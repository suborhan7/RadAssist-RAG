"""
make_splits.py
====================================================================
Phase 0, step 2.

Produces leakage-safe 70/15/15 train/val/test splits over studies.

Two leakage hazards are defeated:
  1. View-pair leakage -> the index is already study-level (one row per uid).
  2. Template near-duplicate leakage -> studies whose reports are near-identical
     are clustered and assigned to the SAME split as an atomic unit. This is what
     actually enforces the Fork-D guarantee; splitting on uid alone does not,
     because identical templated reports have different uids.

Stratification uses a self-contained iterative (greedy, rarest-label-first)
multi-label stratifier -- no external stratification dependency.

Outputs:
    outputs/splits.csv            uid, split, cluster_id
    outputs/neardup_clusters.csv  cluster_id, size, member_uids
"""
from __future__ import annotations

import argparse
import random
import re
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

import numpy as np
import pandas as pd
import yaml
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def normalize_text(s: str) -> str:
    s = str(s).lower()
    s = re.sub(r"x{2,}", " ", s)          # collapse de-id XXXX tokens
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def cluster_near_duplicates(
    uids: Sequence[int], texts: Sequence[str], threshold: float
) -> Dict[int, int]:
    """Group studies with TF-IDF cosine >= threshold into connected components."""
    vec = TfidfVectorizer(min_df=2, ngram_range=(1, 2))
    X = vec.fit_transform([normalize_text(t) for t in texts])   # L2-normalized rows
    # cosine similarity via sparse product; threshold to an adjacency graph
    sim = (X @ X.T).tocsr()
    sim.data = (sim.data >= threshold).astype(np.int8)
    sim.eliminate_zeros()
    n_comp, comp = connected_components(sim, directed=False)
    return {uid: int(c) for uid, c in zip(uids, comp)}


def iterative_stratify(
    units: List[Tuple[int, Set[str], int]],
    ratios: Dict[str, float],
    seed: int,
) -> Dict[int, str]:
    """
    Greedy iterative stratification (Sechidis/Szymanski), cluster-weighted.

    units : list of (cluster_id, label_set, weight)   weight = #studies in cluster
    ratios: {split_name: proportion}, must sum to 1.0
    Returns cluster_id -> split_name.
    """
    rng = random.Random(seed)
    splits = list(ratios.keys())

    total_w = sum(w for _, _, w in units)
    all_labels: Set[str] = set().union(*(ls for _, ls, _ in units))

    # desired remaining weight per split, and per (label, split)
    desired: Dict[str, float] = {s: total_w * ratios[s] for s in splits}
    label_w = {lab: sum(w for _, ls, w in units if lab in ls) for lab in all_labels}
    desired_l: Dict[str, Dict[str, float]] = {
        lab: {s: label_w[lab] * ratios[s] for s in splits} for lab in all_labels
    }

    remaining = {cid: (ls, w) for cid, ls, w in units}
    assignment: Dict[int, str] = {}

    while remaining:
        # rarest label among still-unassigned units (fewest remaining units)
        counts: Dict[str, int] = {}
        for _, (ls, _) in remaining.items():
            for lab in ls:
                counts[lab] = counts.get(lab, 0) + 1
        rarest = min(counts, key=lambda l: counts[l])

        batch = [cid for cid, (ls, _) in remaining.items() if rarest in ls]
        batch.sort(key=lambda cid: -remaining[cid][1])  # heaviest first, stable

        for cid in batch:
            ls, w = remaining.pop(cid)
            # choose split with greatest desired remaining for the rarest label,
            # tie-break by greatest overall desired remaining, then random
            best = max(
                splits,
                key=lambda s: (desired_l[rarest][s], desired[s], rng.random()),
            )
            assignment[cid] = best
            desired[best] -= w
            for lab in ls:
                desired_l[lab][best] -= w

    return assignment


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase0_config.yaml")
    ap.add_argument("--data-root", default=".")
    args = ap.parse_args()

    cfg = load_yaml(Path(args.config))
    data_root = Path(args.data_root)
    metadata_dir = Path(cfg["paths"]["metadata_dir"])
    splits_dir = Path(cfg["paths"]["splits_dir"])
    splits_dir.mkdir(parents=True, exist_ok=True)

    idx = pd.read_csv(metadata_dir / "study_index.csv")
    reports = pd.read_csv(data_root / cfg["paths"]["reports_csv"])[
        ["uid", "findings", "impression"]
    ]
    df = idx.merge(reports, on="uid", how="left")

    if cfg["split"].get("exclude_flagged", True):
        before = len(df)
        df = df[~df["exclude_flag"]].copy()
        print(f"[make_splits] dropped {before - len(df)} technical-quality-flagged studies")

    df["text"] = df["findings"].fillna("") + " " + df["impression"].fillna("")

    # 1. near-duplicate clustering ----------------------------------------
    thr = cfg["split"]["near_dup_threshold"]
    cid_map = cluster_near_duplicates(df["uid"].tolist(), df["text"].tolist(), thr)
    df["cluster_id"] = df["uid"].map(cid_map)

    csize = df.groupby("cluster_id").size()
    multi = csize[csize > 1]
    print(f"[make_splits] near-dup threshold: {thr}")
    print(f"[make_splits] clusters: {csize.size}  (singletons: {(csize == 1).sum()})")
    print(f"[make_splits] multi-study clusters: {multi.size}  "
          f"covering {int(multi.sum())} studies; largest={int(csize.max())}")
    print(f"[make_splits] template contamination if split naively: "
          f"{int(multi.sum())}/{len(df)} = {multi.sum()/len(df):.1%} of studies "
          f"live in a near-dup cluster")

    # 2. build cluster-level units (union of labels, weight = #studies) -----
    label_cols = [c for c in idx.columns if c not in (
        "uid", "primary_label", "label_set", "num_labels",
        "has_frontal", "frontal_filename", "exclude_flag")]
    units: List[Tuple[int, Set[str], int]] = []
    for cid, grp in df.groupby("cluster_id"):
        labs = {c for c in label_cols if grp[c].max() == 1}
        units.append((int(cid), labs, len(grp)))

    # 3. iterative stratified assignment -----------------------------------
    ratios = cfg["split"]["ratios"]
    assert abs(sum(ratios.values()) - 1.0) < 1e-6, "ratios must sum to 1.0"
    cluster_split = iterative_stratify(units, ratios, cfg["split"]["seed"])
    df["split"] = df["cluster_id"].map(cluster_split)

    # 4. write outputs ------------------------------------------------------
    df[["uid", "split", "cluster_id"]].sort_values("uid").to_csv(
        splits_dir / "splits.csv", index=False)
    clus_rows = [
        {"cluster_id": cid, "size": len(grp),
         "member_uids": ";".join(map(str, sorted(grp["uid"])))}
        for cid, grp in df.groupby("cluster_id") if len(grp) > 1
    ]
    pd.DataFrame(clus_rows).sort_values("size", ascending=False).to_csv(
        splits_dir / "neardup_clusters.csv", index=False)

    # 5. verification report -----------------------------------------------
    print("\n[make_splits] split sizes:")
    print(df["split"].value_counts().to_string())
    print("\n[make_splits] per-class counts by split (verify every class in all splits):")
    rows = []
    for c in label_cols:
        r = {"class": c}
        for s in ratios:
            r[s] = int(df[df["split"] == s][c].sum())
        rows.append(r)
    dist = pd.DataFrame(rows).sort_values("train", ascending=False)
    print(dist.to_string(index=False))
    print(f"\n[make_splits] wrote {splits_dir/'splits.csv'} and {splits_dir/'neardup_clusters.csv'}")


if __name__ == "__main__":
    main()
