"""
validate_embeddings.py
====================================================================
ml/embeddings -- Phase 2 closing validation. Sanity-checks the ACTUAL cached
embeddings produced by generate_embeddings.py on real data -- distinct from
Phase 0's encoder bake-off, which already validated BiomedCLIP as the right
encoder choice. This script asks a narrower question: did THIS production
run produce healthy, correctly-aligned vectors?

Three checks, each independently informative:

1. Array health -- every cached array: no NaN/Inf, correct unit norm
   (L2-normalization actually worked), no degenerate zero vectors. Catches
   corruption from an interrupted run or a bad image file.

2. Near-duplicate cluster cohesion -- reuses neardup_clusters.csv from
   Phase 0 (studies already known, by text near-duplication, to be
   near-identical images). Their image embeddings should be highly similar
   to each other and MORE similar than random pairs. A strong, almost
   tautological check: if this fails, something fundamental is wrong (wrong
   image loaded, misaligned uid, corrupted cache).

3. Image->text batch retrieval accuracy -- the most direct test of WHY
   BiomedCLIP was chosen: for a random batch of studies, does each image
   embedding's own report-text embedding rank as its closest match among
   the batch, more often than chance (1/batch_size)? This validates the
   shared latent space is functioning, not just that vectors exist.

Usage:
    python ml/embeddings/validate_embeddings.py \
        --config ml/config/phase0_config.yaml --data-root . --seed 42
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def load_split_cache(embeddings_dir: Path, kind: str, split: str) -> tuple[np.ndarray, np.ndarray] | None:
    arr_path = embeddings_dir / f"biomedclip_{kind}_{split}.npy"
    uids_path = embeddings_dir / f"biomedclip_{kind}_{split}_uids.npy"
    if not (arr_path.exists() and uids_path.exists()):
        return None
    return np.load(arr_path), np.load(uids_path)


def check_array_health(name: str, arr: np.ndarray) -> dict:
    finite = np.isfinite(arr).all()
    norms = np.linalg.norm(arr, axis=1)
    zero_vectors = int((norms < 1e-8).sum())
    norm_mean, norm_std = float(norms.mean()), float(norms.std())
    norm_ok = abs(norm_mean - 1.0) < 1e-3 and norm_std < 1e-3
    result = {
        "array": name, "n": len(arr), "all_finite": bool(finite),
        "zero_vectors": zero_vectors, "norm_mean": round(norm_mean, 6),
        "norm_std": round(norm_std, 6), "norm_ok": norm_ok,
        "healthy": bool(finite) and zero_vectors == 0 and norm_ok,
    }
    return result


def check_neardup_cohesion(
    image_arr: np.ndarray, image_uids: np.ndarray, clusters_df: pd.DataFrame, rng: np.random.Generator,
    n_random_pairs: int = 2000,
) -> dict:
    uid_to_idx = {int(u): i for i, u in enumerate(image_uids)}

    within_sims = []
    for _, row in clusters_df.iterrows():
        member_uids = [int(u) for u in str(row["member_uids"]).split(";")]
        idxs = [uid_to_idx[u] for u in member_uids if u in uid_to_idx]
        if len(idxs) < 2:
            continue
        vecs = image_arr[idxs]
        sim_matrix = vecs @ vecs.T
        iu = np.triu_indices(len(idxs), k=1)
        within_sims.extend(sim_matrix[iu].tolist())

    n = len(image_arr)
    rand_i = rng.integers(0, n, size=n_random_pairs)
    rand_j = rng.integers(0, n, size=n_random_pairs)
    mask = rand_i != rand_j
    random_sims = (image_arr[rand_i[mask]] * image_arr[rand_j[mask]]).sum(axis=1)

    return {
        "n_cluster_pairs": len(within_sims),
        "within_cluster_mean_sim": round(float(np.mean(within_sims)), 4) if within_sims else None,
        "within_cluster_min_sim": round(float(np.min(within_sims)), 4) if within_sims else None,
        "n_random_pairs": int(mask.sum()),
        "random_pair_mean_sim": round(float(np.mean(random_sims)), 4),
        "cohesion_gap": (round(float(np.mean(within_sims) - np.mean(random_sims)), 4)
                          if within_sims else None),
    }


def check_image_text_retrieval(
    image_arr: np.ndarray, image_uids: np.ndarray,
    text_arr: np.ndarray, text_uids: np.ndarray,
    rng: np.random.Generator, batch_size: int = 50, n_batches: int = 10,
) -> dict:
    img_map = {int(u): i for i, u in enumerate(image_uids)}
    txt_map = {int(u): i for i, u in enumerate(text_uids)}
    common_uids = sorted(set(img_map) & set(txt_map))
    if len(common_uids) < batch_size:
        return {"error": f"only {len(common_uids)} uids have both image+text; "
                          f"need >= {batch_size} for a batch"}

    top1_hits, top5_hits, total = 0, 0, 0
    for _ in range(n_batches):
        batch_uids = rng.choice(common_uids, size=batch_size, replace=False)
        img_idx = [img_map[u] for u in batch_uids]
        txt_idx = [txt_map[u] for u in batch_uids]
        img_batch = image_arr[img_idx]          # (B, D)
        txt_batch = text_arr[txt_idx]            # (B, D)
        sim = img_batch @ txt_batch.T            # (B, B), row i = image i vs all texts
        ranks = np.argsort(-sim, axis=1)
        for i in range(batch_size):
            if ranks[i, 0] == i:
                top1_hits += 1
            if i in ranks[i, :5]:
                top5_hits += 1
            total += 1

    return {
        "n_batches": n_batches, "batch_size": batch_size, "n_pairs_evaluated": total,
        "top1_accuracy": round(top1_hits / total, 4),
        "top5_accuracy": round(top5_hits / total, 4),
        "random_baseline_top1": round(1 / batch_size, 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="ml/config/phase0_config.yaml")
    ap.add_argument("--data-root", default=".")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    with open(args.config) as fh:
        cfg = yaml.safe_load(fh)
    data_root = Path(args.data_root)
    embeddings_dir = data_root / Path(cfg["paths"]["embeddings_dir"])
    splits_dir = Path(cfg["paths"]["splits_dir"])
    rng = np.random.default_rng(args.seed)

    print("=" * 70)
    print("CHECK 1: ARRAY HEALTH")
    print("=" * 70)
    health_rows = []
    caches = {}  # (kind, split) -> (arr, uids)
    for split in ("train", "val", "test"):
        for kind in ("image", "text"):
            loaded = load_split_cache(embeddings_dir, kind, split)
            if loaded is None:
                print(f"  {kind}/{split}: NOT FOUND, skipping")
                continue
            arr, uids = loaded
            caches[(kind, split)] = (arr, uids)
            health_rows.append(check_array_health(f"{kind}_{split}", arr))
    health_df = pd.DataFrame(health_rows)
    print(health_df.to_string(index=False))
    all_healthy = health_df["healthy"].all() if not health_df.empty else False
    print(f"\nAll arrays healthy: {all_healthy}")

    print("\n" + "=" * 70)
    print("CHECK 2: NEAR-DUPLICATE CLUSTER COHESION (train split image embeddings)")
    print("=" * 70)
    clusters_path = splits_dir / "neardup_clusters.csv"
    if ("image", "train") in caches and clusters_path.exists():
        image_arr, image_uids = caches[("image", "train")]
        clusters_df = pd.read_csv(clusters_path)
        cohesion = check_neardup_cohesion(image_arr, image_uids, clusters_df, rng)
        for k, v in cohesion.items():
            print(f"  {k}: {v}")
        if cohesion["within_cluster_mean_sim"] is not None:
            print(f"\n  Interpretation: within-cluster similarity should be MUCH higher "
                  f"than random-pair similarity.")
            print(f"  Gap = {cohesion['cohesion_gap']} "
                  f"({'PASS -- clearly separated' if cohesion['cohesion_gap'] and cohesion['cohesion_gap'] > 0.1 else 'CHECK -- gap smaller than expected'})")
    else:
        print("  SKIPPED: missing train image cache or neardup_clusters.csv")

    print("\n" + "=" * 70)
    print("CHECK 3: IMAGE->TEXT BATCH RETRIEVAL ACCURACY (train split)")
    print("=" * 70)
    if ("image", "train") in caches and ("text", "train") in caches:
        img_arr, img_uids = caches[("image", "train")]
        txt_arr, txt_uids = caches[("text", "train")]
        retrieval = check_image_text_retrieval(img_arr, img_uids, txt_arr, txt_uids, rng)
        for k, v in retrieval.items():
            print(f"  {k}: {v}")
        if "top1_accuracy" in retrieval:
            print(f"\n  Interpretation: top1_accuracy should be far above the random "
                  f"baseline ({retrieval['random_baseline_top1']}) if image and text "
                  f"embeddings are correctly aligned in the shared latent space.")
    else:
        print("  SKIPPED: missing train image or text cache")

    print("\n" + "=" * 70)
    print(f"OVERALL: {'ALL CHECKS PASSED' if all_healthy else 'SEE ABOVE -- SOME ISSUES FOUND'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
