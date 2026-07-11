# AI-Assisted Radiology Reporting Workspace

Retrieval-Augmented Generation (RAG) system for bilingual (English/Bengali)
chest X-ray radiology report generation, designed for low-resource deployment
in Bangladesh. Undergraduate thesis project, Brac University.

## Status

- **Phase 0 (Retrieval Validation Gate)** — COMPLETE. BiomedCLIP adopted as
  the frozen encoder following a pre-registered, statistically validated
  bake-off against generic CLIP, DenseNet121, and a random baseline.
- **Phase 1 (Dataset Foundation)** — COMPLETE. Label taxonomy, leakage-safe
  splitting, report cleaning, PHI masking, canonical metadata.
- **Phase 2 (Embedding Pipeline)** — COMPLETE. Shared BiomedCLIP embedder,
  full batch embedding generation, post-hoc validation.
- **Phase 3 (Retrieval Pipeline)** — in progress.

Full methodology, design rationale, and validated results for every module:
see [`docs/methodology/development_log.md`](docs/methodology/development_log.md).

## Repository Structure

```
ml/              Research pipeline (preprocessing, embeddings, evaluation)
shared/          Code shared between ml/ and backend/ (the frozen embedder)
backend/         FastAPI application (domain layer scaffolded, in progress)
frontend/        Next.js application (not yet started)
docs/            Architecture specs, methodology notes, development log
deployment/      Docker Compose, environment templates
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate       # or .venv\Scripts\Activate.ps1 on Windows
pip install -r ml/requirements.txt
```

Place the IU/Indiana chest X-ray dataset CSVs and images under
`ml/datasets/raw/` (see `.gitignore` — this directory is not tracked).

## Running the Pipeline

```bash
# Phase 1: dataset foundation
python ml/preprocessing/build_study_index.py --config ml/config/phase0_config.yaml --data-root .
python ml/preprocessing/clean_reports.py --config ml/config/phase0_config.yaml --data-root .
python ml/preprocessing/make_splits.py --config ml/config/phase0_config.yaml --data-root .
python ml/preprocessing/phi_masking.py --config ml/config/phase0_config.yaml --data-root .
python ml/preprocessing/build_master_metadata.py --config ml/config/phase0_config.yaml --data-root .

# Phase 2: embedding pipeline
python ml/embeddings/generate_embeddings.py --config ml/config/phase0_config.yaml --data-root .
python ml/embeddings/validate_embeddings.py --config ml/config/phase0_config.yaml --data-root .
```

## Team

Three-student undergraduate thesis team, Department of Computer Science and
Engineering, Brac University.
