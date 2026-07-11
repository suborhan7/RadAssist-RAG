"""
app/infrastructure/biomedclip_adapter.py
====================================================================
Thin adapter satisfying IEmbedder. All real logic lives in
shared/embeddings/BiomedCLIPEmbedder -- this class does not reimplement
anything, it only adapts the shared component's (batched, list[float]-per-
item via .embed_image/.embed_text) interface to exactly what IEmbedder
requires, and gives backend/ a single import point independent of shared/'s
internal module layout.

Deliberately thin: if this file starts accumulating logic, that logic
belongs in shared/embeddings/ instead, not here.
"""
from __future__ import annotations

from shared.embeddings.biomedclip_embedder import BiomedCLIPEmbedder


class BiomedCLIPAdapter:
    """Satisfies domain.interfaces.IEmbedder. Wraps the shared embedder singleton."""

    def __init__(self, embedder: BiomedCLIPEmbedder | None = None) -> None:
        # allow injection of an already-loaded embedder (e.g. a shared
        # singleton held by the app's DI container) to avoid reloading the
        # model per request; falls back to loading its own if none given.
        self._embedder = embedder or BiomedCLIPEmbedder()

    def embed_image(self, image_path: str) -> list[float]:
        return self._embedder.embed_image(image_path)

    def embed_text(self, text: str) -> list[float]:
        return self._embedder.embed_text(text)
