"""
shared/embeddings/biomedclip_embedder.py
====================================================================
The project's frozen production embedder (BiomedCLIP). Loaded once, reused
everywhere: batch embedding generation, retrieval evaluation, ChromaDB
indexing, the backend's embedding service, re-embedding runs, and smoke
tests.

Lives in shared/ (not ml/ or backend/) deliberately: both the research
pipeline and the production backend depend on this identical implementation
so that offline-generated knowledge-base embeddings and live query
embeddings are guaranteed to occupy the same vector space. Two independent
copies (one per layer) would risk silent drift between them -- a subtle
preprocessing or normalization difference would not error, it would just
quietly degrade retrieval quality.

No FastAPI, no domain-layer imports, no framework beyond torch/open_clip.
Satisfies the backend's IEmbedder Protocol structurally (Python Protocols
are duck-typed) without this module ever importing that interface --
backend/app/infrastructure/ imports this class directly.

Usage:
    from shared.embeddings.biomedclip_embedder import BiomedCLIPEmbedder

    embedder = BiomedCLIPEmbedder()          # loads the model once
    vecs = embedder.embed_images(paths)      # (N, D) float32, L2-normalized
    qvec = embedder.embed_text("cardiomegaly with pleural effusion")
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

from shared.embeddings.base import BaseEmbedder, l2_normalize

DEFAULT_MODEL_ID = "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224"


class BiomedCLIPEmbedder(BaseEmbedder):
    """Loads BiomedCLIP once; all methods reuse the same model/preprocess/device."""

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        device: str = "auto",
        batch_size: int = 64,
    ) -> None:
        # torch/open_clip imported lazily inside __init__ (not at module level)
        # so this module can be imported -- and shared/embeddings/base.py's
        # pure helpers unit-tested -- in environments without a GPU/torch.
        import torch
        import open_clip

        self.device = self._resolve_device(device, torch)
        self.batch_size = batch_size

        model, _, preprocess = open_clip.create_model_and_transforms(model_id)
        tokenizer = open_clip.get_tokenizer(model_id)

        self._torch = torch
        self.model = model.to(self.device).eval()
        self.preprocess = preprocess
        self.tokenizer = tokenizer

    @staticmethod
    def _resolve_device(device: str, torch_module) -> str:
        if device != "auto":
            return device
        return "cuda" if torch_module.cuda.is_available() else "cpu"

    def embed_images(self, image_paths: Sequence[str | Path]) -> np.ndarray:
        from PIL import Image

        torch = self._torch
        out = []
        with torch.no_grad():
            for i in range(0, len(image_paths), self.batch_size):
                batch_paths = image_paths[i : i + self.batch_size]
                imgs = [self.preprocess(Image.open(p).convert("RGB")) for p in batch_paths]
                x = torch.stack(imgs).to(self.device)
                feats = self.model.encode_image(x).float().cpu().numpy()
                out.append(feats)
        embeddings = np.concatenate(out, axis=0).astype(np.float32)
        return l2_normalize(embeddings)

    def embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        torch = self._torch
        out = []
        with torch.no_grad():
            for i in range(0, len(texts), self.batch_size):
                batch_texts = texts[i : i + self.batch_size]
                tokens = self.tokenizer(list(batch_texts)).to(self.device)
                feats = self.model.encode_text(tokens).float().cpu().numpy()
                out.append(feats)
        embeddings = np.concatenate(out, axis=0).astype(np.float32)
        return l2_normalize(embeddings)
