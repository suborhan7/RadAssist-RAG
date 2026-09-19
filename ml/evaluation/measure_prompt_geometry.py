"""
ml/evaluation/measure_prompt_geometry.py
====================================================================
MEASUREMENT 3 -- pairwise cosine geometry of the five MODALITY_PROMPTS in
BiomedCLIP's text embedding space.

A MEASUREMENT SCRIPT. Reads only. No production module imports it and it
writes nothing. It READS the prompt set out of the settings object so the
matrix describes the prompts actually deployed rather than a copy that
could drift, but it changes no setting -- MODALITY_THRESHOLD is not read
at all, since a threshold plays no part in this measurement.

Why the raw cosines, and not the softmax output
-----------------------------------------------
The gate's decision is a softmax over image-to-prompt cosines, so its
behavior depends on how far apart the PROMPTS are from each other. If two
prompts sit close together in text space, no image can separate them: the
softmax will split its mass between them regardless of what the image
shows. This measures that directly, on the text side alone, with no image
involved.

Normalization
-------------
`BiomedCLIPEmbedder.embed_texts()` returns L2-normalized vectors (it ends
in `l2_normalize`, shared/embeddings/base.py). The dot product of two such
vectors IS their cosine similarity. This script asserts the norms are 1
rather than assuming it, and re-normalization is deliberately NOT applied
on top -- silently re-normalizing would hide it if the frozen embedder
ever stopped normalizing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "backend"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decimals", type=int, default=4)
    args = parser.parse_args()

    from app.core.config import settings
    from shared.embeddings.biomedclip_embedder import BiomedCLIPEmbedder, DEFAULT_MODEL_ID

    # The deployed prompt set, in the deployed order: positives first, then
    # negatives -- the same concatenation ModalityGateService builds its
    # cached prompt vectors from.
    prompts = [*settings.modality_prompts_positive, *settings.modality_prompts_negative]

    print("=" * 78)
    print("MEASUREMENT 3 -- text-embedding geometry of MODALITY_PROMPTS")
    print("=" * 78)
    print(f"model: {DEFAULT_MODEL_ID}")
    print(f"prompt set read from settings (positives first, then negatives), n={len(prompts)}:")
    for index, prompt in enumerate(prompts):
        role = "positive" if index < len(settings.modality_prompts_positive) else "negative"
        print(f"  [{index}] ({role:8s}) {prompt!r}")
    print()

    embedder = BiomedCLIPEmbedder()
    vectors = embedder.embed_texts(prompts)

    norms = np.linalg.norm(vectors, axis=1)
    print("--- normalization ---")
    print(f"embedding shape: {vectors.shape}")
    print(f"L2 norms per prompt: {np.round(norms, 8).tolist()}")
    print(
        "matrix computed on NORMALIZED embeddings: "
        f"{bool(np.allclose(norms, 1.0, atol=1e-5))} "
        "(BiomedCLIPEmbedder.embed_texts returns L2-normalized vectors; "
        "no re-normalization applied here)"
    )
    print()

    # logit_scale is read straight off the loaded model, not off settings --
    # settings holds the TEMPERATURE derived from it, and the point here is
    # to report the model's own learned value.
    logit_scale = float(embedder.model.logit_scale.exp())
    print("--- logit scale ---")
    print(f"BiomedCLIP model.logit_scale.exp() = {logit_scale!r}")
    print(f"reciprocal (the deployed softmax temperature) = {1.0 / logit_scale!r}")
    print(f"settings.MODALITY_SOFTMAX_TEMPERATURE = {settings.MODALITY_SOFTMAX_TEMPERATURE!r}")
    print(
        "NOTE: logit_scale is NOT applied to the matrix below. The matrix is raw "
        "cosine\n  similarity. The scale is reported because it is what converts these "
        "cosines into\n  the gate's softmax logits."
    )
    print()

    matrix = vectors @ vectors.T

    print(f"--- full {len(prompts)}x{len(prompts)} pairwise cosine similarity matrix ---")
    header = "     " + "".join(f"{i:>10d}" for i in range(len(prompts)))
    print(header)
    for i, row in enumerate(matrix):
        print(f"[{i}]  " + "".join(f"{v:>10.{args.decimals}f}" for v in row))
    print()

    print("--- the same matrix, labelled, upper triangle only (each pair once) ---")
    for i in range(len(prompts)):
        for j in range(i + 1, len(prompts)):
            print(f"  {matrix[i, j]:.6f}   {prompts[i]!r}  <->  {prompts[j]!r}")
    print()

    # The pair the measurement was asked for, called out on its own.
    chest = prompts[0]
    abdominal_indices = [i for i, p in enumerate(prompts) if "abdominal" in p.lower()]
    print("--- chest prompt vs abdominal prompt (raw cosine) ---")
    if not abdominal_indices:
        print("  no prompt containing 'abdominal' is present in the deployed set")
    else:
        j = abdominal_indices[0]
        print(f"  chest prompt:     [0] {chest!r}")
        print(f"  abdominal prompt: [{j}] {prompts[j]!r}")
        print(f"  raw cosine similarity = {matrix[0, j]:.8f}")
        others = [
            (matrix[0, k], prompts[k])
            for k in range(len(prompts))
            if k not in (0, j)
        ]
        print()
        print("  for comparison, the chest prompt against every other negative prompt:")
        for value, prompt in sorted(others, reverse=True):
            print(f"    {value:.8f}  {prompt!r}")
    print()

    off_diagonal = matrix[~np.eye(len(prompts), dtype=bool)]
    print("--- off-diagonal summary ---")
    print(f"  min  {off_diagonal.min():.6f}")
    print(f"  mean {off_diagonal.mean():.6f}")
    print(f"  max  {off_diagonal.max():.6f}")


if __name__ == "__main__":
    main()
