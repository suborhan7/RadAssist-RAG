"""
Unit tests for ImageAdmissionService -- requirements A1 to A17 of
input_admission_projection_gate_architecture_v1.1_FROZEN.md §5.

A1-A13 are the file checks (§5.1 to §5.4). A14-A17 are the declared
projection (§5.5, new in v1.1) and are covered at the end of this file.

One test per requirement where the requirement is separately observable,
so a failure names the control that broke rather than "admission is
broken". Fast: pure bytes in, bytes out, no model, no database, no HTTP.

The service is constructed with EXPLICIT bounds here rather than from
`settings`. These tests are about the logic of each control, not about
today's configured values -- reading settings would make them re-fail
every time a bound is recalibrated, which is exactly the coupling §11.1's
"put all values in the settings object" rule exists to avoid.
"""
from __future__ import annotations

import io
import zlib

import numpy as np
import pytest
from PIL import Image

from app.services.exceptions import (
    ImageTooLargeError,
    InputAdmissionError,
    InvalidImageError,
    LateralProjectionError,
    UnsupportedImageFormatError,
)
from app.services.image_admission_service import ImageAdmissionService

ALLOWED = (".png", ".jpg", ".jpeg")
MAX_BYTES = 20 * 1024 * 1024
MIN_BYTES = 20 * 1024
MIN_DIM = 256
MAX_DIM = 8192
MAX_PIXELS = 80_000_000


@pytest.fixture
def service() -> ImageAdmissionService:
    return ImageAdmissionService(
        allowed_extensions=ALLOWED,
        max_bytes=MAX_BYTES,
        min_bytes=MIN_BYTES,
        min_dimension_px=MIN_DIM,
        max_dimension_px=MAX_DIM,
        max_pixels=MAX_PIXELS,
    )


def _png(width: int = 512, height: int = 512, pad_to: int | None = MIN_BYTES + 1024) -> bytes:
    """A real PNG of noise, optionally padded past the minimum size.

    Noise, not a flat fill: a uniform image compresses to a few hundred
    bytes and would trip the minimum-size control in tests that are about
    something else entirely.
    """
    rng = np.random.default_rng(0)
    array = rng.integers(0, 256, size=(height, width), dtype="uint8")
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    payload = buffer.getvalue()
    if pad_to is not None and len(payload) < pad_to:
        # Pad with a private ancillary chunk so the file stays a VALID PNG
        # -- appending raw bytes after IEND works with Pillow but is not
        # something to rely on in a fixture that other tests build on.
        payload = payload[:-12] + _chunk(b"prVt", b"\x00" * (pad_to - len(payload))) + payload[-12:]
    return payload


def _jpeg(width: int = 512, height: int = 512) -> bytes:
    rng = np.random.default_rng(1)
    array = rng.integers(0, 256, size=(height, width, 3), dtype="uint8")
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        len(payload).to_bytes(4, "big")
        + kind
        + payload
        + zlib.crc32(kind + payload).to_bytes(4, "big")
    )


# --- A1 ---------------------------------------------------------------


@pytest.mark.parametrize("extension", [".gif", ".bmp", ".webp", ".dcm", ".pdf", ""])
def test_A1_rejects_an_extension_outside_the_allow_list(service, extension):
    with pytest.raises(UnsupportedImageFormatError) as caught:
        service.admit(_png(), extension)
    assert caught.value.reason_code == "FORMAT_MISMATCH"


def test_A1_accepts_every_allowed_extension(service):
    assert service.admit(_png(), ".png").declared_extension == ".png"
    assert service.admit(_jpeg(), ".jpg").declared_extension == ".jpg"
    assert service.admit(_jpeg(), ".jpeg").declared_extension == ".jpeg"


def test_A1_extension_matching_is_case_insensitive(service):
    """An uploader on Windows routinely produces `SCAN.PNG`. Rejecting it
    for its case would be a usability failure dressed up as a security
    control -- the case of an extension carries no information about the
    file's contents, which is what A2/A4 actually check."""
    assert service.admit(_png(), ".PNG").declared_extension == ".png"


# --- A2 / A3 / A4 -----------------------------------------------------


def test_A4_rejects_a_jpeg_body_declared_as_png(service):
    """The signature says JPEG, the extension says PNG. A4 rejects the
    disagreement itself -- it does not quietly believe the bytes and carry
    on, because a mismatch is a signal about the uploader, not a
    formatting detail to normalize away."""
    with pytest.raises(UnsupportedImageFormatError) as caught:
        service.admit(_jpeg(), ".png")
    assert caught.value.reason_code == "FORMAT_MISMATCH"


def test_A4_rejects_a_png_body_declared_as_jpeg(service):
    with pytest.raises(UnsupportedImageFormatError):
        service.admit(_png(), ".jpg")


def test_A4_rejects_a_file_with_no_recognised_signature(service):
    with pytest.raises(UnsupportedImageFormatError):
        service.admit(b"not an image at all" * 2000, ".png")


def test_A3_format_is_decided_by_the_bytes_not_by_the_extension(service):
    """A3, stated as a property: `.jpg` and `.jpeg` are different strings
    and must both resolve to the same JPEG format decision, and the
    resulting normalized output must be identical either way. If the
    extension were driving the decode, these two would not agree."""
    from_jpg = service.admit(_jpeg(), ".jpg")
    from_jpeg = service.admit(_jpeg(), ".jpeg")
    assert from_jpg.png_bytes == from_jpeg.png_bytes


# --- A5 / A6 ----------------------------------------------------------


def test_A5_rejects_a_file_above_the_maximum_size():
    small_max = ImageAdmissionService(ALLOWED, 1024, 10, MIN_DIM, MAX_DIM, MAX_PIXELS)
    with pytest.raises(ImageTooLargeError) as caught:
        small_max.admit(_png(), ".png")
    assert caught.value.reason_code == "FILE_TOO_LARGE"


def test_A6_rejects_a_file_below_the_minimum_size(service):
    tiny = _png(width=64, height=64, pad_to=None)
    assert len(tiny) < MIN_BYTES
    with pytest.raises(InvalidImageError) as caught:
        service.admit(tiny, ".png")
    assert caught.value.reason_code == "FILE_TOO_SMALL"


def test_A5_and_A6_map_to_different_exception_types(service):
    """§10's table gives 413 for too-large and 422 for too-small. Two
    statuses require two types; a single SizeError would make the API
    layer re-inspect the message to pick a status."""
    small_max = ImageAdmissionService(ALLOWED, 1024, 10, MIN_DIM, MAX_DIM, MAX_PIXELS)
    with pytest.raises(ImageTooLargeError):
        small_max.admit(_png(), ".png")
    with pytest.raises(InvalidImageError):
        service.admit(_png(width=64, height=64, pad_to=None), ".png")


# --- A7 / A8 ----------------------------------------------------------


def _png_with_corrupt_pixel_data() -> bytes:
    """A PNG whose chunks are all structurally valid -- correct lengths,
    correct CRCs -- but whose IDAT holds a broken zlib stream.

    This is the payload A8 exists for. A merely TRUNCATED file does not
    demonstrate the point: Pillow's verify() walks the chunk structure and
    raises "Truncated File Read" on a short file, so truncation is already
    caught at A7 and a test built on it would pass without A8 existing at
    all (measured -- that was this test's first version).

    Corrupting the compressed payload and then RECOMPUTING the CRC is what
    separates the two controls: every structural check verify() performs
    still succeeds, and the file only fails when load() actually asks zlib
    to inflate the pixels.
    """
    original = _png(pad_to=None)
    offset = 8  # past the signature
    rebuilt = bytearray(original[:offset])
    while offset < len(original):
        length = int.from_bytes(original[offset : offset + 4], "big")
        kind = original[offset + 4 : offset + 8]
        payload = bytearray(original[offset + 8 : offset + 8 + length])
        if kind == b"IDAT" and length > 40:
            # Wreck the middle of the deflate stream, leaving the zlib
            # header intact so the damage is only discovered on inflate.
            payload[20:40] = b"\xff" * 20
        rebuilt += (
            len(payload).to_bytes(4, "big")
            + kind
            + payload
            + zlib.crc32(kind + bytes(payload)).to_bytes(4, "big")
        )
        offset += 12 + length
    return bytes(rebuilt)


def test_A8_rejects_corrupt_pixel_data_that_A7_alone_would_pass(service):
    """The exact case A7's Note describes: verify() does not decode
    pixels, so a file whose structure is intact and whose pixel data is
    corrupt survives verify() and can only be caught by the second open
    and load(). If A8 were dropped as redundant, this payload would be
    admitted and a broken image would reach the encoder."""
    payload = _png_with_corrupt_pixel_data()

    # verify() alone really does accept it -- otherwise this test would
    # pass for the wrong reason, proving nothing about A8.
    with Image.open(io.BytesIO(payload)) as probe:
        probe.verify()

    with pytest.raises(InvalidImageError) as caught:
        service.admit(payload, ".png")
    assert caught.value.reason_code == "IMAGE_LOAD_FAILED"


def test_A7_rejects_a_truncated_file(service):
    """Truncation is caught one control earlier, at verify(). Recorded as
    its own test so the division of labour between A7 and A8 is visible:
    A7 catches structural damage, A8 catches pixel-data damage."""
    payload = _png()
    with pytest.raises(InvalidImageError) as caught:
        service.admit(payload[: len(payload) // 2], ".png")
    assert caught.value.reason_code == "IMAGE_VERIFY_FAILED"


# --- A9 ---------------------------------------------------------------


def test_A9_rejects_a_declared_pixel_count_above_the_limit(service):
    """A decompression bomb: a tiny file declaring 1.6e9 pixels. Rejected
    without ever allocating them, which is the point -- see T6."""
    ihdr = (40000).to_bytes(4, "big") + (40000).to_bytes(4, "big") + bytes([8, 0, 0, 0, 0])
    bomb = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(b"\x00" * 40_000_000, level=6))
        + _chunk(b"IEND", b"")
    )
    assert len(bomb) < MAX_BYTES  # size alone cannot catch it

    with pytest.raises(InvalidImageError) as caught:
        service.admit(bomb, ".png")
    assert caught.value.reason_code == "PIXEL_LIMIT_EXCEEDED"


def test_A9_sets_the_configured_limit_on_pillow(service):
    """A9 says to SET Image.MAX_IMAGE_PIXELS, not merely to check the
    product ourselves -- the Pillow-level limit is what protects decodes
    this service does not perform."""
    assert Image.MAX_IMAGE_PIXELS == MAX_PIXELS


# --- A10 / A11 --------------------------------------------------------


def test_A10_rejects_an_image_below_the_minimum_dimension(service):
    narrow = ImageAdmissionService(ALLOWED, MAX_BYTES, 10, MIN_DIM, MAX_DIM, MAX_PIXELS)
    with pytest.raises(InvalidImageError) as caught:
        narrow.admit(_png(width=128, height=512, pad_to=None), ".png")
    assert caught.value.reason_code == "DIMENSIONS_TOO_SMALL"


def test_A11_rejects_an_image_above_the_maximum_dimension():
    small_max_dim = ImageAdmissionService(ALLOWED, MAX_BYTES, 10, 8, 64, MAX_PIXELS)
    with pytest.raises(InvalidImageError) as caught:
        small_max_dim.admit(_png(width=512, height=512), ".png")
    assert caught.value.reason_code == "DIMENSIONS_TOO_LARGE"


# --- A12 / A13 --------------------------------------------------------


def test_A12_output_is_always_png_whatever_went_in(service):
    assert service.admit(_png(), ".png").png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert service.admit(_jpeg(), ".jpg").png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_A12_strips_exif_from_a_jpeg(service):
    piexif = pytest.importorskip("piexif")

    rng = np.random.default_rng(2)
    array = rng.integers(0, 256, size=(512, 512, 3), dtype="uint8")
    buffer = io.BytesIO()
    exif = piexif.dump(
        {
            "0th": {piexif.ImageIFD.ImageDescription: b"PATIENT: Abdur Rahman"},
            "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None,
        }
    )
    Image.fromarray(array).save(buffer, format="JPEG", exif=exif, quality=95)
    payload = buffer.getvalue()
    assert b"Abdur Rahman" in payload

    admitted = service.admit(payload, ".jpg")
    assert b"Abdur Rahman" not in admitted.png_bytes
    with Image.open(io.BytesIO(admitted.png_bytes)) as normalized:
        assert not normalized.getexif()


def test_A12_preserves_the_pixels(service):
    """Normalization must not alter the image. A PNG source is lossless
    end to end, so the decoded output has to be pixel-identical to the
    decoded input -- an embedding computed from a subtly different raster
    would not be the embedding of what the doctor uploaded."""
    payload = _png()
    admitted = service.admit(payload, ".png")
    with Image.open(io.BytesIO(payload)) as before, Image.open(io.BytesIO(admitted.png_bytes)) as after:
        assert np.array_equal(np.asarray(before), np.asarray(after))


def test_sha256_is_over_the_raw_bytes_not_the_normalized_output(service):
    """DR-2 uses this hash to find repeated attempts, so it must identify
    the file the user actually sent. Hashing the re-encode would make two
    different uploads that normalize alike collide, and would not exist at
    all for a file rejected before decode."""
    import hashlib

    payload = _jpeg()
    admitted = service.admit(payload, ".jpg")
    assert admitted.sha256 == hashlib.sha256(payload).hexdigest()
    assert admitted.sha256 != hashlib.sha256(admitted.png_bytes).hexdigest()


# --- the PHI contract -------------------------------------------------


def test_no_rejection_message_can_contain_a_file_name(service):
    """§10's Rule and DR-2's Warning, tested as the structural property
    they are: admit() has no file-name parameter, so there is nothing for
    a message to leak. This asserts the signature, which is what makes the
    guarantee hold for messages that do not exist yet."""
    import inspect

    parameters = set(inspect.signature(service.admit).parameters)
    assert parameters == {"raw_bytes", "declared_extension"}
    for forbidden in ("filename", "file_name", "name", "upload_file"):
        assert forbidden not in parameters


@pytest.mark.parametrize(
    "case",
    ["bad_signature", "too_small", "bad_extension", "corrupt_pixels"],
)
def test_every_rejection_carries_a_reason_code_and_a_stage(service, case):
    """Every rejection has to be able to populate DR-2's audit row, and
    the raise site is the only place that knows which control fired.

    Parametrized by NAME, with the payload built inside the test. Passing
    the raw bytes as the parameter makes pytest render a megabyte of
    binary into every test id and into any failure report.
    """
    payload, extension = {
        "bad_signature": (b"not an image" * 2000, ".png"),
        "too_small": (_png(width=64, height=64, pad_to=None), ".png"),
        "bad_extension": (_png(), ".gif"),
        "corrupt_pixels": (_png_with_corrupt_pixel_data(), ".png"),
    }[case]

    with pytest.raises((UnsupportedImageFormatError, ImageTooLargeError, InvalidImageError)) as caught:
        service.admit(payload, extension)
    assert caught.value.reason_code
    assert caught.value.stage


# ======================================================================
# §5.5 -- the declared projection (A14 to A17), new in v1.1
# ======================================================================

ACCEPTED = ("PA", "AP")
DECLARABLE = ("PA", "AP", "LATERAL")


@pytest.fixture
def projection_service() -> ImageAdmissionService:
    """The same service, additionally configured with the two projection
    lists. Kept as a second fixture so the A1-A13 tests above keep
    constructing the service the way every caller did before v1.1, which
    is what proves the projection arguments are genuinely optional to the
    file checks."""
    return ImageAdmissionService(
        allowed_extensions=ALLOWED,
        max_bytes=MAX_BYTES,
        min_bytes=MIN_BYTES,
        min_dimension_px=MIN_DIM,
        max_dimension_px=MAX_DIM,
        max_pixels=MAX_PIXELS,
        accepted_projections=ACCEPTED,
        declared_projection_values=DECLARABLE,
    )


# --- A14 --------------------------------------------------------------


@pytest.mark.parametrize("value", ["PA", "AP"])
def test_A14_accepts_the_accepted_projections(projection_service, value):
    assert projection_service.check_declared_projection(value) == value


def test_A14_normalizes_case_and_surrounding_space(projection_service):
    """A form field arrives as text. `pa` and ` PA ` are the same
    declaration as `PA`; treating them as unrecognised would reject a
    correct answer for its typography."""
    assert projection_service.check_declared_projection("pa") == "PA"
    assert projection_service.check_declared_projection("  Ap  ") == "AP"


# --- A15 --------------------------------------------------------------


@pytest.mark.parametrize("absent", [None, "", "   ", "\t"])
def test_A15_rejects_an_absent_field_and_selects_no_default(projection_service, absent):
    """A15: "Reject the request if the field is absent. Do not select a
    default value."

    Whitespace counts as absent: a field holding " " is not a
    declaration, and accepting it would select PA by accident -- exactly
    what A15 forbids.
    """
    with pytest.raises(InvalidImageError) as caught:
        projection_service.check_declared_projection(absent)
    assert caught.value.reason_code == "PROJECTION_NOT_DECLARED"
    assert caught.value.stage == "admission_projection"


@pytest.mark.parametrize("value", ["OBLIQUE", "pa1", "FRONTAL", "LAT", "PA,AP"])
def test_A15_an_unrecognised_value_is_not_declared_and_is_not_lateral(projection_service, value):
    """An unrecognised value has declared none of A14's three permitted
    values, which is the condition A15 describes.

    It must NOT map to DECLARED_LATERAL: that code means "the doctor told
    us it is lateral", and using it for a typo would make DR-2's
    rejection counts wrong -- the specific failure §10's Rule names.
    """
    with pytest.raises(InvalidImageError) as caught:
        projection_service.check_declared_projection(value)
    assert caught.value.reason_code == "PROJECTION_NOT_DECLARED"


# --- A16 --------------------------------------------------------------


def test_A16_rejects_a_declared_lateral_with_its_own_type_and_code(projection_service):
    with pytest.raises(LateralProjectionError) as caught:
        projection_service.check_declared_projection("LATERAL")
    assert caught.value.reason_code == "DECLARED_LATERAL"
    assert caught.value.stage == "admission_projection"
    assert caught.value.declared_projection == "LATERAL"


def test_A16_is_not_an_InvalidImageError(projection_service):
    """§10's Rule: a lateral image IS a chest radiograph, and it is a
    valid image. Raising InvalidImageError for it would both mis-state the
    failure and collapse it into the "file too small, damaged, or bad
    dimensions" row of §10's table."""
    assert not issubclass(LateralProjectionError, InvalidImageError)
    assert not issubclass(LateralProjectionError, InputAdmissionError)


def test_A16_message_key_is_carried_not_english_prose(projection_service):
    """§10.1: the projection messages are translated through the i18n key
    set, so the exception carries a key for the API layer to send."""
    with pytest.raises(LateralProjectionError) as caught:
        projection_service.check_declared_projection("LATERAL")
    assert caught.value.message_key == "error.projection.declaredLateral"


# --- A17 --------------------------------------------------------------


def test_A17_the_projection_check_cannot_mask_embed_or_query(projection_service):
    """A17: "Reject at this point. Do not mask the image. Do not embed the
    image. Do not query ChromaDB."

    Enforced structurally and asserted as such: this method is given only
    the declared value, so it holds no image, no masker, no embedder and
    no vector store to reach for. The end-to-end proof that the ROUTE
    honours the ordering is T15, which counts the calls.
    """
    import inspect

    parameters = set(inspect.signature(projection_service.check_declared_projection).parameters)
    assert parameters == {"declared_projection"}
    for forbidden in ("image", "raw_bytes", "png_bytes", "path", "masker", "embedder"):
        assert forbidden not in parameters


def test_the_projection_check_never_sees_a_file_name(projection_service):
    """DR-2's Warning and §10's Rule, same structural argument as admit()."""
    import inspect

    parameters = set(inspect.signature(projection_service.check_declared_projection).parameters)
    for forbidden in ("filename", "file_name", "name", "upload_file"):
        assert forbidden not in parameters
