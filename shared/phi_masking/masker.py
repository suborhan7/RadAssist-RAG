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
  - Maximum region area (added 2026-08-19): a single detected region larger
    than `max_region_area_fraction` of the image is NOT masked. Burned-in
    PHI -- a patient name, a hospital name, an ID, a date, a machine
    annotation -- is small and sits at the margins; the Phase 1 validation
    measured mean cosine similarity 0.992 pre/post masking across the IU
    corpus precisely because every real detection was small. A detection
    covering a large share of the frame is not PHI, it is a stock-image
    watermark stamped across the picture, and blacking it out destroys the
    diagnostic field instead of protecting anyone. Found for real: a
    Shutterstock watermark on a downloaded chest X-ray produced a 363x80px
    solid box across both lungs (8.1% of a 600x633 frame), which drove the
    modality gate's chest-radiograph score from 0.3695 to 0.0259. The cap
    is a constructor parameter, not a literal, so the backend can supply it
    from settings; ml/preprocessing/phi_masking.py keeps its own CLI flag.
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
    # Detections that cleared the confidence threshold but were left UNMASKED
    # for exceeding max_region_area_fraction. Reported rather than silently
    # dropped: a caller auditing what this masker did needs to see that a
    # region was found and deliberately not covered, which is a different
    # event from finding nothing at all.
    regions_skipped_oversized: int = 0


class PHIMasker:
    """Wraps EasyOCR. Instantiate once, reuse across images (model load is expensive) --
    both ml/preprocessing/phi_masking.py's offline batch run and the live backend's
    app.state singleton (app/main.py's lifespan) follow this same "construct once" rule."""

    def __init__(
        self,
        confidence_threshold: float = 0.30,
        pad_px: int = 6,
        gpu: bool = True,
        max_region_area_fraction: float = 0.08,
    ):
        import easyocr  # deferred import: only required when this module actually runs
        self.reader = easyocr.Reader(["en"], gpu=gpu)
        self.confidence_threshold = confidence_threshold
        self.pad_px = pad_px
        if not 0 < max_region_area_fraction <= 1:
            # A zero or negative cap would mask nothing at all, and a value
            # above 1 can never be exceeded, so the control would be off in
            # both directions while still appearing to be configured.
            raise ValueError("max_region_area_fraction must be in (0, 1]")
        self.max_region_area_fraction = max_region_area_fraction

    def detect_and_mask(self, image_path: Path, out_path: Path) -> MaskingResult:
        start = time.perf_counter()
        img = cv2.imread(str(image_path))
        if img is None:
            raise FileNotFoundError(f"could not read image: {image_path}")
        h, w = img.shape[:2]

        detections = self.reader.readtext(str(image_path))
        regions: list[MaskedRegion] = []
        skipped_oversized = 0
        image_area = float(h * w)

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

            # Area cap, measured AFTER padding and clipping, because the box
            # that would actually be painted is the thing whose size matters
            # -- not the raw OCR quadrilateral before it was grown.
            region_fraction = ((x2 - x1) * (y2 - y1)) / image_area if image_area else 0.0
            if region_fraction > self.max_region_area_fraction:
                skipped_oversized += 1
                continue

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
            regions_skipped_oversized=skipped_oversized,
        )
