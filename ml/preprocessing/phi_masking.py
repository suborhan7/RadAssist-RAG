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

Usage:
    python ml/preprocessing/phi_masking.py --config ml/config/phase0_config.yaml \
        --data-root . --limit 20      # --limit for a quick dry run
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import time
import yaml


@dataclass
class MaskedRegion:
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    text_snippet: str  # first few chars only -- never persist full detected PHI text


@dataclass
class MaskingResult:
    uid: int
    filename: str
    regions_masked: int
    regions: list[MaskedRegion]
    skipped_no_detection: bool
    processing_time_sec: float = 0.0


class PHIMasker:
    """Wraps EasyOCR. Instantiate once, reuse across images (model load is expensive)."""

    def __init__(self, confidence_threshold: float = 0.30, pad_px: int = 6, gpu: bool = True):
        import easyocr  # deferred import: only required when this module actually runs
        self.reader = easyocr.Reader(["en"], gpu=gpu)
        self.confidence_threshold = confidence_threshold
        self.pad_px = pad_px

    def detect_and_mask(self, image_path: Path, out_path: Path) -> MaskingResult:
        start = time.perf_counter()
        img = cv2.imread(str(image_path))
        if img is None:
            raise FileNotFoundError(f"could not read image: {image_path}")
        h, w = img.shape[:2]

        detections = self.reader.readtext(str(image_path))
        regions: list[MaskedRegion] = []

        for bbox, text, conf in detections:
            if conf < self.confidence_threshold:
                continue
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            x1, x2 = int(min(xs)), int(max(xs))
            y1, y2 = int(min(ys)), int(max(ys))

            # pad, then clip to image bounds
            x1 = max(0, x1 - self.pad_px)
            y1 = max(0, y1 - self.pad_px)
            x2 = min(w, x2 + self.pad_px)
            y2 = min(h, y2 + self.pad_px)

            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 0), thickness=-1)  # solid black box
            regions.append(MaskedRegion(
                x1=x1, y1=y1, x2=x2, y2=y2, confidence=round(float(conf), 3),
                text_snippet=text[:3] + "..." if text else "",  # never store full PHI text
            ))

        skipped = len(regions) == 0
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), img)  # unmodified copy written even if nothing was masked
        elapsed = time.perf_counter() - start

        return MaskingResult(
            uid=-1, filename=image_path.name, regions_masked=len(regions),
            regions=regions, skipped_no_detection=skipped,
            processing_time_sec=round(elapsed, 4),
        )


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
