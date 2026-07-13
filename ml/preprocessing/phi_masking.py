"""
phi_masking.py
====================================================================
ml/preprocessing -- PHI masking stage.

Detects burned-in text (patient name, hospital name, ID, dates, machine
annotations) on chest X-ray images via EasyOCR, then masks each detected
region with a padded solid black box. Runs before BiomedCLIP embedding.

Design decisions (see docs/methodology/development_log.md for rationale):
  - EasyOCR over PaddleOCR/Tesseract: PyTorch-native, no second DL framework
    dependency alongside the existing BiomedCLIP/torch stack.
  - Black-box masking over blur/inpainting: inpainting hallucinates pixel
    content, which conflicts with an evidence-grounded system's own premise;
    a solid box is an unambiguous "no information here" signal.
  - Confidence threshold + padding: avoids masking false-positive OCR hits
    on lung texture, and avoids a razor-sharp box edge sitting exactly on
    text boundaries (which can look like a spurious high-contrast feature
    to a ViT patch embedding).
  - No masking is applied if OCR finds nothing above threshold -- image
    passes through unmodified rather than being forced through a no-op mask.

NOTE: IU X-ray (this project's dataset) is already de-identified at the
text-report level; there is no known burned-in-PHI image subset to validate
detection recall against. This module is a deployment-readiness contribution,
not empirically validated against real PHI images. State this explicitly in
the thesis -- do not imply recall/precision was measured on this dataset.

PHIMasker/MaskedRegion/MaskingResult now live in shared/phi_masking/masker.py
(extracted there in Phase 12 Step 7) so the live backend's newly-persisted
query-image masking reuses the EXACT same implementation this offline batch
script uses -- not a second, possibly-drifting copy. Same deliberate,
one-off shared/ exception as shared/embeddings/biomedclip_embedder.py.

Usage:
    python ml/preprocessing/phi_masking.py --config ml/config/phase0_config.yaml \
        --data-root . --limit 20      # --limit for a quick dry run
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from shared.phi_masking.masker import MaskingResult, PHIMasker


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="ml/config/phase0_config.yaml")
    ap.add_argument("--data-root", default=".")
    ap.add_argument("--limit", type=int, default=None, help="process only first N frontal images (dry run)")
    ap.add_argument("--confidence-threshold", type=float, default=0.30)
    ap.add_argument("--pad-px", type=int, default=6)
    ap.add_argument("--gpu", action="store_true", default=True)
    ap.add_argument("--cpu", dest="gpu", action="store_false")
    args = ap.parse_args()

    with open(args.config) as fh:
        cfg = yaml.safe_load(fh)
    data_root = Path(args.data_root)
    metadata_dir = Path(cfg["paths"]["metadata_dir"])
    img_root = data_root / cfg["paths"]["image_root"]
    masked_dir = data_root / "ml/datasets/masked"
    masked_dir.mkdir(parents=True, exist_ok=True)
    log_dir = Path(cfg["paths"].get("out_dir", "ml/outputs/evaluation")).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    idx = pd.read_csv(metadata_dir / "study_index.csv")
    frontal = idx[idx["has_frontal"]].copy()
    if args.limit:
        frontal = frontal.head(args.limit)

    masker = PHIMasker(confidence_threshold=args.confidence_threshold,
                        pad_px=args.pad_px, gpu=args.gpu)

    results: list[MaskingResult] = []
    for _, row in frontal.iterrows():
        src = img_root / row["frontal_filename"]
        dst = masked_dir / row["frontal_filename"]
        try:
            result = masker.detect_and_mask(src, dst)
            result.uid = int(row["uid"])
            results.append(result)
        except FileNotFoundError as e:
            print(f"[phi_masking] WARN skipping {row['frontal_filename']}: {e}")

    n_masked = sum(1 for r in results if r.regions_masked > 0)
    total_regions = sum(r.regions_masked for r in results)

    # detailed per-region log (full box geometry, for exact mask reproducibility)
    log_path = log_dir / "phi_masking_log.jsonl"
    with open(log_path, "w") as fh:
        for r in results:
            fh.write(json.dumps(asdict(r)) + "\n")

    # lightweight CSV summary log -- debugging/reproducibility only, not read by
    # any downstream production step
    csv_rows = [{
        "image_id": r.uid,
        "filename": r.filename,
        "num_regions_detected": r.regions_masked,
        "confidence_scores": ";".join(str(reg.confidence) for reg in r.regions),
        "masking_applied": r.regions_masked > 0,
        "processing_time_sec": r.processing_time_sec,
    } for r in results]
    csv_path = log_dir / "phi_masking_log.csv"
    pd.DataFrame(csv_rows).to_csv(csv_path, index=False)

    print(f"[phi_masking] processed: {len(results)}")
    print(f"[phi_masking] images with >=1 region masked: {n_masked} "
          f"({n_masked/len(results):.1%})" if results else "n/a")
    print(f"[phi_masking] total regions masked: {total_regions}")
    print(f"[phi_masking] mean processing time: "
          f"{np.mean([r.processing_time_sec for r in results]):.3f}s/image" if results else "n/a")
    print(f"[phi_masking] masked images written to: {masked_dir}")
    print(f"[phi_masking] detailed per-region log (JSONL, full box geometry): {log_path}")
    print(f"[phi_masking] reproducibility summary log (CSV): {csv_path}")
    print(f"[phi_masking] NOTE: IU X-ray text is already de-identified; this dataset has no "
          f"known burned-in-PHI ground truth to validate recall against. Detections above are "
          f"whatever EasyOCR flags on already-clean images (margin markers, projection labels, "
          f"etc.) -- useful as a pipeline smoke test, not a PHI-recall measurement.")


if __name__ == "__main__":
    main()
