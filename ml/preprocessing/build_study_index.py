"""
build_study_index.py
====================================================================
Phase 0, step 1.

Reads the study-level reports CSV and the image-level projections CSV,
applies the curated label taxonomy (config/label_mapping.yaml), selects one
deterministic frontal image per study, and writes a single master index:

    outputs/study_index.csv

Columns:
    uid, primary_label, label_set, num_labels, has_frontal, frontal_filename,
    exclude_flag, <one binary column per curated class>

The code is agnostic to the taxonomy: it is fully driven by the YAML mapping.
No labels are hardcoded here.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pandas as pd
import yaml


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_term_index(mapping: dict) -> Tuple[Dict[str, str], Set[str], Set[str], List[str]]:
    """Invert the taxonomy into: raw_term -> class, drop set, exclude set, class order."""
    term_to_class: Dict[str, str] = {}
    class_order: List[str] = [mapping["normal_class"]]
    for cls, terms in mapping["classes"].items():
        class_order.append(cls)
        for t in terms:
            term_to_class[t.strip()] = cls
    class_order.append(mapping["other_class"])
    drop_terms = {t.strip() for t in mapping.get("drop_terms", [])}
    exclude_terms = {t.strip() for t in mapping.get("exclude_flags", [])}
    return term_to_class, drop_terms, exclude_terms, class_order


def resolve_labels(
    raw: str,
    term_to_class: Dict[str, str],
    drop_terms: Set[str],
    exclude_terms: Set[str],
    normal_class: str,
    other_class: str,
    enforce_normal_exclusive: bool,
    unmapped_counter: Counter,
) -> Tuple[Set[str], bool]:
    """Map one semicolon-separated Problems string to a set of curated classes."""
    labels: Set[str] = set()
    exclude_flag = False
    terms = [p.strip() for p in str(raw).split(";") if p.strip()]
    for t in terms:
        if t in exclude_terms:
            exclude_flag = True
            continue
        if t.lower() == normal_class.lower():
            labels.add(normal_class)
            continue
        if t in drop_terms:
            continue
        if t in term_to_class:
            labels.add(term_to_class[t])
            continue
        # genuine but unlisted pathology -> Other, and log it for review
        unmapped_counter[t] += 1
        labels.add(other_class)

    if not labels:
        # all terms were dropped/anatomy and it was not tagged normal -> Other
        labels.add(other_class)

    if enforce_normal_exclusive and normal_class in labels and len(labels) > 1:
        labels.discard(normal_class)

    return labels, exclude_flag


def select_frontal(projections: pd.DataFrame) -> Dict[int, str]:
    """Deterministically pick one frontal filename per uid (lexicographically first)."""
    frontal = projections[projections["projection"] == "Frontal"].copy()
    frontal = frontal.sort_values(["uid", "filename"])
    return frontal.groupby("uid")["filename"].first().to_dict()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase0_config.yaml")
    ap.add_argument("--data-root", default=".", help="dir containing the CSV files")
    args = ap.parse_args()

    cfg = load_yaml(Path(args.config))
    data_root = Path(args.data_root)
    metadata_dir = Path(cfg["paths"]["metadata_dir"])
    metadata_dir.mkdir(parents=True, exist_ok=True)

    mapping = load_yaml(Path(cfg["paths"]["label_mapping"]))
    normal_class = mapping["normal_class"]
    other_class = mapping["other_class"]
    term_to_class, drop_terms, exclude_terms, class_order = build_term_index(mapping)

    reports = pd.read_csv(data_root / cfg["paths"]["reports_csv"])
    projections = pd.read_csv(data_root / cfg["paths"]["projections_csv"])
    frontal_map = select_frontal(projections)

    # global label frequencies drive the primary-label choice (rarest present = primary)
    unmapped: Counter = Counter()
    per_study_labels: Dict[int, Set[str]] = {}
    per_study_exclude: Dict[int, bool] = {}
    for _, row in reports.iterrows():
        labels, ex = resolve_labels(
            row["Problems"], term_to_class, drop_terms, exclude_terms,
            normal_class, other_class, mapping.get("enforce_normal_exclusive", True), unmapped,
        )
        per_study_labels[int(row["uid"])] = labels
        per_study_exclude[int(row["uid"])] = ex

    label_freq: Counter = Counter()
    for labs in per_study_labels.values():
        label_freq.update(labs)

    def primary_of(labs: Set[str]) -> str:
        # rarest present label is the most informative for stratification diagnostics
        return min(labs, key=lambda l: label_freq[l])

    records = []
    for uid, labs in per_study_labels.items():
        rec = {
            "uid": uid,
            "primary_label": primary_of(labs),
            "label_set": ";".join(sorted(labs)),
            "num_labels": len(labs),
            "has_frontal": uid in frontal_map,
            "frontal_filename": frontal_map.get(uid, ""),
            "exclude_flag": per_study_exclude[uid],
        }
        for cls in class_order:
            rec[cls] = int(cls in labs)
        records.append(rec)

    df = pd.DataFrame(records).sort_values("uid")
    out_path = metadata_dir / "study_index.csv"
    df.to_csv(out_path, index=False)

    # ---- reporting -------------------------------------------------------
    print(f"[build_study_index] studies: {len(df)}")
    print(f"[build_study_index] with frontal: {df.has_frontal.sum()}  "
          f"(no-frontal, Phase-0-excluded: {(~df.has_frontal).sum()})")
    print(f"[build_study_index] flagged (technical quality): {df.exclude_flag.sum()}")
    print(f"[build_study_index] wrote {out_path}")
    print("\nPer-class study counts (multi-label, so sum > n):")
    dist = pd.DataFrame(
        {"class": class_order, "count": [int(df[c].sum()) for c in class_order]}
    ).sort_values("count", ascending=False)
    print(dist.to_string(index=False))
    print(f"\nLabel-cardinality (labels per study): mean={df.num_labels.mean():.2f}, "
          f"max={df.num_labels.max()}")
    if unmapped:
        print("\nUnmapped Problems terms routed to Other (review these):")
        for term, n in unmapped.most_common():
            print(f"   {n:5d}  {term}")


if __name__ == "__main__":
    main()
