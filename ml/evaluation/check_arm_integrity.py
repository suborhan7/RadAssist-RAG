"""
ml/evaluation/check_arm_integrity.py
====================================================================
Phase 21 pre-scoring integrity gate. Runs BEFORE any scoring and
answers the two questions that determine whether the paired design is
valid at all:

1. Are the retrieved uid sets identical across arms, for every case?
   Retrieval is upstream of the evidence-mode branch -- all three arms
   call the same /retrieve and differ only in how the result is
   rendered into the prompt (§2.2). Identical retrieval is therefore a
   PREDICTION of the design, not an assumption it is entitled to make.
   If it fails, the arms differ in more than evidence and the contrast
   does not measure what it claims to.

2. Did every arm complete the same cases?
   The paired bootstrap resamples case indices and applies them to both
   arms at once. That requires one shared case set. An arm that
   completed fewer cases silently changes the estimand.

This script DOES NOT repair either problem. It reports and, on
failure, exits non-zero -- the handling of an unequal case set is a
methodological decision, not something a script should quietly make by
dropping rows.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ARMS = ("full", "labels_only", "empty")


def load_arm(data_root: Path, arm: str) -> pd.DataFrame:
    path = data_root / f"ml/outputs/evaluation/generation_arm_{arm}/per_case_results.csv"
    if not path.is_file():
        raise SystemExit(f"[check_arm_integrity] missing results for arm '{arm}': {path}")
    df = pd.read_csv(path, dtype={"study_uid": str, "retrieved_uids": str})
    df["arm"] = arm
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=".")
    ap.add_argument("--arms", default=",".join(ARMS))
    args = ap.parse_args()

    data_root = Path(args.data_root)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    frames = {arm: load_arm(data_root, arm) for arm in arms}

    problems: list[str] = []

    # ---- 2. completion counts (reported first: it frames everything else) ----
    print("=" * 68)
    print("COMPLETION COUNTS PER ARM")
    print("=" * 68)
    completed: dict[str, set[str]] = {}
    for arm, df in frames.items():
        ok = df[df["status"] == "completed"]
        completed[arm] = set(ok["study_uid"])
        n_fail = len(df) - len(ok)
        print(f"  {arm:12} attempted={len(df):4}  completed={len(ok):4}  failed={n_fail:4}")
        if n_fail:
            # Every failure, with its reason string -- not a count.
            for _, r in df[df["status"] != "completed"].iterrows():
                print(f"      FAIL uid={r['study_uid']}  reason={str(r['reason'])[:160]}")

    sizes = {arm: len(s) for arm, s in completed.items()}
    if len(set(sizes.values())) != 1:
        problems.append(f"unequal completion counts across arms: {sizes}")

    shared = set.intersection(*completed.values()) if completed else set()
    union = set.union(*completed.values()) if completed else set()
    print(f"\n  shared by all arms : {len(shared)}")
    print(f"  completed in >=1   : {len(union)}")
    if len(shared) != len(union):
        problems.append(
            f"case sets differ: {len(union) - len(shared)} case(s) completed in some arms but not all"
        )
        for uid in sorted(union - shared):
            missing = [a for a in arms if uid not in completed[a]]
            print(f"      uid={uid} missing from: {', '.join(missing)}")

    # ---- 1. retrieved uid identity, per case ----
    print()
    print("=" * 68)
    print("RETRIEVED UID IDENTITY ACROSS ARMS")
    print("=" * 68)
    ref_arm = arms[0]
    ref_map = dict(zip(frames[ref_arm]["study_uid"], frames[ref_arm]["retrieved_uids"].fillna("")))
    mismatches = []
    # Checked over every case present in both arms, INCLUDING failed ones:
    # retrieval happens before generation, so a case that failed to generate
    # still has a retrieval result worth comparing.
    for arm in arms[1:]:
        this_map = dict(zip(frames[arm]["study_uid"], frames[arm]["retrieved_uids"].fillna("")))
        for uid, ref_uids in ref_map.items():
            if uid not in this_map:
                continue
            if this_map[uid] != ref_uids:
                mismatches.append({
                    "study_uid": uid, "arm": arm,
                    f"{ref_arm}_uids": ref_uids, f"{arm}_uids": this_map[uid],
                })
    n_compared = sum(
        1 for arm in arms[1:] for uid in ref_map if uid in set(frames[arm]["study_uid"])
    )
    print(f"  pairwise case comparisons vs '{ref_arm}': {n_compared}")
    if mismatches:
        problems.append(f"{len(mismatches)} case(s) retrieved different uids across arms")
        print(f"  MISMATCHES: {len(mismatches)}")
        for m in mismatches:
            print(f"      uid={m['study_uid']} arm={m['arm']}")
            print(f"        {ref_arm:12}: {m[f'{ref_arm}_uids']}")
            print(f"        {m['arm']:12}: {m[f'{m['arm']}_uids']}")
    else:
        print("  MISMATCHES: 0 -- retrieved uid sets identical across all arms, every case")

    out = data_root / "ml/outputs/evaluation/phase21_arm_integrity.json"
    out.write_text(json.dumps({
        "arms": arms,
        "attempted": {a: int(len(df)) for a, df in frames.items()},
        "completed": {a: int(len(s)) for a, s in completed.items()},
        "shared_by_all_arms": len(shared),
        "retrieval_mismatches": mismatches,
        "problems": problems,
    }, indent=2), encoding="utf-8")
    print(f"\n[check_arm_integrity] wrote {out}")

    print()
    print("=" * 68)
    if problems:
        print("RESULT: NOT CLEAR TO SCORE")
        for p in problems:
            print(f"  - {p}")
        print("=" * 68)
        raise SystemExit(1)
    print("RESULT: CLEAR TO SCORE -- equal case sets, identical retrieval")
    print("=" * 68)


if __name__ == "__main__":
    main()
