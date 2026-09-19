"""
ml/evaluation/measure_fnr_by_projection.py
====================================================================
MEASUREMENT 1 -- false-negative rate at two modality thresholds, split by
projection.

A MEASUREMENT SCRIPT. It reads. It changes nothing: no production module
imports it, it writes no file under backend/ or ml/config/, and it does
not read or alter MODALITY_THRESHOLD -- both thresholds are command-line
arguments, so running this cannot depend on, or disturb, the deployed
setting (which stays at its provisional 0.60).

Set identification (reproducibility)
------------------------------------
The positive set is the EXACT set used by the Gate B run, identified by
`ml/outputs/calibration/calibration_manifest.csv`. That file holds one row
per image with its repo-relative `path`, `set`, `subclass` and
`projection`; the 600 positive rows are the 300 frontal and 300 lateral
held-out IU studies drawn by
`ml/calibration/build_calibration_sets.py --per-projection 300 --seed 42`.
The manifest is the identifier of record, not the seed: the seed
reproduces the DRAW, the manifest names the images that were actually
drawn and scored.

Modality scores are reused from `modality_scores.csv`, which is the Gate B
run's own per-image output and is row-aligned to the manifest (asserted
below). `--verify` re-runs the real ModalityGateService over the same
images and reports the maximum absolute difference against the stored
scores, so the reuse can be shown to be faithful rather than assumed.

A false negative is a positive-set image whose modality score is BELOW the
threshold -- a true chest radiograph the gate would refuse.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "backend"))

CALIBRATION_DIR = _REPO_ROOT / "ml" / "outputs" / "calibration"
MANIFEST = CALIBRATION_DIR / "calibration_manifest.csv"
SCORES = CALIBRATION_DIR / "modality_scores.csv"

# Below this, a rate is reported with its count and marked low-confidence.
SMALL_STRATUM = 30


def _load() -> pd.DataFrame:
    """Loads the Gate B sets and asserts the two files describe the same
    images in the same order. If they ever diverge, the scores could be
    silently attributed to the wrong rows, so this fails loudly rather
    than measuring something that looks plausible."""
    for path in (MANIFEST, SCORES):
        if not path.is_file():
            raise SystemExit(
                f"STOP: {path} is missing. The Gate B sets cannot be reproduced "
                f"exactly; re-run ml/calibration/build_calibration_sets.py and "
                f"calibrate_modality_gate.py before measuring."
            )

    manifest = pd.read_csv(MANIFEST)
    scores = pd.read_csv(SCORES)
    if list(manifest["path"]) != list(scores["path"]):
        raise SystemExit(
            "STOP: calibration_manifest.csv and modality_scores.csv do not "
            "describe the same images in the same order. The Gate B set cannot "
            "be reproduced exactly."
        )

    missing = [p for p in manifest["path"] if not (_REPO_ROOT / p).is_file()]
    if missing:
        raise SystemExit(
            f"STOP: {len(missing)} image(s) named in the manifest are no longer on "
            f"disk, e.g. {missing[:3]}. The Gate B set cannot be reproduced exactly."
        )
    return scores


def _verify(scores: pd.DataFrame) -> None:
    """Re-scores the same images through the real ModalityGateService and
    reports the largest disagreement with the stored Gate B scores."""
    from app.core.config import settings
    from app.services.modality_gate_service import ModalityGateService
    from shared.embeddings.biomedclip_embedder import BiomedCLIPEmbedder

    class _Adapter:
        def __init__(self, embedder):
            self._embedder = embedder

        def embed_text(self, text: str) -> list[float]:
            return self._embedder.embed_texts([text])[0].tolist()

        def embed_image(self, image_path: str) -> list[float]:
            return self._embedder.embed_images([image_path])[0].tolist()

    embedder = BiomedCLIPEmbedder()
    gate = ModalityGateService(
        embedder=_Adapter(embedder),
        positive_prompts=settings.modality_prompts_positive,
        negative_prompts=settings.modality_prompts_negative,
        softmax_temperature=settings.MODALITY_SOFTMAX_TEMPERATURE,
        modality_threshold=settings.MODALITY_THRESHOLD,
        retrieval_floor=settings.RETRIEVAL_FLOOR,
    )

    scored = scores[scores["modality_score"].notna()]
    vectors = embedder.embed_images([str(_REPO_ROOT / p) for p in scored["path"]])
    recomputed = np.array([gate.score(v.tolist()) for v in vectors])
    delta = np.abs(recomputed - scored["modality_score"].to_numpy())

    print(f"[verify] re-scored {len(scored)} images through ModalityGateService")
    print(f"[verify] max |recomputed - stored| = {delta.max():.3e}")
    print(f"[verify] mean |recomputed - stored| = {delta.mean():.3e}")
    print(f"[verify] rows differing by more than 1e-6: {int((delta > 1e-6).sum())}")
    print()


def _rates(positives: pd.DataFrame, thresholds: list[float]) -> pd.DataFrame:
    rows = []
    for projection in ("Frontal", "Lateral"):
        stratum = positives[positives["projection"] == projection]
        for threshold in thresholds:
            false_negatives = int((stratum["modality_score"] < threshold).sum())
            n = len(stratum)
            rows.append(
                {
                    "projection": projection,
                    "threshold": threshold,
                    "n": n,
                    "false_negatives": false_negatives,
                    "FNR": false_negatives / n if n else float("nan"),
                    "low_confidence": "YES (n<30)" if n < SMALL_STRATUM else "",
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    # Both thresholds are arguments. Nothing here reads MODALITY_THRESHOLD.
    parser.add_argument("--threshold", type=float, default=0.82)
    parser.add_argument("--compare-threshold", type=float, default=0.60)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    scores = _load()

    print("=" * 78)
    print("MEASUREMENT 1 -- false-negative rate by projection")
    print("=" * 78)
    print(f"positive/negative sets identified by: {MANIFEST}")
    print(f"modality scores reused from:          {SCORES}")
    print(f"manifest rows: {len(scores)}  (all paths verified present on disk)")
    print()

    if args.verify:
        _verify(scores)

    positives = scores[(scores["set"] == "positive") & scores["modality_score"].notna()]
    print(f"positive set: n={len(positives)} scored "
          f"(admitted and scored / {int((scores['set'] == 'positive').sum())} in manifest)")
    print("projection field source: manifest `projection` column, taken from the "
          "dataset's own\n  projections_available field at set-build time")
    print()

    table = _rates(positives, [args.threshold, args.compare_threshold])
    print(f"--- FNR at {args.threshold} and {args.compare_threshold}, by projection ---")
    print(table.to_string(index=False))
    print()

    print(f"--- every false negative at threshold {args.threshold} ---")
    misses = positives[positives["modality_score"] < args.threshold].sort_values("modality_score")
    if misses.empty:
        print("(none)")
    else:
        print(f"count: {len(misses)}")
        print(
            misses[["projection", "study_uid", "modality_score", "path"]]
            .to_string(index=False, float_format=lambda v: f"{v:.8f}")
        )
    print()

    at_compare = positives[positives["modality_score"] < args.compare_threshold]
    print(f"(for reference, false negatives at {args.compare_threshold}: {len(at_compare)})")


if __name__ == "__main__":
    main()
