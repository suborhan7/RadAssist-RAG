"""
shared/phi_masking/masker.py
====================================================================
PHIMasker, extracted from ml/preprocessing/phi_masking.py (Phase 1) into
shared/ so both the offline ml/ pipeline and the live backend (Phase 12
Step 7) import the identical implementation -- same deliberate,
one-off exception to the frozen "ml/ and backend/ never import each
other" rule that shared/embeddings/biomedclip_embedder.py already
established (see CLAUDE.md's "shared/ vs ml/ boundary" section). Two
copies would risk silent drift between how the offline training corpus
was masked and how a live-uploaded query image gets masked before this
phase persists it for redisplay -- exactly the same "identical
implementation, not a second copy" reasoning as the embedder.

Detects burned-in text (patient name, hospital name, ID, dates, machine
annotations) on chest X-ray images via EasyOCR, then masks each detected
region with a padded solid black box.

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
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import cv2


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
    """Wraps EasyOCR. Instantiate once, reuse across images (model load is expensive) --
    both ml/preprocessing/phi_masking.py's offline batch run and the live backend's
    app.state singleton (app/main.py's lifespan) follow this same "construct once" rule."""

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
