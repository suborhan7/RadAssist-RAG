"""
app/services/image_validator.py
====================================================================
Implements IImageValidator. Checks an uploaded image is a real, openable,
non-empty file before it enters the retrieval pipeline.
"""
from __future__ import annotations

import os

from PIL import Image, UnidentifiedImageError


class ImageValidator:
    """Satisfies domain.interfaces.IImageValidator."""

    def validate(self, image_path: str) -> None:
        if not os.path.isfile(image_path):
            raise ValueError(f"image file does not exist: {image_path}")

        if os.path.getsize(image_path) == 0:
            raise ValueError(f"image file is empty: {image_path}")

        try:
            with Image.open(image_path) as img:
                img.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"file is not a valid/readable image: {image_path} ({exc})") from exc
