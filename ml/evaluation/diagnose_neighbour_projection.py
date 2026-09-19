"""
ml/evaluation/diagnose_neighbour_projection.py
====================================================================
DIAGNOSTIC A -- projection of the neighbours returned for lateral queries,
read against the projection composition of the archive itself.

A MEASUREMENT SCRIPT. Read-only. No production module imports it, it
writes nothing, it changes no setting and no frozen decision. It opens the
existing ChromaDB collection with `.get()` and `.count()` only -- it never
adds, upserts, deletes, or re-indexes -- and it does not embed anything.

How the neighbour projections are obtained, and why no query is run
-------------------------------------------------------------------
The Gate B calibration recorded each query's top-1 SIMILARITY but not the
IDENTITY of any neighbour (top1_similarity_by_label.csv has no neighbour
uid column). Re-running the 600 queries would require embedding the 600
query images, which this task forbids, and the cached Phase 2 embeddings
cannot stand in for them: those are vectors of the MASKED FRONTAL image
per study, while the calibration queried with raw frontal and raw lateral
images, so they are different vectors of a different image set.

So A1, A2, A4 and A5 are derived from the archive's own composition
instead, which is a stronger statement than a sample of queries would be:
if every vector in the collection carries one projection, then every
neighbour any query can possibly return carries that projection, for all
queries at once. A0 establishes that composition and the script REFUSES to
derive anything if the archive turns out to be mixed -- in that case the
neighbour projections genuinely would require running the queries, and
this prints a stop notice instead of guessing.

Projection resolution
---------------------
Reported in full by step P0 below: `projection` is present in the ChromaDB
vector metadata, so the archive side needs no join. It is nevertheless
cross-checked against `ml/datasets/raw/indiana_projections.csv` by joining
on the filename in each vector's `image_path`, and any vector whose
projection cannot be resolved by either route is counted and reported, not
dropped.
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

PROJECTIONS_CSV = _REPO_ROOT / "ml" / "datasets" / "raw" / "indiana_projections.csv"
SUPPORT_CSV = _REPO_ROOT / "ml" / "outputs" / "calibration" / "top1_similarity_by_label.csv"
MANIFEST_CSV = _REPO_ROOT / "ml" / "outputs" / "calibration" / "calibration_manifest.csv"


def _pct(count: int, total: int) -> str:
    return f"{(100.0 * count / total):.2f}%" if total else "n/a"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    import chromadb
    from app.core.config import settings

    print("=" * 78)
    print("DIAGNOSTIC A -- neighbour projection for lateral queries")
    print("=" * 78)
    print(f"collection:   {settings.CHROMA_COLLECTION_NAME}")
    print(f"persist path: {settings.CHROMA_PERSIST_PATH}")
    print(f"positive set: {MANIFEST_CSV}")
    print(f"top-1 sims:   {SUPPORT_CSV}")
    print("access mode:  read-only (.count() / .get() only; no add, upsert, delete,")
    print("              re-index, or embedding of any kind)")
    print()

    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_PATH)
    collection = client.get_collection(settings.CHROMA_COLLECTION_NAME)
    total_vectors = collection.count()
    stored = collection.get(include=["metadatas"])
    metadatas = stored["metadatas"]

    # ---------------- P0: precondition ----------------
    print("-" * 78)
    print("P0. PRECONDITION -- is projection stored in the ChromaDB vector metadata?")
    print("-" * 78)
    keys = sorted(metadatas[0].keys())
    has_projection = "projection" in keys
    print(f"metadata keys present on indexed vectors: {keys}")
    print(f"'projection' present in vector metadata: {has_projection}")
    print()

    projections_csv = pd.read_csv(PROJECTIONS_CSV)
    by_filename = dict(zip(projections_csv["filename"], projections_csv["projection"]))

    from_metadata: list[str | None] = []
    from_join: list[str | None] = []
    for meta in metadatas:
        value = meta.get("projection")
        from_metadata.append(str(value) if value not in (None, "") else None)
        filename = Path(str(meta.get("image_path", ""))).name
        from_join.append(by_filename.get(filename))

    unresolved_metadata = sum(1 for v in from_metadata if v is None)
    unresolved_join = sum(1 for v in from_join if v is None)
    unresolved_both = sum(
        1 for a, b in zip(from_metadata, from_join) if a is None and b is None
    )
    disagreements = sum(
        1 for a, b in zip(from_metadata, from_join)
        if a is not None and b is not None and a != b
    )

    print(f"projection source used for the archive: "
          f"{'ChromaDB vector metadata' if has_projection else 'JOIN on indiana_projections.csv'}")
    print(f"cross-check join file: {PROJECTIONS_CSV} "
          f"({len(projections_csv)} rows, joined on image_path filename)")
    print(f"  vectors with no projection in metadata:        {unresolved_metadata}")
    print(f"  vectors unresolvable by the filename join:     {unresolved_join}")
    print(f"  vectors unresolvable by EITHER route:          {unresolved_both}")
    print(f"  vectors where the two routes DISAGREE:         {disagreements}")
    print()

    resolved = [a if a is not None else b for a, b in zip(from_metadata, from_join)]

    # ---------------- A0: archive base rate ----------------
    print("-" * 78)
    print("A0. Projection composition of the retrievable archive (base rate)")
    print("-" * 78)
    counts = Counter(v if v is not None else "UNRESOLVED" for v in resolved)
    print(f"collection.count()            = {total_vectors}")
    print(f"metadata records retrieved    = {len(metadatas)}")
    print()
    print(f"{'projection':<14}{'n':>8}{'pct':>10}")
    for name in ("Frontal", "Lateral"):
        print(f"{name:<14}{counts.get(name, 0):>8}{_pct(counts.get(name, 0), len(resolved)):>10}")
    for name in sorted(set(counts) - {"Frontal", "Lateral"}):
        print(f"{name:<14}{counts[name]:>8}{_pct(counts[name], len(resolved)):>10}")
    print(f"{'TOTAL':<14}{len(resolved):>8}{_pct(len(resolved), len(resolved)):>10}")
    print()

    archive_projections = {v for v in resolved if v is not None}
    homogeneous = len(archive_projections) == 1 and unresolved_both == 0
    only = next(iter(archive_projections)) if homogeneous else None

    if not homogeneous:
        print("STOP: the archive is NOT homogeneous in projection (or some vectors are")
        print("unresolved). A1, A2, A4 and A5 cannot be derived from the base rate and")
        print("would require re-running the 600 retrieval queries, which requires")
        print("embedding the query images -- forbidden by this task. Reporting A0 and A3")
        print("only.")
        print()
    else:
        print(f"Every indexed vector has projection = {only!r}, and 0 vectors are")
        print(f"unresolved. Therefore every neighbour returned by ANY query against this")
        print(f"collection has projection {only!r}, at every rank. A1, A2, A4 and A5")
        print(f"below follow from this by construction -- no query is executed and")
        print(f"nothing is embedded.")
        print()

    # ---------------- load the positive set ----------------
    support = pd.read_csv(SUPPORT_CSV)
    lateral = support[support["projection"] == "Lateral"]
    frontal = support[support["projection"] == "Frontal"]
    unresolved_queries = int(support["projection"].isna().sum()) + int(
        (~support["projection"].isin(["Frontal", "Lateral"])).sum()
    )

    print("-" * 78)
    print("query-side projection resolution")
    print("-" * 78)
    print(f"positive-set rows:            {len(support)}")
    print(f"  lateral queries:            {len(lateral)}")
    print(f"  frontal queries:            {len(frontal)}")
    print(f"  queries with UNRESOLVED projection: {unresolved_queries}")
    print("(query projection comes from the calibration manifest's `projection` column,")
    print(" itself taken from the dataset projection field at set-build time)")
    print()

    # ---------------- A1 ----------------
    print("-" * 78)
    print("A1. Top-1 neighbour projection, LATERAL queries")
    print("-" * 78)
    if homogeneous:
        n = len(lateral)
        print(f"{'neighbour projection':<24}{'n':>8}{'pct':>10}")
        for name in ("Frontal", "Lateral"):
            c = n if name == only else 0
            print(f"{name:<24}{c:>8}{_pct(c, n):>10}")
        print(f"{'TOTAL':<24}{n:>8}{_pct(n, n):>10}")
        print(f"unresolved neighbours: 0")
    else:
        print("not derivable -- see STOP above")
    print()

    # ---------------- A2 ----------------
    print("-" * 78)
    print("A2. Top-1 neighbour projection, FRONTAL queries (control)")
    print("-" * 78)
    if homogeneous:
        n = len(frontal)
        print(f"{'neighbour projection':<24}{'n':>8}{'pct':>10}")
        for name in ("Frontal", "Lateral"):
            c = n if name == only else 0
            print(f"{name:<24}{c:>8}{_pct(c, n):>10}")
        print(f"{'TOTAL':<24}{n:>8}{_pct(n, n):>10}")
        print(f"unresolved neighbours: 0")
    else:
        print("not derivable -- see STOP above")
    print()

    # ---------------- A3 ----------------
    print("-" * 78)
    print("A3. Top-1 similarity for LATERAL queries, split by neighbour projection")
    print("-" * 78)
    if homogeneous:
        rows = []
        for name in ("Frontal", "Lateral"):
            group = lateral["top1_similarity"] if name == only else lateral["top1_similarity"].iloc[0:0]
            rows.append(
                {
                    "neighbour_projection": name,
                    "n": int(group.notna().sum()),
                    "min": group.min() if len(group) else float("nan"),
                    "p25": group.quantile(0.25) if len(group) else float("nan"),
                    "median": group.median() if len(group) else float("nan"),
                    "p75": group.quantile(0.75) if len(group) else float("nan"),
                    "max": group.max() if len(group) else float("nan"),
                }
            )
        print(pd.DataFrame(rows).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
        print()
        print("(the lateral-query -> lateral-neighbour stratum is empty because the")
        print(" archive contains no lateral vectors; n=0 is reported rather than omitted)")
    else:
        print("not derivable -- see STOP above")
    print()

    # ---------------- A4 ----------------
    print("-" * 78)
    print(f"A4. Projection composition of the FULL top-{args.top_k} neighbour set, LATERAL queries")
    print("-" * 78)
    if homogeneous:
        n_queries = len(lateral)
        available = min(args.top_k, total_vectors)
        total_neighbours = n_queries * available
        print(f"lateral queries:                 {n_queries}")
        print(f"neighbours requested per query:  {args.top_k}")
        print(f"neighbours available per query:  {available} "
              f"(collection holds {total_vectors} vectors)")
        print(f"total neighbours returned:       {total_neighbours}")
        print()
        print(f"{'neighbour projection':<24}{'n':>10}{'pct':>10}")
        for name in ("Frontal", "Lateral"):
            c = total_neighbours if name == only else 0
            print(f"{name:<24}{c:>10}{_pct(c, total_neighbours):>10}")
        print(f"{'TOTAL':<24}{total_neighbours:>10}{_pct(total_neighbours, total_neighbours):>10}")
        print(f"unresolved neighbours: 0")
    else:
        print("not derivable -- see STOP above")
    print()

    # ---------------- A5 ----------------
    print("-" * 78)
    print(f"A5. Lateral queries with ZERO lateral neighbours anywhere in their top-{args.top_k}")
    print("-" * 78)
    if homogeneous:
        n_queries = len(lateral)
        zero = n_queries if only != "Lateral" else 0
        print(f"{'':<44}{'n':>8}{'pct':>10}")
        print(f"{'lateral queries with 0 lateral neighbours':<44}{zero:>8}{_pct(zero, n_queries):>10}")
        print(f"{'lateral queries with >=1 lateral neighbour':<44}"
              f"{n_queries - zero:>8}{_pct(n_queries - zero, n_queries):>10}")
        print(f"{'TOTAL lateral queries':<44}{n_queries:>8}{_pct(n_queries, n_queries):>10}")
    else:
        print("not derivable -- see STOP above")


if __name__ == "__main__":
    main()
