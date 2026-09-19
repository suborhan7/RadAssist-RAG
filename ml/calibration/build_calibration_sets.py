"""
ml/calibration/build_calibration_sets.py
====================================================================
Steps 1 to 3 of the Gate B calibration procedure in §11.2 of
docs/methodology/input_admission_modality_gate_architecture_v1.0_FROZEN.md.
Builds the positive set and the negative set on disk; measurement is
calibrate_modality_gate.py's job, not this script's.

  Step 1  positive set: held-out chest radiographs from the IU dataset,
          NOT images from the ChromaDB index
  Step 2  frontal projections AND lateral projections
  Step 3  negative set: natural photographs, other radiograph modalities,
          scanned documents, damaged images

Step 1's "do not use images from the ChromaDB index" is satisfied by the
split column, not by an ad-hoc exclusion list: ml/retrieval/build_chroma_
index.py indexed the TRAIN split only (the collection is literally named
iu_cxr_biomedclip_v1_train), so drawing positives from val and test is
exactly the held-out condition Step 1 asks for.

Preprocessing note, stated because it affects how the measured rates must
be read: positives are taken as RAW images, not the masked copies under
ml/datasets/masked/. Two reasons. First, only frontals were ever masked
(3,689 files, all frontal), so mixing masked frontals with raw laterals
would confound the frontal-vs-lateral comparison that Step 2 exists to
make. Second, Phase 1 measured the embedding impact of masking at mean
cosine 0.992 pre/post (0/50 flagged), so uniform raw preprocessing costs
essentially nothing in fidelity and buys a clean comparison.

Sourcing of the negative set
----------------------------
Three of Step 3's four sub-classes come from sources that are fully
offline and reproducible on any machine (scikit-image's bundled sample
data, and the IU dataset itself for the damaged files). The fourth --
other radiograph modalities -- has no offline source in this repository,
and is fetched from a public dataset of bone-fracture radiographs. If the
network is unavailable the script does NOT substitute anything for it: it
writes a smaller set and records the shortfall in the manifest, so the
measurement downstream reports a real gap rather than a fabricated
sub-class. Run with --no-network to skip the fetch deliberately.

Usage:
    python ml/calibration/build_calibration_sets.py --data-root . [--no-network]
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

# Public dataset of bone-fracture radiographs (hand, arm, leg, and other
# non-chest plain films), used ONLY as Step 3's "other radiograph
# modalities" sub-class. Individual files are fetched by name; nothing is
# cloned and no dataset library is required.
_BONE_XRAY_REPO = "Mahadih534/x-ray_bone-fracture-Dataset"
_BONE_XRAY_TREE = f"https://huggingface.co/api/datasets/{_BONE_XRAY_REPO}/tree/main/test/images"
_BONE_XRAY_FILE = f"https://huggingface.co/datasets/{_BONE_XRAY_REPO}/resolve/main/"

# scikit-image's bundled sample images, split by which Step 3 sub-class
# each one actually belongs to. Grouped by what the picture IS, not by
# what would be convenient: `brain` is an MRI slice and `shepp_logan_
# phantom` is a CT reconstruction phantom, so neither is a radiograph and
# both sit under other medical imaging rather than under Step 3's "other
# radiograph modalities" -- which is why the network fetch above is not
# optional-in-spirit even though the script tolerates its absence.
_SKIMAGE_NATURAL = [
    "astronaut", "cat", "chelsea", "coffee", "rocket", "camera", "coins",
    "horse", "moon", "clock", "grass", "gravel", "brick", "eagle", "lily",
    "colorwheel", "hubble_deep_field", "immunohistochemistry",
]
_SKIMAGE_OTHER_MEDICAL = ["brain", "retina", "shepp_logan_phantom", "human_mitosis", "skin"]
_SKIMAGE_DOCUMENT = ["page", "text", "logo"]


def _save(array: np.ndarray, path: Path) -> None:
    """Writes a numpy sample image as an 8-bit PNG.

    Volumes (skimage's `brain` is a stack of MRI slices) are reduced to
    their middle slice -- one representative image per source, so no
    single source can dominate the negative set by contributing dozens of
    near-identical frames.
    """
    if array.ndim == 3 and array.shape[-1] not in (3, 4):
        array = array[array.shape[0] // 2]
    if array.dtype != np.uint8:
        finite = array.astype(np.float64)
        span = finite.max() - finite.min()
        finite = (finite - finite.min()) / span if span > 0 else np.zeros_like(finite)
        array = (finite * 255).astype(np.uint8)
    Image.fromarray(array).save(path)


def _build_positives(repo_root: Path, out_dir: Path, per_projection: int, seed: int) -> list[dict]:
    """Steps 1 and 2."""
    meta = pd.read_csv(repo_root / "ml" / "datasets" / "metadata" / "master_metadata.csv")

    # Step 1: held out from the ChromaDB index. train is what was indexed.
    held_out = meta[meta["split"].isin(["val", "test"])]
    # exclude_flag marks studies Phase 1 flagged out of the pipeline; a
    # flagged study is not a fair positive because production would never
    # have embedded it either.
    held_out = held_out[~held_out["exclude_flag"].fillna(False).astype(bool)]

    image_root = repo_root / "ml" / "datasets" / "raw" / "images" / "images_normalized"
    rows: list[dict] = []

    for projection in ("Frontal", "Lateral"):
        # image_ids and projections_available are positionally aligned
        # (verified below by cross-checking the Frontal entry against the
        # independently-recorded frontal_filename column) -- that alignment
        # is the ONLY way to reach a lateral filename, since the metadata
        # has a frontal_filename column and no lateral equivalent.
        candidates: list[tuple[str, str]] = []
        for _, row in held_out.iterrows():
            ids = str(row["image_ids"]).split(";")
            projections = str(row["projections_available"]).split(";")
            if len(ids) != len(projections) or projection not in projections:
                continue
            filename = ids[projections.index(projection)]
            if projection == "Frontal" and filename != str(row["frontal_filename"]):
                # positional alignment does not hold for this row -- skip it
                # rather than guess, and let the count in the manifest show it
                continue
            if (image_root / filename).is_file():
                candidates.append((str(row["study_uid"]), filename))

        sampled = (
            pd.DataFrame(candidates, columns=["study_uid", "filename"])
            .sample(n=min(per_projection, len(candidates)), random_state=seed)
            .to_dict("records")
        )
        for item in sampled:
            destination = out_dir / projection.lower() / item["filename"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(image_root / item["filename"], destination)
            label_row = held_out[held_out["study_uid"].astype(str) == item["study_uid"]].iloc[0]
            rows.append(
                {
                    "path": str(destination.relative_to(repo_root)),
                    "set": "positive",
                    "subclass": f"chest_radiograph_{projection.lower()}",
                    "projection": projection,
                    "study_uid": item["study_uid"],
                    # Step 8 groups top-1 similarity by disease label.
                    "primary_label": label_row["primary_label"],
                }
            )
    return rows


def _fetch_other_radiographs(out_dir: Path, repo_root: Path, wanted: int) -> list[dict]:
    """Step 3's "other radiograph modalities" sub-class.

    Returns an empty list if the source is unreachable. The caller records
    the shortfall; nothing is substituted.
    """
    destination_dir = out_dir / "other_radiograph"
    destination_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    try:
        with urllib.request.urlopen(_BONE_XRAY_TREE + f"?limit={wanted}", timeout=30) as response:
            entries = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return rows

    for entry in entries:
        if entry.get("type") != "file" or not entry["path"].lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        name = Path(entry["path"]).name
        try:
            with urllib.request.urlopen(_BONE_XRAY_FILE + entry["path"], timeout=30) as response:
                payload = response.read()
            image = Image.open(io.BytesIO(payload))
            image.load()
        except Exception:
            continue
        destination = destination_dir / (Path(name).stem + ".png")
        image.convert("L").save(destination)
        rows.append(
            {
                "path": str(destination.relative_to(repo_root)),
                "set": "negative",
                "subclass": "other_radiograph_modality",
                "projection": "",
                "study_uid": "",
                "primary_label": "",
            }
        )
        if len(rows) >= wanted:
            break
    return rows


def _fetch_natural_photographs(out_dir: Path, repo_root: Path, wanted: int) -> list[dict]:
    """Widens Step 3's "natural photographs" sub-class beyond the handful
    scikit-image bundles.

    The bundled samples are a well-known, deliberately varied set, but
    there are under twenty of them and several are scientific imagery
    rather than ordinary photographs. A false-positive rate estimated on
    sixteen images has a confidence interval too wide to select a
    threshold from, so real photographs are drawn from a public photo
    service by fixed ID -- fixed, not random, so a re-run measures the
    same images and the reported rate is reproducible.

    Photograph 1080 is a close-up of strawberries: the same subject as the
    P0-1 defect this whole architecture exists to fix (§4 -- "the pipeline
    accepted a photograph of a strawberry"), and the same image the T3
    acceptance test uses, so the calibration set and the acceptance gate
    are measuring the identical failure case.
    """
    destination_dir = out_dir / "natural_photograph"
    destination_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for photo_id in range(1000, 1000 + wanted * 2):
        if len(rows) >= wanted:
            break
        try:
            request = urllib.request.Request(
                f"https://picsum.photos/id/{photo_id}/640/480",
                headers={"User-Agent": "RadAssist-RAG-Calibration/1.0"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
            image = Image.open(io.BytesIO(payload))
            image.load()
        except Exception:
            continue
        destination = destination_dir / f"photo_{photo_id}.png"
        image.convert("RGB").save(destination)
        rows.append(
            {
                "path": str(destination.relative_to(repo_root)),
                "set": "negative",
                "subclass": "natural_photograph",
                "projection": "",
                "study_uid": "",
                "primary_label": "",
            }
        )
    return rows


def _render_report_pages(repo_root: Path, out_dir: Path, wanted: int) -> list[dict]:
    """Renders real report text as page images for Step 3's "scanned
    document" sub-class. Offline; no font files beyond Pillow's default.

    A light grey page tint and a black-on-white body reproduce the gross
    appearance of a scan. The text is drawn at a size that fills a
    letter-proportioned page, because a document's signature to an image
    encoder is its layout -- dense dark lines on a light field -- far more
    than the glyph shapes.
    """
    from PIL import ImageDraw

    destination_dir = out_dir / "scanned_document"
    destination_dir.mkdir(parents=True, exist_ok=True)
    meta = pd.read_csv(repo_root / "ml" / "datasets" / "metadata" / "master_metadata.csv")
    texts = meta["full_text"].dropna().astype(str)
    texts = texts[texts.str.len() > 200].head(wanted).tolist()

    rows: list[dict] = []
    for index, text in enumerate(texts):
        page = Image.new("L", (1024, 1320), color=246)
        draw = ImageDraw.Draw(page)
        words, line, y = text.split(), "", 90
        for word in words:
            if len(line) + len(word) + 1 > 62:
                draw.text((80, y), line, fill=25)
                line, y = word, y + 34
                if y > 1230:
                    break
            else:
                line = f"{line} {word}".strip()
        if line and y <= 1230:
            draw.text((80, y), line, fill=25)
        destination = destination_dir / f"report_page_{index:02d}.png"
        page.save(destination)
        rows.append(
            {
                "path": str(destination.relative_to(repo_root)),
                "set": "negative",
                "subclass": "scanned_document",
                "projection": "",
                "study_uid": "",
                "primary_label": "",
            }
        )
    return rows


def _build_negatives(repo_root: Path, out_dir: Path, use_network: bool, seed: int) -> list[dict]:
    """Step 3."""
    import skimage.data as sample_data

    rows: list[dict] = []

    for subclass, names in (
        ("natural_photograph", _SKIMAGE_NATURAL),
        ("other_medical_imaging", _SKIMAGE_OTHER_MEDICAL),
        ("scanned_document", _SKIMAGE_DOCUMENT),
    ):
        destination_dir = out_dir / subclass
        destination_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            try:
                array = getattr(sample_data, name)()
            except Exception:
                continue
            destination = destination_dir / f"{name}.png"
            _save(np.asarray(array), destination)
            rows.append(
                {
                    "path": str(destination.relative_to(repo_root)),
                    "set": "negative",
                    "subclass": subclass,
                    "projection": "",
                    "study_uid": "",
                    "primary_label": "",
                }
            )

    if use_network:
        rows.extend(_fetch_other_radiographs(out_dir, repo_root, wanted=25))
        rows.extend(_fetch_natural_photographs(out_dir, repo_root, wanted=60))

    # Scanned documents: scikit-image bundles only `page` and `text`, so
    # the sub-class is widened with rendered pages of REAL radiology report
    # text from this project's own dataset. That is the document a
    # radiology upload form is most plausibly going to receive by mistake
    # -- a typed report scanned or photographed instead of the film -- and
    # it is the hardest document case for a medical image encoder, since
    # the words on the page are the vocabulary the encoder was trained on.
    # A generic lorem-ipsum page would make this sub-class easier than
    # reality and flatter the measured false-positive rate.
    rows.extend(_render_report_pages(repo_root, out_dir, wanted=20))

    # Damaged images: real chest radiographs truncated mid-stream. Built
    # from the dataset rather than from random bytes on purpose -- a
    # damaged file with a VALID PNG header is what A7/A8's two-open
    # sequence exists to catch, and random bytes would be caught earlier
    # by A2's signature check instead, testing the wrong control.
    #
    # These have no modality score and are not expected to: they are
    # rejected at admission, before any embedding exists. The calibration
    # reports them under the admission control, not in the score
    # distributions.
    image_root = repo_root / "ml" / "datasets" / "raw" / "images" / "images_normalized"
    damaged_dir = out_dir / "damaged"
    damaged_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted(image_root.glob("*.png"))
    rng = np.random.default_rng(seed)
    for source in rng.choice(sources, size=min(20, len(sources)), replace=False):
        payload = Path(source).read_bytes()
        destination = damaged_dir / Path(source).name
        # Keep the header and the first part of the data stream, drop the
        # rest: verify() passes, load() fails. That is precisely A8's Note.
        destination.write_bytes(payload[: len(payload) // 3])
        rows.append(
            {
                "path": str(destination.relative_to(repo_root)),
                "set": "negative",
                "subclass": "damaged_image",
                "projection": "",
                "study_uid": "",
                "primary_label": "",
            }
        )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default=".")
    parser.add_argument("--per-projection", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-network", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.data_root).resolve()
    out_dir = repo_root / "ml" / "outputs" / "calibration" / "sets"
    out_dir.mkdir(parents=True, exist_ok=True)

    positives = _build_positives(repo_root, out_dir, args.per_projection, args.seed)
    negatives = _build_negatives(repo_root, out_dir, not args.no_network, args.seed)

    manifest = pd.DataFrame(positives + negatives)
    manifest_path = repo_root / "ml" / "outputs" / "calibration" / "calibration_manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    print(f"wrote {manifest_path}")
    print(f"\ntotal images: {len(manifest)}")
    print("\nby set and sub-class:")
    print(manifest.groupby(["set", "subclass"]).size().to_string())

    if not any(row["subclass"] == "other_radiograph_modality" for row in negatives):
        print(
            "\nSHORTFALL: Step 3's 'other radiograph modalities' sub-class is EMPTY.\n"
            "  No offline source exists for it in this repository and the fetch did not\n"
            "  succeed. Nothing was substituted. The measured false-positive rate\n"
            "  downstream therefore does NOT cover non-chest plain radiographs, and must\n"
            "  be reported with that gap named."
        )


if __name__ == "__main__":
    main()
