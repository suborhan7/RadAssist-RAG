"""
run_encoder_eval.py
====================================================================
Phase 0, step 3  --  THE GATE.  Run on the workstation (needs GPU + downloads).

Image->image retrieval bake-off. Isolates "how good is each image encoder at
retrieving same-finding historical cases", which is the fair apples-to-apples
comparison (DenseNet and generic CLIP cannot embed into BiomedCLIP's text space,
so image->image is the common denominator).

  KB      = TRAIN split, one frontal image per study   (test/val NEVER indexed)
  Queries = VAL split, one frontal image per study
  Relevance(q,d) = | curated_labels(q) ∩ curated_labels(d) |   (graded)

Encoders compared: biomedclip, clip_generic, densenet121, random(baseline).
Exact cosine kNN is used here for metric correctness; the production system uses
ChromaDB for the same operation approximately.

Outputs:
    outputs/encoder_comparison_micro.csv
    outputs/encoder_comparison_macro.csv   (per-primary-class, then macro-averaged)

Decision rule: adopt BiomedCLIP only if it beats clip_generic AND the random
floor on the MACRO (non-Normal) numbers -- not just micro, because Normal ~= 47%
makes the random floor deceptively high.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd
import yaml


# --------------------------------------------------------------------------- #
# Encoders. Imports are deferred so the file loads even without torch present. #
# --------------------------------------------------------------------------- #
def embed_images(encoder: str, paths: Sequence[Path], device: str = "cuda") -> np.ndarray:
    """Return an (N, D) float32 array of L2-normalized image embeddings."""
    if encoder == "biomedclip":
        return _embed_openclip(
            "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224",
            paths, device)
    if encoder == "clip_generic":
        return _embed_openclip("ViT-B-32", paths, device, pretrained="laion2b_s34b_b79k")
    if encoder == "densenet121":
        return _embed_densenet(paths, device)
    raise ValueError(f"unknown encoder: {encoder}")


def _load_images(paths, preprocess):
    from PIL import Image
    import torch
    batch = []
    for p in paths:
        img = Image.open(p).convert("RGB")
        batch.append(preprocess(img))
    return torch.stack(batch)


def _embed_openclip(model_id, paths, device, pretrained=None):
    import open_clip
    import torch
    if pretrained:
        model, _, preprocess = open_clip.create_model_and_transforms(
            model_id, pretrained=pretrained)
    else:
        model, _, preprocess = open_clip.create_model_and_transforms(model_id)
    model = model.to(device).eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(paths), 64):
            x = _load_images(paths[i:i + 64], preprocess).to(device)
            feats = model.encode_image(x).float()
            feats /= feats.norm(dim=-1, keepdim=True)
            out.append(feats.cpu().numpy())
    return np.concatenate(out).astype(np.float32)


def _embed_densenet(paths, device):
    import torch
    import torchvision.transforms as T
    from torchvision.models import densenet121, DenseNet121_Weights
    weights = DenseNet121_Weights.IMAGENET1K_V1
    model = densenet121(weights=weights).to(device).eval()
    feat = torch.nn.Sequential(model.features, torch.nn.AdaptiveAvgPool2d(1))
    preprocess = weights.transforms()
    out = []
    with torch.no_grad():
        for i in range(0, len(paths), 64):
            x = _load_images(paths[i:i + 64], preprocess).to(device)
            f = feat(x).flatten(1).float()
            f /= f.norm(dim=-1, keepdim=True)
            out.append(f.cpu().numpy())
    return np.concatenate(out).astype(np.float32)


# --------------------------------------------------------------------------- #
# Metrics                                                                      #
# --------------------------------------------------------------------------- #
def dcg(rels: np.ndarray, gain: str) -> float:
    g = rels if gain == "linear" else (2.0 ** rels - 1.0)
    discounts = 1.0 / np.log2(np.arange(2, len(rels) + 2))
    return float((g * discounts).sum())


def metrics_for_ranking(order: np.ndarray, rel_row: np.ndarray,
                        ks: Sequence[int], gain: str) -> Dict[str, float]:
    """order: KB indices ranked best-first for one query. rel_row: relevance to all KB."""
    ranked = rel_row[order]
    ideal = np.sort(rel_row)[::-1]
    res: Dict[str, float] = {}
    # MRR over any positive relevance
    hits = np.nonzero(ranked > 0)[0]
    res["mrr"] = 1.0 / (hits[0] + 1) if hits.size else 0.0
    for k in ks:
        topk = ranked[:k]
        res[f"recall@{k}"] = float((topk > 0).any())
        res[f"precision@{k}"] = float((topk > 0).mean())
        idcg = dcg(ideal[:k], gain)
        res[f"ndcg@{k}"] = dcg(topk, gain) / idcg if idcg > 0 else 0.0
    return res


def evaluate(sim_or_none, rel: np.ndarray, ks, gain, rng=None, seed=0) -> List[Dict]:
    """Return a per-query list of metric dicts. If sim is None -> random ranking."""
    n_q, n_d = rel.shape
    per_query = []
    if sim_or_none is None:
        r = np.random.default_rng(seed)
        for q in range(n_q):
            order = r.permutation(n_d)
            per_query.append(metrics_for_ranking(order, rel[q], ks, gain))
    else:
        order_all = np.argsort(-sim_or_none, axis=1)
        for q in range(n_q):
            per_query.append(metrics_for_ranking(order_all[q], rel[q], ks, gain))
    return per_query


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #
def cached_embed(enc: str, paths, split: str, emb_dir: Path, device: str) -> np.ndarray:
    """Embed with disk caching so re-running the eval doesn't repeat GPU work."""
    cache = emb_dir / f"{enc}_{split}.npy"
    if cache.exists():
        arr = np.load(cache)
        if arr.shape[0] == len(paths):
            print(f"[eval]   {enc}/{split}: loaded cached embeddings {arr.shape}")
            return arr
        print(f"[eval]   {enc}/{split}: cache size mismatch, recomputing")
    arr = embed_images(enc, paths, device)
    emb_dir.mkdir(parents=True, exist_ok=True)
    np.save(cache, arr)
    return arr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase0_config.yaml")
    ap.add_argument("--data-root", default=".")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    with open(args.config) as fh:
        cfg = yaml.safe_load(fh)
    metadata_dir = Path(cfg["paths"]["metadata_dir"])
    splits_dir = Path(cfg["paths"]["splits_dir"])
    out_dir = Path(cfg["paths"]["out_dir"])          # evaluation outputs
    emb_dir = Path(cfg["paths"]["embeddings_dir"])   # shared cache, own top-level folder
    per_query_dir = out_dir / "per_query"
    per_query_dir.mkdir(parents=True, exist_ok=True)
    img_root = Path(args.data_root) / cfg["paths"]["image_root"]
    ks = cfg["eval"]["k_values"]
    gain = cfg["eval"]["ndcg_gain"]

    idx = pd.read_csv(metadata_dir / "study_index.csv")
    splits = pd.read_csv(splits_dir / "splits.csv")
    df = idx.merge(splits, on="uid")
    df = df[df["has_frontal"]].copy()               # Phase 0 = frontal only

    label_cols = [c for c in idx.columns if c not in (
        "uid", "primary_label", "label_set", "num_labels",
        "has_frontal", "frontal_filename", "exclude_flag")]

    train = df[df["split"] == "train"].reset_index(drop=True)
    val = df[df["split"] == "val"].reset_index(drop=True)
    print(f"[eval] KB(train)={len(train)}  queries(val)={len(val)}")

    # graded relevance matrix via label-overlap: R = Yval @ Ytrain^T
    Yq = val[label_cols].to_numpy(np.float32)
    Yd = train[label_cols].to_numpy(np.float32)
    rel = (Yq @ Yd.T).astype(np.float32)

    train_paths = [img_root / f for f in train["frontal_filename"]]
    val_paths = [img_root / f for f in val["frontal_filename"]]

    micro_rows, macro_rows, perclass_rows = [], [], []
    for enc in cfg["eval"]["encoders"]:
        print(f"[eval] encoder: {enc}")
        if enc == "random":
            seeds = range(cfg["eval"]["random_baseline_seeds"])
            pqs = [evaluate(None, rel, ks, gain, seed=s) for s in seeds]
            per_query = [
                {m: float(np.mean([pqs[s][q][m] for s in range(len(pqs))]))
                 for m in pqs[0][0]}
                for q in range(len(val))
            ]
        else:
            d_emb = cached_embed(enc, train_paths, "train", emb_dir, args.device)
            q_emb = cached_embed(enc, val_paths, "val", emb_dir, args.device)
            sim = q_emb @ d_emb.T
            per_query = evaluate(sim, rel, ks, gain)

        pq = pd.DataFrame(per_query)
        pq.insert(0, "uid", val["uid"].values)
        pq.insert(1, "primary_label", val["primary_label"].values)
        pq.insert(2, "encoder", enc)
        pq.to_csv(per_query_dir / f"{enc}.csv", index=False)  # <- feeds analyze_results.py

        metric_cols = [c for c in pq.columns if c not in ("uid", "primary_label", "encoder")]
        micro_rows.append({"encoder": enc, **pq[metric_cols].mean().to_dict()})

        per_class = pq.groupby("primary_label")[metric_cols].mean()
        for cls, row in per_class.iterrows():
            perclass_rows.append({"encoder": enc, "primary_label": cls, **row.to_dict()})
        macro_rows.append({"encoder": enc, **per_class[metric_cols].mean().to_dict()})

    micro_df = pd.DataFrame(micro_rows)
    macro_df = pd.DataFrame(macro_rows)
    perclass_df = pd.DataFrame(perclass_rows)
    micro_df.to_csv(out_dir / "encoder_comparison_micro.csv", index=False)
    macro_df.to_csv(out_dir / "encoder_comparison_macro.csv", index=False)
    perclass_df.to_csv(out_dir / "encoder_comparison_perclass.csv", index=False)

    show = ["encoder", "recall@1", "recall@5", "recall@10", "mrr", "ndcg@10"]
    print("\n=== MICRO (all queries) ===")
    print(micro_df[show].to_string(index=False))
    print("\n=== MACRO (per-primary-class, non-Normal-sensitive) ===")
    print(macro_df[show].to_string(index=False))
    print(f"\nWrote per-query results to {per_query_dir}/  (used by analyze_results.py)")
    print("Point estimates only above. Run analyze_results.py for bootstrap CIs")
    print("and the actual GO/NO-GO decision — do not decide from this table alone.")


if __name__ == "__main__":
    main()
