"""
ml/evaluation/diagnose_high_agreement_low_support.py
====================================================================
DIAGNOSTIC B -- the cases carrying HIGH agreement together with retrieval
support BELOW the floor.

A MEASUREMENT SCRIPT. Read-only. No production module imports it, it
writes nothing, and it changes no setting, no service and no frozen
decision. It reads two CSVs and (for the neighbour projection only) the
existing ChromaDB collection via `.get()`. Nothing is embedded, queried
for ranking, re-indexed, or migrated.

Identification of the 15 cases
------------------------------
They are the rows of the Gate B run's own per-image output,
`ml/outputs/calibration/top1_similarity_by_label.csv`, satisfying BOTH:

    agreement       >= DISCLAIMER_AGREEMENT_THRESHOLD   (0.5)
    top1_similarity <  RETRIEVAL_FLOOR                  (0.7603)

Both cut points are passed as arguments and echoed in the output, so the
selection rule is visible rather than implied. They are the same two
values the Gate B run used when it reported this cell, which is what makes
the count comparable to the 15 reported earlier.

Both columns come from that same file and are per-image measurements made
during the Gate B run: `agreement` from the backend's own
LabelVotingService over that query's retrieved cases, `top1_similarity`
from the rank-1 neighbour returned by the real collection.

Neighbour projection
--------------------
Taken from the archive's projection composition, which
diagnose_neighbour_projection.py measures directly and which this script
re-derives independently from the same read-only source. Neighbour
identities were never persisted by the Gate B run, and recovering them
would require re-running the queries; where the collection is homogeneous
in projection that is unnecessary, since every neighbour then carries the
same projection by construction. If it is not homogeneous, this reports
the neighbour projection as UNRESOLVED rather than guessing.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "backend"))

SUPPORT_CSV = _REPO_ROOT / "ml" / "outputs" / "calibration" / "top1_similarity_by_label.csv"


def _pct(count: int, total: int) -> str:
    return f"{(100.0 * count / total):.2f}%" if total else "n/a"


def _composition(frame: pd.DataFrame, title: str) -> None:
    total = len(frame)
    counts = Counter(frame["projection"].fillna("UNRESOLVED"))
    print(f"{title}  (total n={total})")
    print(f"  {'projection':<16}{'n':>8}{'pct':>10}")
    for name in ("Frontal", "Lateral"):
        print(f"  {name:<16}{counts.get(name, 0):>8}{_pct(counts.get(name, 0), total):>10}")
    for name in sorted(set(counts) - {"Frontal", "Lateral"}):
        print(f"  {name:<16}{counts[name]:>8}{_pct(counts[name], total):>10}")
    print(f"  {'TOTAL':<16}{total:>8}{_pct(total, total):>10}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--floor", type=float, default=0.7603)
    parser.add_argument("--agreement-threshold", type=float, default=0.5)
    args = parser.parse_args()

    import chromadb
    from app.core.config import settings

    if not SUPPORT_CSV.is_file():
        raise SystemExit(f"STOP: {SUPPORT_CSV} is missing; the Gate B set cannot be reproduced.")

    support = pd.read_csv(SUPPORT_CSV)

    print("=" * 78)
    print("DIAGNOSTIC B -- high-agreement / low-support cases")
    print("=" * 78)
    print(f"source:                {SUPPORT_CSV}")
    print(f"rows in source:        {len(support)}")
    print(f"RETRIEVAL_FLOOR used:  {args.floor}")
    print(f"agreement threshold:   {args.agreement_threshold}")
    print("access mode:           read-only; nothing embedded, re-indexed, or migrated")
    print()

    # neighbour projection, derived read-only from the archive
    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_PATH)
    collection = client.get_collection(settings.CHROMA_COLLECTION_NAME)
    archive = collection.get(include=["metadatas"])
    archive_projections = {str(m.get("projection")) for m in archive["metadatas"]}
    homogeneous = len(archive_projections) == 1 and "None" not in archive_projections
    neighbour_projection = next(iter(archive_projections)) if homogeneous else "UNRESOLVED"
    print(f"archive vectors: {collection.count()}; distinct projections in archive: "
          f"{sorted(archive_projections)}")
    print(f"=> top-1 neighbour projection for every row below: {neighbour_projection}"
          + ("" if homogeneous else "  (archive is mixed; not derivable)"))
    print()

    # ---------------- B1 ----------------
    print("-" * 78)
    print("B1. Identification and count")
    print("-" * 78)
    below = support[support["top1_similarity"] < args.floor]
    high_low = below[below["agreement"] >= args.agreement_threshold]
    print(f"rule: agreement >= {args.agreement_threshold} AND top1_similarity < {args.floor}")
    print(f"rows below floor (any agreement):        n={len(below)}")
    print(f"rows below floor AND high agreement:     n={len(high_low)}")
    print(f"matches the 15 reported earlier:         {len(high_low) == 15}")
    print(f"rows with missing agreement or top1:     "
          f"{int(support[['agreement', 'top1_similarity']].isna().any(axis=1).sum())}")
    print()

    # ---------------- B2 ----------------
    print("-" * 78)
    print(f"B2. The {len(high_low)} cases")
    print("-" * 78)
    detail = high_low.assign(
        study_uid=high_low["study_uid"].astype("int64"),
        top1_neighbour_projection=neighbour_projection,
    )[
        [
            "study_uid",
            "projection",
            "agreement",
            "top1_similarity",
            "primary_label",
            "top_voted_label",
            "top1_neighbour_projection",
        ]
    ].sort_values("top1_similarity")
    print(detail.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print()

    # ---------------- B3 ----------------
    print("-" * 78)
    print(f"B3. Projection composition of the {len(high_low)} high-agreement / low-support cases")
    print("-" * 78)
    _composition(high_low, "query projection")
    print()

    # ---------------- B4 ----------------
    print("-" * 78)
    print(f"B4. Projection composition of ALL {len(below)} below-floor rows")
    print("-" * 78)
    _composition(below, "query projection")
    print()

    print("-" * 78)
    print("for reference: the full support x agreement contingency (n=%d)" % len(support))
    print("-" * 78)
    table = support.assign(
        support=lambda d: d["top1_similarity"].ge(args.floor).map(
            {True: "at_or_above_floor", False: "below_floor"}
        ),
        agreement_band=lambda d: d["agreement"].ge(args.agreement_threshold).map(
            {True: "high", False: "low"}
        ),
    )
    counts = pd.crosstab(table["support"], table["agreement_band"]).reindex(
        index=["at_or_above_floor", "below_floor"], columns=["high", "low"], fill_value=0
    )
    print(counts.to_string())
    print()
    print("as percentages of all %d rows:" % len(support))
    print((100.0 * counts / len(support)).round(2).to_string())


if __name__ == "__main__":
    main()
