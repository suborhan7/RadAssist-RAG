"""
shared/embeddings/base.py
====================================================================
Abstract contract every embedder implementation in this package follows
(BiomedCLIP now; MedCLIP/BioViL/CheXzero if ever swapped or compared later).

Concrete subclasses implement only the two batched methods; the singular
convenience methods (embed_image/embed_text) are derived once, here, so
every future embedder gets them for free instead of re-implementing the
same trivial wrapper.

Note: this ABC is NOT what satisfies the backend's IEmbedder Protocol --
Python Protocols are structural, so any class with matching method
signatures already satisfies IEmbedder without inheriting anything. This
ABC's job is purely internal consistency within shared/embeddings/ as it
grows to support more than one model.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

import numpy as np


def l2_normalize(x: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalization with a safe epsilon -- a degenerate
    all-zero embedding (e.g. from a corrupt input) stays zero rather than
    propagating a NaN through cosine-similarity computations downstream."""
    norms = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.clip(norms, a_min=1e-12, a_max=None)


class BaseEmbedder(ABC):
    """Every embedder returns L2-normalized float32 vectors, batched by default."""

    @abstractmethod
    def embed_images(self, image_paths: Sequence[str | Path]) -> np.ndarray:
        """Returns (N, D) float32, L2-normalized rows."""
        raise NotImplementedError

    @abstractmethod
    def embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        """Returns (N, D) float32, L2-normalized rows."""
        raise NotImplementedError

    def embed_image(self, image_path: str | Path) -> list[float]:
        return self.embed_images([image_path])[0].tolist()

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0].tolist()
