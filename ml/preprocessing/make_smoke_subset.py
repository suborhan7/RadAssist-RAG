"""
make_smoke_subset.py
====================================================================
Builds a tiny frontal-only subset of the real splits so you can shake out
image pathing / preprocessing / VRAM before the overnight full run.

It does NOT touch the three real scripts. It writes a parallel outputs dir
(default: outputs_smoke/) containing a study_index.csv and a splits.csv that
run_encoder_eval.py can consume unchanged via --data-root/out_dir override.

Selection is stratified-ish by primary_label so the relevance matrix is not
all-zeros on the subset (the classic "nothing relevant retrieved" false alarm).

Usage:
    python scripts/make_smoke_subset.py \
        --in-dir outputs --out-dir outputs_smoke \
        --n-train 100 --n-val 30 --seed 42
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def take_stratified(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Take ~n rows spread across primary_label classes, frontal-only."""
    df = df[df["has_frontal"]].copy()
    classes = df["primary_label"].unique()
    per = max(1, n // len(classes))
    picks = (
        df.groupby("primary_label", group_keys=False)
        .apply(lambda g: g.sample(min(len(g), per), random_state=seed))
    )
    # top up to n if stratification under-filled
    if len(picks) < n:
        extra = df.drop(picks.index).sample(
            min(n - len(picks), len(df) - len(picks)), random_state=seed)
        picks = pd.concat([picks, extra])
    return picks.head(n)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", default="outputs")
    ap.add_argument("--out-dir", default="outputs_smoke")
    ap.add_argument("--n-train", type=int, default=100)
    ap.add_argument("--n-val", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    in_dir, out_dir = Path(args.in_dir), Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    idx = pd.read_csv(in_dir / "study_index.csv")
    splits = pd.read_csv(in_dir / "splits.csv")
    df = idx.merge(splits, on="uid")

    tr = take_stratified(df[df["split"] == "train"], args.n_train, args.seed)
    va = take_stratified(df[df["split"] == "val"], args.n_val, args.seed)
    keep = pd.concat([tr, va])

    idx[idx["uid"].isin(keep["uid"])].to_csv(out_dir / "study_index.csv", index=False)
    keep[["uid", "split", "cluster_id"]].sort_values("uid").to_csv(
        out_dir / "splits.csv", index=False)

    print(f"[smoke] train={len(tr)}  val={len(va)}  -> {out_dir}/")
    print(f"[smoke] train classes: {tr['primary_label'].nunique()}, "
          f"val classes: {va['primary_label'].nunique()}")
    print("[smoke] run the eval against this dir (see command below).")


if __name__ == "__main__":
    main()
