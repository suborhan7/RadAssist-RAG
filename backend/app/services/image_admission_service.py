"""
app/services/image_admission_service.py
====================================================================
ImageAdmissionService -- requirements A1 to A13 of
docs/methodology/input_admission_projection_gate_architecture_v1.1_FROZEN.md
(§5). The "admit" verb of that document's §3.2 vocabulary lock: check the
RAW uploaded file for safety. It is not "validate" (§3.2 reserves that for
`validate_semantic()`, which compares a finished report with its evidence)
and it is not "gate" (§3.2 reserves that for ModalityGateService, which
checks image CONTENT).

This service is deliberately separate from ModalityGateService, and its
logic is deliberately absent from PrivacyService and EmbeddingService
(§1, §10). It runs first, before everything else (§5 opening line, §9
pipeline order) -- specifically before PrivacyService, because §3.3 states
the reason plainly: the system must not hand an unsafe file to the OCR
library.

Relationship to the pre-existing ImageValidator
-----------------------------------------------
app/services/image_validator.py (Phase 4) is NOT this service and is not
replaced by it. That class answers "can Pillow open this path at all"
for the RetrievalService.retrieve(path) code path; this one answers §5's
thirteen much stronger questions about an untrusted upload, works on
bytes rather than a path, and re-encodes its output. Both continue to
exist: the P0-1 defect (a photograph of a strawberry produced a full
radiology report) happened with ImageValidator already in place and
passing, which is precisely why §4 calls the input layer absent.

Why this class takes bytes and an extension, never a file name
--------------------------------------------------------------
DR-2's Warning and §10's closing Rule forbid the uploaded file's name
from appearing in any error message, application log line, or audit row,
because a file name frequently contains a patient name (the document's
own example: `Abdur_Rahman_CXR_2026.jpg`). That is enforced here
structurally rather than by careful writing: the file name is never
passed in, so no raise site in this module has one in scope to leak. The
caller extracts the declared extension and hands over only that. Nothing
below logs, and every message is built from configured parameters and
measured properties of the pixels.

No parameter value is written in this file (§11.1's Rule). Every bound --
allowed extensions, size limits, dimension limits, the pixel ceiling --
arrives through the constructor from `settings`.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from app.services.exceptions import (
    ImageTooLargeError,
    InvalidImageError,
    LateralProjectionError,
    UnsupportedImageFormatError,
)

# Not parameters -- these are the PNG and JPEG file-format specifications
# (RFC 2083 §3.1 and ITU-T T.81 respectively), the same in every
# deployment and not something an operator may tune. §11.1's Rule governs
# calibration/policy values, which these are not; putting a format's own
# magic bytes in a .env file would make a wrong value silently accept
# malformed files.
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"

# Which sniffed format each declared extension is allowed to resolve to
# (A4). Also a format fact, not a tunable: `.jpg` and `.jpeg` are two
# spellings of one format.
_EXTENSION_TO_FORMAT = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
}


@dataclass(frozen=True)
class AdmittedImage:
    """What a successful admission produces.

    `png_bytes` is A12's re-encode: a brand-new PNG built from the decoded
    pixel array alone. It is the ONLY thing downstream services are given
    (A13) -- the original upload bytes never leave this service, so EXIF
    (which can carry Protected Health Information, per A12's Note) and any
    polyglot payload are gone by construction rather than by stripping.

    `sha256` is over the ORIGINAL raw bytes, not the re-encode. DR-2's
    audit table uses it to find repeated attempts, and two attempts to
    upload the same rejected file must hash identically -- a hash of the
    normalized output would not exist for a file rejected before decode.
    """

    png_bytes: bytes
    sha256: str
    size_bytes: int
    declared_extension: str
    width: int
    height: int


class ImageAdmissionService:
    """Implements §5, requirements A1 to A13."""

    def __init__(
        self,
        allowed_extensions: tuple[str, ...],
        max_bytes: int,
        min_bytes: int,
        min_dimension_px: int,
        max_dimension_px: int,
        max_pixels: int,
        accepted_projections: tuple[str, ...] = (),
        declared_projection_values: tuple[str, ...] = (),
    ) -> None:
        self._allowed_extensions = allowed_extensions
        self._max_bytes = max_bytes
        self._min_bytes = min_bytes
        self._min_dimension_px = min_dimension_px
        self._max_dimension_px = max_dimension_px
        self._max_pixels = max_pixels
        # §5.5 (A14-A17). Defaulted to empty tuples so the eighteen existing
        # unit tests that construct this service with six positional bounds
        # keep working -- they exercise A1-A13, which the projection check
        # does not touch. The API layer always supplies both.
        self._accepted_projections = accepted_projections
        self._declared_projection_values = declared_projection_values

        # A9. Pillow reads this at decode time off the module, so it is
        # process-global state rather than a per-instance setting -- set
        # here (at construction, i.e. once at app start-up) so the limit
        # is in force for every decode this process ever performs,
        # including the one two lines below in admit().
        #
        # Pillow's own behavior is graded: it emits a DecompressionBomb
        # WARNING above MAX_IMAGE_PIXELS and only raises
        # DecompressionBombError above twice that. A warning is not a
        # rejection, so admit() ALSO checks width*height against the same
        # configured limit explicitly. Setting the Pillow limit satisfies
        # A9 as written; the explicit check makes the limit the hard
        # boundary A9 exists to create, at exactly the configured value
        # rather than at an implicit 2x of it.
        Image.MAX_IMAGE_PIXELS = max_pixels

    def admit(self, raw_bytes: bytes, declared_extension: str) -> AdmittedImage:
        """Runs A1 to A13 in order and returns the normalized PNG.

        Raises UnsupportedImageFormatError (415), ImageTooLargeError (413),
        or InvalidImageError (422) per §10's table. `declared_extension` is
        the extension the client's file name carried -- taken as a CLAIM to
        be checked against the bytes (A4), never as the source of truth for
        the format (A3).
        """
        extension = declared_extension.strip().lower()

        # --- A1: extension allow-list. ---
        if extension not in self._allowed_extensions:
            raise UnsupportedImageFormatError(
                f"file extension is not accepted; allowed extensions are "
                f"{', '.join(self._allowed_extensions)}",
                reason_code="FORMAT_MISMATCH",
                stage="admission_format",
            )

        # --- A2 + A3: sniff the real format from the leading bytes. ---
        # The Content-Type header is never consulted (this method is not
        # given one) and the file name is never consulted (this method is
        # not given one either) -- A3 satisfied structurally.
        sniffed_format = self._sniff_format(raw_bytes)

        # --- A4: the signature must agree with the extension. ---
        if sniffed_format is None or sniffed_format != _EXTENSION_TO_FORMAT[extension]:
            raise UnsupportedImageFormatError(
                f"file content does not match the declared '{extension}' extension",
                reason_code="FORMAT_MISMATCH",
                stage="admission_format",
            )

        # --- A5 + A6: size bounds. ---
        size_bytes = len(raw_bytes)
        if size_bytes > self._max_bytes:
            raise ImageTooLargeError(
                f"file size {size_bytes} bytes is above the maximum of {self._max_bytes} bytes",
                reason_code="FILE_TOO_LARGE",
                stage="admission_size",
            )
        if size_bytes < self._min_bytes:
            raise InvalidImageError(
                f"file size {size_bytes} bytes is below the minimum of {self._min_bytes} bytes",
                reason_code="FILE_TOO_SMALL",
                stage="admission_size",
            )

        # --- A7 + A8: verify(), then a second open for load(). ---
        self._verify(raw_bytes)
        image = self._load(raw_bytes)

        try:
            width, height = image.size

            # --- A9: pixel-count ceiling (see __init__ for why this is
            # checked explicitly as well as configured into Pillow). ---
            if width * height > self._max_pixels:
                raise InvalidImageError(
                    f"image has {width * height} pixels, above the maximum of "
                    f"{self._max_pixels} pixels",
                    reason_code="PIXEL_LIMIT_EXCEEDED",
                    stage="admission_decode",
                )

            # --- A10 + A11: dimension bounds. ---
            if width < self._min_dimension_px or height < self._min_dimension_px:
                raise InvalidImageError(
                    f"image dimensions {width}x{height} are below the minimum of "
                    f"{self._min_dimension_px} px on a side",
                    reason_code="DIMENSIONS_TOO_SMALL",
                    stage="admission_decode",
                )
            if width > self._max_dimension_px or height > self._max_dimension_px:
                raise InvalidImageError(
                    f"image dimensions {width}x{height} are above the maximum of "
                    f"{self._max_dimension_px} px on a side",
                    reason_code="DIMENSIONS_TOO_LARGE",
                    stage="admission_decode",
                )

            # --- A12: re-encode from the pixel array alone. ---
            png_bytes = self._reencode_as_png(image)
        finally:
            image.close()

        return AdmittedImage(
            png_bytes=png_bytes,
            sha256=hashlib.sha256(raw_bytes).hexdigest(),
            size_bytes=size_bytes,
            declared_extension=extension,
            width=width,
            height=height,
        )

    # ------------------------------------------------------------------
    # §5.5 -- the declared projection (A14 to A17)
    # ------------------------------------------------------------------
    def check_declared_projection(self, declared_projection: str | None) -> str:
        """A14 to A17. Returns the normalized accepted projection, or raises.

        A separate method from admit(), not a parameter of it. §9 runs the
        two as consecutive steps (A1-A13, then A14-A17), and they answer
        different questions about different inputs: admit() judges bytes,
        this judges a form field. Folding the field into admit() would also
        mean a request with a bad projection had to be decoded first, which
        A17 exists to prevent.

        A17 is satisfied by WHERE this is called, not by anything in here:
        the route calls it before the masker, the embedder and ChromaDB are
        touched at all. This method has no access to any of them.

        Raises
        ------
        InvalidImageError(PROJECTION_NOT_DECLARED)
            A15 -- the field is absent. No default is selected.
        LateralProjectionError(DECLARED_LATERAL)
            A16 -- the declared projection is LATERAL.
        """
        # --- A15: absent means rejected. No default value. ---
        # A15 says "Do not select a default value", so an empty or missing
        # field is a rejection and never an assumed PA. Whitespace-only is
        # treated as absent: a form field containing " " is not a
        # declaration, and accepting it would be selecting a default by
        # accident.
        if declared_projection is None or not declared_projection.strip():
            raise InvalidImageError(
                "the declared projection field is required and was not supplied",
                reason_code="PROJECTION_NOT_DECLARED",
                stage="admission_projection",
            )

        value = declared_projection.strip().upper()

        # --- A14: the permitted declared values. ---
        # An unrecognised value (say "OBLIQUE" or "pa1") is mapped to
        # PROJECTION_NOT_DECLARED rather than to a code of its own. §5.5
        # names three permitted values and gives a rejection code only for
        # LATERAL; a value outside the permitted set has not declared any
        # of the three, which is the condition A15 describes. It is
        # deliberately NOT mapped to DECLARED_LATERAL, because that code
        # means "the doctor told us it is lateral" and would make the DR-2
        # rejection counts wrong.
        if value not in self._declared_projection_values:
            raise InvalidImageError(
                f"the declared projection must be one of "
                f"{', '.join(self._declared_projection_values)}",
                reason_code="PROJECTION_NOT_DECLARED",
                stage="admission_projection",
            )

        # --- A16: LATERAL is a permitted declaration and a rejected input. ---
        # Its own exception type and its own reason code, per §10's Rule: a
        # lateral image IS a chest radiograph, so it must not share a type
        # with NotAChestRadiographError or with ProjectionMismatchError.
        if value not in self._accepted_projections:
            raise LateralProjectionError(value)

        return value

    # ------------------------------------------------------------------
    # A2/A4 helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _sniff_format(raw_bytes: bytes) -> str | None:
        """A2: read the first bytes and compare them with the known PNG and
        JPEG signatures. Returns None for anything else -- including an
        empty or truncated-to-nothing upload, since a prefix comparison
        against a short buffer simply fails rather than erroring."""
        if raw_bytes.startswith(_PNG_SIGNATURE):
            return "PNG"
        if raw_bytes.startswith(_JPEG_SIGNATURE):
            return "JPEG"
        return None

    # ------------------------------------------------------------------
    # A7/A8 helpers
    # ------------------------------------------------------------------
    def _verify(self, raw_bytes: bytes) -> None:
        """A7: open and call verify()."""
        try:
            with Image.open(io.BytesIO(raw_bytes)) as image:
                image.verify()
        except InvalidImageError:
            raise
        except Image.DecompressionBombError as exc:
            # A9, and it fires here rather than at the explicit pixel-count
            # check in admit(): Pillow runs its own decompression-bomb
            # check inside Image.open() itself, off the dimensions declared
            # in the header, BEFORE a single pixel is allocated. That early
            # rejection is the whole reason A9 works -- the process stays
            # up (T6), which it would not if the decode were attempted
            # first and 1.6 billion pixels were requested from the
            # allocator.
            #
            # Caught as its OWN clause, not folded into the tuple below.
            # DecompressionBombError derives directly from Exception, not
            # from ValueError or OSError as its siblings do, so a generic
            # image-error tuple does not cover it -- which was a real bug
            # here: the bomb escaped admission entirely and surfaced as an
            # unhandled 500 instead of the 422 §10's table requires.
            raise InvalidImageError(
                f"image exceeds the maximum of {self._max_pixels} pixels",
                reason_code="PIXEL_LIMIT_EXCEEDED",
                stage="admission_decode",
            ) from exc
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise InvalidImageError(
                f"file is not a readable image ({exc.__class__.__name__})",
                reason_code="IMAGE_VERIFY_FAILED",
                stage="admission_decode",
            ) from exc

    def _load(self, raw_bytes: bytes) -> Image.Image:
        """A8: close, open again, call load().

        The second open is not defensive duplication -- A7's Note states
        the reason: verify() does not decode pixels, so a file with a valid
        header and a damaged data stream passes verify() and only fails
        here. A fresh BytesIO is used because verify() leaves the previous
        handle unusable for further reads (Pillow documents that the
        instance must not be used after verify()).
        """
        try:
            image = Image.open(io.BytesIO(raw_bytes))
        except Image.DecompressionBombError as exc:
            # Same clause, same reason as in _verify() above -- see there.
            # Repeated rather than shared because this is the second of the
            # two opens A8 mandates, and a bomb must be stopped at whichever
            # one reaches it first.
            raise InvalidImageError(
                f"image exceeds the maximum of {self._max_pixels} pixels",
                reason_code="PIXEL_LIMIT_EXCEEDED",
                stage="admission_decode",
            ) from exc
        try:
            image.load()
        except Image.DecompressionBombError as exc:
            image.close()
            raise InvalidImageError(
                f"image exceeds the maximum of {self._max_pixels} pixels",
                reason_code="PIXEL_LIMIT_EXCEEDED",
                stage="admission_decode",
            ) from exc
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            image.close()
            raise InvalidImageError(
                f"image data is damaged and could not be decoded ({exc.__class__.__name__})",
                reason_code="IMAGE_LOAD_FAILED",
                stage="admission_decode",
            ) from exc
        return image

    # ------------------------------------------------------------------
    # A12 helper
    # ------------------------------------------------------------------
    @staticmethod
    def _reencode_as_png(image: Image.Image) -> bytes:
        """A12: encode the decoded pixels again as PNG, using only the
        pixel array.

        The mode conversion is part of "use only the pixel array": a JPEG
        decodes to RGB and a radiograph PNG usually to L or I;16, and
        Image.save() carries a source image's `info` dict (which is where
        Pillow keeps EXIF, ICC profiles, and text chunks) into the output
        for some formats. Building a NEW image from `getdata()` leaves that
        dict behind entirely rather than trusting a per-format exclusion
        list, which is what makes A12's Note ("the new PNG file has no EXIF
        metadata") true by construction.

        Palette ("P") and 1-bit images are widened to a normal grayscale or
        RGB mode first, so the output is a plain pixel raster with no
        palette chunk riding along.

        tobytes()/frombytes() rather than getdata()/putdata(): same
        pixels-only guarantee, but it moves the raster as one buffer
        instead of materializing a Python list with one object per pixel
        (an 8192x8192 image at the configured dimension ceiling would be
        67 million of them), and getdata() is deprecated for removal in
        Pillow 14.
        """
        if image.mode in ("P", "1"):
            image = image.convert("RGB" if image.mode == "P" else "L")

        clean = Image.frombytes(image.mode, image.size, image.tobytes())

        buffer = io.BytesIO()
        clean.save(buffer, format="PNG")
        clean.close()
        return buffer.getvalue()
