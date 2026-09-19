"""
tests/integration/admission_fixtures.py
====================================================================
Builds the upload fixtures the T1-T21 acceptance gate of
input_admission_projection_gate_architecture_v1.1_FROZEN.md (§13) needs.

Everything except the strawberry photograph is DERIVED at call time from
the IU dataset already in this repository, rather than committed as
binary test assets. Two reasons: a truncated PNG and a decompression bomb
are both things a reviewer should be able to see constructed (a committed
"bomb.png" is an opaque blob nobody can audit), and deriving them keeps
the fixtures in step with the real images the rest of the suite uses.

The strawberry photograph is the exception and IS committed, under
tests/fixtures/. §13's T3 names it specifically -- it is the actual P0-1
defect ("the system made a report from a photograph of a strawberry",
§ scope reference) -- so the acceptance gate must not depend on a network
fetch to reproduce the defect it exists to prove is closed.
"""
from __future__ import annotations

import io
import zlib
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_IMAGE_DIR = REPO_ROOT / "ml" / "datasets" / "raw" / "images" / "images_normalized"
METADATA = REPO_ROOT / "ml" / "datasets" / "metadata" / "master_metadata.csv"
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _held_out(projection: str) -> pd.DataFrame:
    """Studies in the val/test splits carrying `projection`.

    Held out on purpose even for the acceptance tests: the ChromaDB
    collection indexes the TRAIN split, so a train image would retrieve
    itself at similarity ~1.0 and every support-category assertion would
    be measuring an artifact rather than real retrieval behavior.
    """
    meta = pd.read_csv(METADATA)
    meta = meta[meta["split"].isin(["val", "test"])]
    meta = meta[~meta["exclude_flag"].fillna(False).astype(bool)]
    return meta[meta["projections_available"].astype(str).str.contains(projection)]


def _image_for(row, projection: str) -> Path | None:
    ids = str(row["image_ids"]).split(";")
    projections = str(row["projections_available"]).split(";")
    if len(ids) != len(projections) or projection not in projections:
        return None
    candidate = RAW_IMAGE_DIR / ids[projections.index(projection)]
    return candidate if candidate.is_file() else None


def frontal_radiograph() -> Path:
    """T1: a correct frontal chest radiograph."""
    for _, row in _held_out("Frontal").iterrows():
        path = _image_for(row, "Frontal")
        if path is not None:
            return path
    pytest.skip(f"no held-out frontal radiograph found under {RAW_IMAGE_DIR}")


def lateral_radiograph() -> Path:
    """T2: a correct lateral chest radiograph."""
    for _, row in _held_out("Lateral").iterrows():
        path = _image_for(row, "Lateral")
        if path is not None:
            return path
    pytest.skip(f"no held-out lateral radiograph found under {RAW_IMAGE_DIR}")


def low_support_candidates(require_high_agreement: bool = False, limit: int = 25) -> list[Path]:
    """Several ranked candidates for low_support_radiograph(), best first.

    A list rather than one path because the calibration's measurement and
    the live pipeline's measurement are close but not identical, and the
    difference matters for selecting §7.2's high-agreement/low-support
    cell. The calibration embeds the RAW image; the live pipeline embeds
    the ADMITTED and MASKED image (§9 puts the mask before the embed), so
    the two vectors differ slightly, the retrieved neighbour set can
    differ by a case or two, and the agreement score moves with it -- a
    study measured at 0.60 agreement offline came back as 0.40 through the
    API.

    That is not a defect in either measurement. It means the calibration
    can only RANK candidates, and the caller has to confirm the cell
    against the live pipeline. Returning a ranked list lets it do that.
    """
    paths: list[Path] = []
    for _ in range(limit):
        try:
            path = low_support_radiograph(require_high_agreement, _exclude=paths)
        except BaseException:  # pytest.skip raises BaseException
            break
        paths.append(path)
    return paths


def low_support_radiograph(
    require_high_agreement: bool = False, _exclude: list[Path] | None = None
) -> Path:
    """T9/T10: a real chest radiograph whose top-1 similarity falls BELOW
    the retrieval floor.

    Selected from the Gate B calibration output rather than guessed, so
    the test asserts against a case that was actually measured to be below
    the floor -- and so this fixture cannot silently stop being a
    low-support case if the collection or the floor changes: it re-reads
    the measurement each run and skips loudly if none qualifies.

    That such cases exist is not a defect being exploited. It is DR-3's
    whole subject: a correct chest radiograph for which no retrieved case
    meets the support threshold. The measured driver here is projection --
    laterals average 0.780 top-1 against frontals' 0.964, because the
    indexed knowledge base is frontal-only.

    `require_high_agreement` selects specifically the cell §7.1's Warning
    is about: HIGH agreement together with LOW support, the combination
    where a disclaimer reading only the agreement score would report
    confidence on evidence that does not meet the support threshold. T10
    tests exactly that cell, and picking an arbitrary below-floor image
    for it is a coin flip -- the first version of this fixture returned a
    40%-agreement case and T10 skipped itself rather than testing
    anything. The agreement column comes from the same calibration run,
    computed with the backend's own LabelVotingService.
    """
    from app.core.config import settings

    measured = REPO_ROOT / "ml" / "outputs" / "calibration" / "top1_similarity_by_label.csv"
    if not measured.is_file():
        pytest.skip(f"calibration output not found at {measured}; run §11.2 first")

    frame = pd.read_csv(measured)
    below = frame[frame["top1_similarity"] < settings.RETRIEVAL_FLOOR]
    if require_high_agreement:
        if "agreement" not in frame.columns:
            pytest.skip("calibration output predates the agreement column; re-run §11.2")
        below = below[below["agreement"] >= settings.DISCLAIMER_AGREEMENT_THRESHOLD]
        # Highest agreement first: the further above the threshold, the
        # more squarely the case sits in the cell T10 is about.
        below = below.sort_values("agreement", ascending=False)
    else:
        below = below.sort_values("top1_similarity")
    if below.empty:
        pytest.skip(
            f"no calibration image has top-1 similarity below RETRIEVAL_FLOOR="
            f"{settings.RETRIEVAL_FLOOR}"
            + (" with high agreement" if require_high_agreement else "")
        )

    meta = pd.read_csv(METADATA)
    # study_uid is compared as an INTEGER, not as a string. The manifest
    # round-trips through CSV, and pandas reads a column of whole numbers
    # back as float64, so `str(uid)` here yields "3672.0" while the
    # metadata's own column yields "3672" -- a comparison that silently
    # matches nothing and turns every one of T9/T10/T11 into a skip rather
    # than a failure.
    meta_uids = meta["study_uid"].astype("int64")
    excluded = set(_exclude or ())
    for _, candidate in below.iterrows():
        rows = meta[meta_uids == int(candidate["study_uid"])]
        if rows.empty:
            continue
        path = _image_for(rows.iloc[0], str(candidate["projection"]))
        if path is not None and path not in excluded:
            return path
    pytest.skip("no source image found for any measured below-floor study")


def strawberry_photograph() -> Path:
    """T3: the strawberry photograph from the P0-1 defect."""
    path = FIXTURE_DIR / "strawberry.jpg"
    if not path.is_file():
        pytest.skip(f"strawberry fixture missing at {path}")
    return path


def text_file_named_png() -> bytes:
    """T4: a text file carrying a `.png` extension.

    Deliberately longer than UPLOAD_MIN_BYTES so that A4 (signature
    disagrees with extension) is unambiguously the control that fires. A
    short text file would ALSO trip A6, and the test would pass while
    proving nothing about A4.
    """
    return b"This is a plain text file, not an image.\n" * 800


def tiny_image() -> bytes:
    """T5: a ~2 kB image.

    A real, valid PNG -- signature correct, decodable, dimensions fine --
    so that A6 (file size below the minimum) is the ONLY control it can
    fail. The point of T5 is the size rule, not a second corrupt-file
    test. Noise rather than flat colour because a flat PNG compresses to a
    few hundred bytes, which would land under a different part of the
    curve than the 4 kB file A6's text names.
    """
    import numpy as np

    rng = np.random.default_rng(0)
    for side in range(40, 200):
        array = rng.integers(0, 256, size=(side, side), dtype="uint8")
        buffer = io.BytesIO()
        Image.fromarray(array).save(buffer, format="PNG")
        payload = buffer.getvalue()
        if 1800 <= len(payload) <= 2400:
            return payload
    raise AssertionError("could not construct a ~2 kB PNG")


def decompression_bomb_png() -> bytes:
    """T6: a PNG whose header declares a pixel count far above
    IMAGE_MAX_PIXELS, in a file of a few tens of kilobytes.

    Written byte by byte rather than through Pillow because Pillow will
    not produce this file: the whole point of a decompression bomb is that
    the DECLARED dimensions in the IHDR chunk are enormous while the
    compressed data is trivial, so materializing it the normal way would
    require actually allocating the pixels the attack is designed to make
    the victim allocate.

    The declared size is 40000x40000 = 1.6e9 pixels, twenty times
    IMAGE_MAX_PIXELS (80,000,000), in a file about 25 kB on disk. That
    ratio is the attack, and it is exactly why a file-SIZE check cannot
    catch this and A9 has to exist.

    The file is deliberately padded to sit ABOVE UPLOAD_MIN_BYTES. A first
    version of this fixture was ~4 kB and T6 failed with
    stage='admission_size' instead of 'admission_decode': §5 runs the size
    checks (A5/A6) before the decode checks (A7-A11), so the tiny bomb was
    rejected by A6 for being under the minimum size and never reached A9
    at all. The control order was right; the fixture was testing the wrong
    control. T6 requires failure AT A9, so the bomb has to be a
    plausibly-sized upload.
    """
    width = height = 40000

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            len(payload).to_bytes(4, "big")
            + kind
            + payload
            + zlib.crc32(kind + payload).to_bytes(4, "big")
        )

    ihdr = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes([8, 0, 0, 0, 0])  # 8-bit greyscale, no interlace
    )
    # ~25 kB of compressed zeros: still nothing next to 1.6e9 declared
    # pixels, but past the minimum-size gate so the decode gate is what
    # this fixture actually meets.
    idat = zlib.compress(b"\x00" * 40_000_000, level=6)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


def jpeg_with_exif() -> bytes:
    """T7: a real chest radiograph saved as a JPEG carrying EXIF.

    The EXIF is populated with a plausible patient name and description,
    because that is precisely the risk A12's Note names ("EXIF metadata
    can contain Protected Health Information") -- a test that embedded
    empty or meaningless EXIF would confirm the tags are gone without
    demonstrating that anything worth removing was ever there.
    """
    import piexif

    source = frontal_radiograph()
    with Image.open(source) as image:
        rgb = image.convert("RGB")
        buffer = io.BytesIO()
        exif = {
            "0th": {
                piexif.ImageIFD.Artist: b"Dr Test Radiologist",
                piexif.ImageIFD.ImageDescription: b"PATIENT: Abdur Rahman, DOB 1959-04-02",
                piexif.ImageIFD.Make: b"RadAssist Test Harness",
            },
            "Exif": {},
            "GPS": {},
            "1st": {},
            "thumbnail": None,
        }
        rgb.save(buffer, format="JPEG", exif=piexif.dump(exif), quality=95)
    return buffer.getvalue()
