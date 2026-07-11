# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A thesis research pipeline for **retrieval-augmented chest X-ray report generation** on the
IU/Indiana dataset. Phase 0 (retrieval validation gate) asked: does BiomedCLIP retrieve
clinically similar chest-X-ray cases well enough to make retrieval-augmented generation
viable? It passed (see below), so Phase 1 (dataset foundation) and Phase 2 (embedding
pipeline) were built on top of it and are also complete. **Phase 3 (ChromaDB retrieval
indexing) is next / in progress.**

`docs/methodology/development_log.md` is the authoritative, chronological record of every
decision, its rationale, and its validation evidence (including exact metrics/gate results)
for Phases 0–2 — read it before re-deriving *why* something was built a certain way. This
CLAUDE.md summarizes the parts relevant to writing code; the log has the full narrative and
thesis-ready writeups.

**This directory is a partial copy/archive of a larger frozen monorepo.** The dev log
records a frozen top-level layout of `ml/` + `backend/` (FastAPI, clean architecture) +
`frontend/` (Next.js) + `docs/` + `deployment/` (Docker Compose) that "never import each
other" except through the explicit `shared/` exception (see below). **Only `ml/`, `shared/`,
and `docs/` exist in this copy** — there is no `backend/`, `frontend/`, or `deployment/` here,
and no test suite. Don't assume backend/frontend code exists or try to wire into it; if asked
to build Phase 3+ work, it likely needs a new `ml/retrieval/` (or similar) module rather than
a `backend/` you can't see.

Everything is config-driven: no labels, paths, or parameters are hardcoded in the scripts.
`ml/config/label_mapping.yaml` (the finding taxonomy) is a clinical input that needs
clinically-informed review before being frozen — the code is agnostic to its contents.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # already present as .venv/ here
pip install -r requirements.txt
```

`requirements.txt` is split into a CPU-only block (Phase 0 steps 1–2: pandas/numpy/scipy/
sklearn/pyyaml) and a GPU/download block (step 3+: torch/torchvision/open_clip/pillow).
`chromadb` is commented out — only needed by the future production backend, not this eval.

Place dataset CSVs under `ml/datasets/raw/` and point `paths.image_root` in the config at
the `images/images_normalized` directory of `.png` files.

## Pipeline stages and run order

All scripts take `--config <path> --data-root .` and are safe/idempotent to re-run.
Config: `ml/config/phase0_config.yaml` (real run) or `ml/config/phase0_config_smoke.yaml`
(fast plumbing check — smaller encoder list, separate `*_smoke` output dirs, does not
touch real outputs).

**Phase 0 — retrieval validation (the gate):**
```bash
python ml/preprocessing/build_study_index.py --config ml/config/phase0_config.yaml --data-root .
python ml/preprocessing/make_splits.py       --config ml/config/phase0_config.yaml --data-root .
python ml/evaluation/run_encoder_eval.py     --config ml/config/phase0_config.yaml --data-root . --device cuda
python ml/evaluation/analyze_results.py      --config ml/config/phase0_config.yaml   # bootstrap CIs, GO/NO-GO gates
python ml/evaluation/build_manual_review_detail.py --config ml/config/phase0_config.yaml
```

**Phase 1 — dataset foundation (report cleaning, PHI masking, canonical metadata):**
```bash
python ml/preprocessing/clean_reports.py            --config ml/config/phase0_config.yaml --data-root .
python ml/preprocessing/phi_masking.py               --config ml/config/phase0_config.yaml --data-root . [--limit 20] [--cpu]
python ml/preprocessing/validate_masking_impact.py   --config ml/config/phase0_config.yaml --data-root . --n-sample 30
python ml/preprocessing/build_master_metadata.py     --config ml/config/phase0_config.yaml --data-root .
```

**Phase 2 — production embeddings:**
```bash
python ml/embeddings/generate_embeddings.py --config ml/config/phase0_config.yaml --data-root . [--limit 20]
python ml/embeddings/validate_embeddings.py --config ml/config/phase0_config.yaml --data-root .
```

**Smoke test** (shakes out image pathing/VRAM before an overnight full run, does not
touch the real scripts or outputs):
```bash
python ml/preprocessing/make_smoke_subset.py --in-dir ml/datasets/metadata --out-dir outputs_smoke --n-train 100 --n-val 30 --seed 42
```

There is no lint/test/build tooling configured (no pyproject.toml, no test suite) — verify
changes by running the relevant stage script and reading its printed report.

## Architecture

### Single source of truth, joined once
`ml/datasets/metadata/master_metadata.csv` (built by `build_master_metadata.py`) is the
canonical study-level file that consolidates every prior artifact (study index, cleaned
text, splits, PHI-masking log, projections). **No downstream module should re-join the
underlying CSVs itself** — read `master_metadata.csv`. It's idempotent: `created_at` is
preserved across re-runs per uid, `updated_at` always reflects the current run. Fields like
`processing_stage` and `embedding_cached` are *computed from what artifacts exist on disk*
each run, not manually tracked — a batch CSV can't safely hold live operational state
(that belongs in the backend's Postgres once built).

### Config is the only source of paths/params
`ml/config/phase0_config.yaml` centralizes every path (`paths:`), split ratios/seed/near-dup
threshold (`split:`), and eval k-values/encoders (`eval:`). Every script reads it and nothing
else — don't hardcode a path or parameter into a script; add it to the config schema instead.

### Label taxonomy is fully data-driven
`ml/config/label_mapping.yaml` maps raw `Problems` terms → curated classes (or drops them as
bare anatomy, or routes unlisted-but-pathological terms to `Other Abnormality`, logged for
review). `build_study_index.py` is agnostic to the taxonomy's contents — change the YAML,
re-run, nothing else moves. `enforce_normal_exclusive` drops `Normal` when it co-occurs with
an abnormal label (indexing artifact cleanup).

### Leakage-safe splitting is the load-bearing design decision
`make_splits.py` defeats two leakage hazards: study-level indexing (one row per uid) handles
view-pair leakage; **near-duplicate clustering** (TF-IDF cosine over normalized report text,
connected components at `near_dup_threshold`) handles template leakage, since near-identical
reports have different uids and would otherwise straddle train/test. ~28% of studies live in
a near-dup cluster — clusters are the atomic unit for a self-contained iterative
(Sechidis/Szymanski-style) stratified splitter, not individual studies. `splits.csv` is
seeded and meant to be reused by every later stage/ablation so the test set is touched
exactly once.

### Phase 0's decision rule: macro over micro, with real CIs
`run_encoder_eval.py` does image→image retrieval (the fair common denominator across
BiomedCLIP/generic CLIP/DenseNet121, since only BiomedCLIP has a shared image/text space).
KB = train split, queries = val split, relevance = curated-label overlap (graded). It writes
point estimates and per-query CSVs; **`analyze_results.py` is the actual decision layer** —
class-stratified paired bootstrap CIs, because Normal ≈ 47% of the data makes micro metrics
and pooled bootstrap resampling deceptively favorable. The three pre-registered gates (see
its docstring) must be read from `gate_decision_table.csv`, not the raw comparison table.
Adopt BiomedCLIP only if it clears random AND clip_generic on **macro** Recall@5/nDCG@10 with
CIs excluding 0, and wins concentrate on real findings (not just Normal/Other/Support
Devices). Embeddings are cached to disk per encoder/split (`cached_embed`) so re-running
analysis doesn't repeat GPU work.

### shared/ vs ml/ boundary
The frozen architecture has `ml/` and `backend/` never import each other (research stays
independent of the deployed app) — `shared/` is a **deliberate, one-off exception** to that
rule, not a generic dumping ground. `shared/embeddings/biomedclip_embedder.py` is the
**frozen production embedder**, living outside `ml/` so both the research pipeline and the
(not-present-in-this-copy) backend import the identical implementation — two copies would
risk silent drift between offline KB embeddings and live query embeddings without ever
erroring. It satisfies the backend's `IEmbedder` Protocol structurally (duck-typed) without
importing anything from a backend layer. `ml/` scripts are orchestration only (decide what to
embed, call the embedder, cache results); model/preprocessing logic never gets duplicated
into `ml/`. `run_encoder_eval.py`'s `embed_images()` is reused directly by
`validate_masking_impact.py` for the same reason — don't re-implement a second BiomedCLIP
loader. Before adding anything else to `shared/`, confirm it's genuinely cross-cutting
between `ml/` and a production consumer, not just convenient.

### PHI masking is a deployment-readiness feature, not a validated measurement
`phi_masking.py` (EasyOCR + solid black-box masking, not blur/inpaint — inpainting would
hallucinate content, conflicting with an evidence-grounded system) runs on IU X-ray images
that are already de-identified at the text level, so there's no burned-in-PHI ground truth
to measure recall against here. Detections are pipeline smoke-test signal, not a PHI-recall
metric — don't present it as validated detection performance. `validate_masking_impact.py`
instead checks that masking didn't damage diagnostic content, via pre/post BiomedCLIP cosine
similarity.

### Pandas groupby.apply gotcha (recurring pattern in this codebase)
Several scripts (`analyze_results.py`, `generate_embeddings.py`) deliberately use an explicit
per-group loop instead of `groupby().apply()` — pandas ≥2.2 drops the grouping column by
default when the applied function returns the group frame unchanged, which silently breaks
on pandas 3.x. Follow this pattern (explicit loop + `pd.concat`) rather than reintroducing
`groupby().apply()` for the same shape of operation.

### Validated results so far (from the dev log — don't re-derive, cite)
- **Phase 0 gate**: BiomedCLIP adopted as the frozen encoder. Gate 1 (vs random) passed
  cleanly; Gate 2 (vs clip_generic) passed on nDCG@10 but was inconclusive on Recall@5 at
  this sample size; Gate 3 satisfied (wins on 11/15 real-finding classes). Manual relevance
  check: label-overlap proxy is 89% precise / 49% recall vs. hand-read judgment — i.e. a
  conservative lower bound, so quantitative Phase 0 numbers likely *understate* true quality.
- **Phase 1**: 3,689 frontal images, 2,875 (77.9%) had ≥1 PHI region masked; embedding-impact
  validation showed mean cosine similarity 0.992 pre/post mask (0/50 flagged) — masking is
  safe. `master_metadata.csv` covers all 3,851 studies.
- **Phase 2**: 3,609 non-flagged studies with a frontal view fully embedded (train 2,462 /
  val 576 / test 571). Array-health checks all pass. Near-dup cluster cohesion and
  image↔text cross-modal retrieval are both real-but-modest signals (expected — the frozen
  retrieval path is image→image, not cross-modal; cross-modal weakness is a documented
  limitation, not a blocker).

## Known drift

`README.md` describes an earlier flat layout (`scripts/`, `config/` at repo root). The actual
paths are `ml/preprocessing/`, `ml/evaluation/`, `ml/embeddings/`, `ml/config/` — trust the
code/config over the README's directory diagram and command paths.
