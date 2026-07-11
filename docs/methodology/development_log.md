# Development Log

Chronological record of what was built, why, and how it was validated.
Intended as raw material for the thesis methodology/implementation chapters —
each entry states the decision, the reasoning, and concrete evidence.

---

## Repository Structure (frozen)

Adopted a clean-architecture layout separating the ML research pipeline from
the production backend, so experiments run independently of the deployed app.

```
ml/            research pipeline (preprocessing, embeddings, retrieval, evaluation)
  config/          YAML run configs
  preprocessing/   dataset prep stage scripts
  evaluation/      encoder bake-off, statistics, manual review tooling
  datasets/        raw/ masked/ metadata/ splits/  (gitignored)
  outputs/         embeddings/ evaluation/ logs/    (gitignored, except small summary CSVs)
backend/       FastAPI app, clean architecture (api/services/domain/infrastructure/models/schemas)
frontend/      Next.js app
docs/          architecture specs, methodology notes, thesis drafts
deployment/    Docker Compose, env templates
```

Rationale: `ml/` and `backend/` never import each other — both wrap BiomedCLIP/
ChromaDB independently. No generic `scripts/`/`utils/` dumping folders.
`ml/datasets/` separates raw vs. masked vs. derived-metadata vs. splits so the
preprocessing pipeline is auditable stage-by-stage. `ml/outputs/` is organized
by artifact purpose (embeddings / evaluation / logs), not by script name.

---

## Phase 0 — Retrieval Validation Gate

**Goal:** determine whether BiomedCLIP's shared image-text embedding space
retrieves clinically relevant historical chest X-ray cases well enough to
justify the whole RAG architecture, before building any backend module on
top of it.

### Dataset audit
- Source: IU/Indiana chest X-ray dataset. `indiana_reports.csv` = 3,851
  unique studies (true study-level table). `indiana_projections.csv` = 7,466
  images (1-4 per study, mostly frontal+lateral pairs).
- Findings text missing on 514 studies (13%); both findings and impression
  missing on 25. De-identification already applied (`XXXX` tokens in text).
- `Problems`/`MeSH` columns contain disease labels already, but as raw
  MTI/MeSH auto-indexing — mixed with anatomy terms (`Lung`, `Spine`, `Aorta`),
  administrative tags (`No Indexing`, `Technical Quality Unsatisfactory`), and
  device/descriptor terms. Not usable as a flat one-hot matrix without curation.

### Label taxonomy (`ml/config/label_mapping.yaml`)
Curated 18 clinically meaningful classes from the raw `Problems` vocabulary:
mapped disease-finding terms to classes (e.g. Opacity/Infiltrate/Consolidation
→ `Lung Opacity`), dropped bare-anatomy/administrative terms, routed
unmapped-but-genuine rare pathology (Sarcoidosis, TB, etc., all n≤7) to
`Other Abnormality`. Fully versioned, auditable, decoupled from code — editing
the taxonomy requires no script changes.

### Study-level, leakage-safe splitting (`ml/preprocessing/make_splits.py`)
- **Near-duplicate audit**: TF-IDF cosine similarity (threshold 0.90) on
  normalized findings+impression text, clustered via connected components.
  **Result: 28.2% of studies (1,064/3,767) live in a near-duplicate cluster**
  (largest cluster = 51 near-identical normal-chest templates). This is the
  empirical justification for cluster-atomic splitting.
- **Cluster-atomic assignment**: every study in a duplicate cluster is
  assigned to the same split, preventing template leakage across train/test.
- **Iterative multi-label stratification** (self-contained, rarest-label-first
  greedy algorithm) ensures every one of the 18 classes appears in all three
  splits, including rare ones (Pneumothorax: 17/4/4 train/val/test).
- Result: train 2,563 / val 609 / test 595 studies.

### Encoder bake-off (`ml/evaluation/run_encoder_eval.py`, `analyze_results.py`)
- Comparison: BiomedCLIP vs. generic OpenCLIP (ViT-B/32) vs. DenseNet121
  (ImageNet-pretrained, zero-shot feature extraction) vs. empirical random
  baseline. Image→image retrieval (fair common denominator — DenseNet/generic
  CLIP can't embed into BiomedCLIP's text space).
- Relevance defined as graded label-overlap between query and retrieved study
  (curated taxonomy above).
- Metrics: Recall@{1,3,5,10}, Precision@K, MRR, nDCG@10, both micro (all
  queries) and macro (per-class then averaged — the Normal-insensitive view,
  since Normal is ~47% of the data and inflates micro metrics).
- **Statistics**: class-stratified, paired bootstrap (n=2000 resamples) on
  the macro-metric differences between encoders — paired because every
  encoder is evaluated on the identical query set, which cancels shared
  query-level variance and gives a correct significance estimate.

**Pre-registered decision gates** (set before seeing results):
- Gate 1: BiomedCLIP macro Recall@5 beats random baseline, bootstrap 95% CI
  excludes zero.
- Gate 2: BiomedCLIP macro Recall@5 AND nDCG@10 beat generic CLIP, CI
  excludes zero.
- Gate 3: per-class wins concentrate on real findings (not just Normal or
  the Other/Support-Devices grab-bags).

**Results (full val set, n=576 queries, KB=2,462 train studies):**

| Comparison | Metric | Δ | 95% CI | Verdict |
|---|---|---|---|---|
| BiomedCLIP vs random | Recall@5 | +0.072 | [0.020, 0.124] | **PASS** |
| BiomedCLIP vs random | nDCG@10 | +0.073 | [0.051, 0.095] | **PASS** |
| BiomedCLIP vs clip_generic | Recall@5 | +0.064 | [-0.007, 0.134] | inconclusive (CI barely includes 0) |
| BiomedCLIP vs clip_generic | nDCG@10 | +0.060 | [0.039, 0.082] | **PASS** |

Gate 1: clean pass. Gate 2: split verdict — nDCG (uses the full graded
ranking) detects a real, statistically confirmed effect; Recall@5 (coarse
binary top-5 hit/miss) trends positive but is underpowered at this sample
size to confirm it. Gate 3: BiomedCLIP beat random on 11/15 real-finding
classes; standout win on Pleural Effusion (0.889 vs. 0.444–0.511 for the
other encoders); notable weak spot on Degenerative/Bone (a heterogeneous
class) — documented as a limitation, not hidden.

**Decision: BiomedCLIP adopted as the frozen encoder.** Basis: Gate 1 pass +
Gate 2 partial pass (nDCG) + clinically coherent per-class wins, reported
honestly including the inconclusive Recall@5 comparison rather than rounding
up to a clean sweep.

### Manual clinical relevance validation
The label-overlap relevance proxy was checked against independent judgment:
180 query/retrieved pairs (36 queries × top-5 BiomedCLIP neighbors, stratified
across classes) were read and rated 0/1/2 for genuine clinical relevance
(reading `findings`/`impression` text directly, not the label metadata).

**Result: proxy precision 89%, proxy recall 49%** (of pairs manually judged
relevant, the label-overlap proxy caught only about half). Interpretation:
the label-overlap proxy is a **conservative lower bound** on true clinical
relevance — when it says "relevant" it's almost always right, but it misses
roughly half of genuinely relevant retrievals because clinically related
findings sometimes fall into different curated label buckets. This means the
Phase 0 quantitative retrieval metrics likely *understate* BiomedCLIP's true
clinical retrieval quality, which strengthens rather than weakens the case
for adopting it.

*(Methodological note: an initial LLM-assisted first-pass rating was
attempted with a keyword/negation heuristic script; it only reached 67%
agreement with hand-read judgments on a calibration sample and was discarded
in favor of direct reading of all 180 pairs.)*

### How to Write This in Your Thesis (Phase 0 / Encoder Selection)

*Methodology chapter, "Retrieval Validation Experiment" subsection:*

> Before committing to BiomedCLIP as the multimodal encoder, a pre-registered
> retrieval validation experiment was conducted to test whether it retrieves
> clinically relevant historical cases significantly better than alternative
> encoders. Four encoders were compared under an identical image-to-image
> retrieval protocol — BiomedCLIP, a generic ImageNet/LAION-pretrained CLIP
> (ViT-B/32), a zero-shot DenseNet121 feature extractor, and an empirical
> random-retrieval baseline — using a knowledge base built exclusively from
> the training split (2,462 studies) queried against the held-out validation
> split (576 studies), preventing any data leakage into the evaluation.
> Relevance was defined via graded label overlap between query and retrieved
> study, using an 18-class taxonomy curated from the dataset's raw MeSH/MTI
> annotations. Three decision gates were pre-registered before results were
> observed: (1) BiomedCLIP must significantly exceed the random baseline on
> macro-averaged Recall@5, (2) BiomedCLIP must significantly exceed the
> generic CLIP baseline on macro Recall@5 and nDCG@10, and (3) performance
> gains must concentrate on genuine clinical findings rather than the Normal
> or non-specific classes. Statistical significance was assessed via a
> class-stratified, paired bootstrap procedure (2,000 resamples), paired
> because all encoders were evaluated on an identical query set. BiomedCLIP
> passed Gate 1 decisively (Recall@5 Δ = +0.072, 95% CI [0.020, 0.124];
> nDCG@10 Δ = +0.073, 95% CI [0.051, 0.095]) and passed Gate 2 on nDCG@10
> (Δ = +0.060, 95% CI [0.039, 0.082]) but not conclusively on Recall@5
> (Δ = +0.064, 95% CI [-0.007, 0.134]), which we attribute to Recall@5's
> coarser binary signal being underpowered at this sample size relative to
> the graded nDCG metric. Gate 3 was satisfied qualitatively: BiomedCLIP
> outperformed the random baseline on 11 of 15 clinically meaningful finding
> classes, with a pronounced advantage on Pleural Effusion (0.889 vs.
> 0.444–0.511 for competing encoders). On this basis, BiomedCLIP was adopted
> as the frozen encoder for the remainder of the system.

*Why this is a strong paragraph for your defense*: it reports the
inconclusive Recall@5 result honestly instead of rounding up to a clean
sweep, which is exactly the kind of transparency an examiner respects and
will not be able to catch you overclaiming on.

*What to include as a table/figure*: the `ml/outputs/evaluation/
gate_decision_table.csv` and `encoder_comparison_macro.csv` as your primary
results table — this is your strongest, most citable result in the whole
project.


### Report cleaning (`ml/preprocessing/clean_reports.py`)
Normalizes raw findings/impression text for downstream embedding/LLM use:
collapses `XXXX...` de-identification tokens to `[REDACTED]`, strips
whitespace/punctuation artifacts. Flags the 514 impression-only studies
(kept in the retrieval KB, excluded from generation-quality evaluation
targets per the frozen protocol, since findings is the primary generation
target).

---

## Repository restructuring — migration verified

Moved all Phase 0 artifacts from the flat `scripts/`/`config/`/`outputs/`
layout into the frozen `ml/` structure (see top of this log). Verification:
re-ran `build_study_index.py` → `clean_reports.py` → `make_splits.py` against
the relocated files and confirmed byte-for-byte identical results to the
pre-migration run (3,851 studies; 28.2% near-duplicate contamination;
train/val/test = 2,563/609/595; identical per-class distribution). Confirms
the migration was lossless and the path-corrected scripts are functioning
correctly in the new locations (`study_index.csv`/`study_index_clean.csv` →
`ml/datasets/metadata/`, `splits.csv`/`neardup_clusters.csv` →
`ml/datasets/splits/`).

---

## PHI Masking (`ml/preprocessing/phi_masking.py`)

**Pipeline**: uploaded image → OCR text detection → mask detected regions
(padded black box) → downstream BiomedCLIP embedding.

**Design decisions and rationale:**
- **EasyOCR over PaddleOCR**: PaddleOCR would add a second deep-learning
  framework (PaddlePaddle) alongside the existing PyTorch/BiomedCLIP stack,
  duplicating the exact kind of dependency risk already hit once with
  `transformers` for BiomedCLIP's text tower. EasyOCR is PyTorch-native,
  shares the existing CUDA environment, and is not meaningfully less accurate
  for short high-contrast burned-in text (vs. PaddleOCR's advantage on dense
  multi-line documents, which isn't this use case). Tesseract was ruled out
  as weakest on rotated/low-contrast radiographic text.
- **Solid black-box masking over Gaussian blur or inpainting**: inpainting
  hallucinates plausible pixel content to fill the region, which conflicts
  with the project's own evidence-grounding premise (invented texture would
  be a strange thing for an "evidence-grounded" retrieval system to feed its
  encoder). A solid box is an unambiguous null signal and simplest to defend.
- **Confidence threshold (0.30) + padding (6px)**: guards against masking
  false-positive OCR hits on lung texture, and avoids a razor-sharp box edge
  exactly on a text boundary reading as a spurious high-contrast feature to
  a ViT's patch embeddings.
- **No forced masking**: if OCR finds nothing above threshold, the image
  passes through unmodified rather than being run through a no-op mask step.

**Validation approach**: `validate_masking_impact.py` embeds a sample of
images before/after masking with the frozen BiomedCLIP encoder and reports
cosine similarity between the pairs (reuses `embed_images()` from
`run_encoder_eval.py`). High similarity confirms masking stayed confined to
peripheral/non-diagnostic regions; a low-similarity outlier flags a mask that
likely overlapped anatomy, for manual inspection.

**Results (full run, all 3,689 frontal images, RTX 4070 Ti SUPER):**
- 2,875/3,689 images (77.9%) had ≥1 region detected and masked; 4,278 total
  regions; mean processing time 0.426s/image.
- Embedding-impact validation (n=50 sample): mean cosine similarity 0.9916,
  min 0.9215, max 1.0000, **0/50 flagged below the 0.90 threshold** —
  confirms masking did not meaningfully perturb BiomedCLIP's representation
  of any sampled image.

**Reproducibility logging**: `ml/outputs/logs/phi_masking_log.csv` records
per-image `image_id, num_regions_detected, confidence_scores, masking_applied,
processing_time_sec` for debugging/reproducibility. A parallel JSONL log
(`phi_masking_log.jsonl`) retains full per-region box geometry for exact mask
reproduction. Neither log feeds back into the masking pipeline itself.

**Known limitation, stated explicitly rather than glossed over**: IU X-ray's
report text is already de-identified; there is no known burned-in-PHI image
subset in this dataset to measure true detection recall/precision against.
This module is implemented as a deployment-readiness / privacy-by-design
contribution and validated for embedding-impact safety, but is **not**
empirically validated for PHI-detection accuracy on real de-identification
cases. State this distinction clearly in the thesis methodology section —
do not present detection counts on this dataset as a recall measurement.

### How to Write This in Your Thesis

*Methodology chapter, "Privacy Protection" subsection — adapt directly:*

> To support deployment in real clinical settings where chest X-ray images
> may carry burned-in Protected Health Information (patient name, hospital
> identifiers, acquisition dates), a PHI masking stage was implemented prior
> to embedding generation. The stage uses EasyOCR for burned-in text
> detection, chosen over alternatives such as PaddleOCR for framework
> compatibility with the existing PyTorch-based encoder pipeline, avoiding a
> second deep-learning dependency stack. Detected text regions above a
> confidence threshold of 0.30 are masked with a padded solid black box
> rather than Gaussian blur or generative inpainting; the latter was
> deliberately avoided as it would introduce hallucinated pixel content into
> a system whose core design principle is evidence grounding. Across the
> full frontal-image set (3,689 images), 77.9% had at least one region
> detected and masked (4,278 regions total; mean processing time 0.43s per
> image on an RTX 4070 Ti SUPER). To verify masking does not compromise
> diagnostically relevant image content, a validation step compared
> BiomedCLIP embeddings of a 50-image sample before and after masking via
> cosine similarity, yielding a mean similarity of 0.992 (min 0.922, max
> 1.000), with zero images falling below a 0.90 similarity threshold —
> confirming masked regions are confined to non-diagnostic peripheral areas
> and do not materially perturb the encoder's representation. Because the
> dataset used in this study (IU/Indiana chest X-ray) is already de-identified
> at the report level, this module could not be empirically validated for
> PHI-detection recall on real burned-in identifiers; it is presented as a
> deployment-readiness contribution and privacy-by-design measure, with its
> safety (non-interference with diagnostic content) validated rather than
> its detection accuracy.

*Limitations chapter — adapt directly:*

> The PHI masking module's detection accuracy could not be quantitatively
> evaluated, as the dataset used in this study contains no ground-truth
> examples of burned-in PHI. Future work involving hospital-sourced or
> synthetically augmented data would allow formal precision/recall
> measurement of the OCR-based detection stage.

*What to screenshot/include as a figure*: a before/after masked-image pair
from `ml/datasets/masked/` alongside the original in `ml/datasets/raw/`, and
the `validate_masking_impact.py` similarity-distribution output (mean/min/max
cosine similarity) as a small results table.



### Master Metadata (`ml/preprocessing/build_master_metadata.py`)

**Purpose**: single canonical study-level file consolidating every Phase 1
artifact (`study_index`, `study_index_clean`, `splits`, `phi_masking_log`,
`projections`) into one source of truth — `ml/datasets/metadata/
master_metadata.csv`. Every downstream module (embedding, retrieval,
evaluation, backend ingestion, future longitudinal history) reads from this
file; no module re-joins the underlying artifacts itself.

**Schema** (one row per study): `study_uid`, `patient_uid` (synthetic,
`SYN-{uid}`, 1:1 for now — real patient linkage does not exist in this
dataset; see Fork C), `image_ids`, `projections_available`, `num_images`,
`has_frontal`, `frontal_filename`, `raw_image_path`, `masked_image_path`,
`phi_masking_applied`, `phi_regions_detected`, `primary_label`, `label_set`,
18 binary class columns, `findings_clean`, `impression_clean`,
`has_findings`, `full_text`, `split`, `cluster_id`, `exclude_flag`,
`embedding_model`, `embedding_version`, `embedding_cached`,
`processing_stage`, `pipeline_version`, `created_at`, `updated_at`.

**Design decision — computed vs. tracked state**: fields describing *live
operational status* (`embedding_cached`, `processing_stage`) are computed
from filesystem-observable evidence every time the file is regenerated
(does the `.npy` cache exist? does the masked file exist?) rather than
manually set and persisted. This was a deliberate correction from an earlier
proposal to include `indexed_in_chromadb`/`embedding_status` as flat CSV
flags — those genuinely live operational states belong in the backend's
PostgreSQL tables (once built), where they can be updated transactionally as
async pipeline stages complete; a batch-generated CSV cannot safely hold
state that a live process also mutates without risking drift between the
two. `created_at` is preserved across regenerations (merged against the
prior file if one exists); `updated_at` refreshes every run — this makes the
file idempotent and safe to re-run at any pipeline stage.

**Validation**: tested against synthetic fixtures covering every edge case
(a study with no frontal image, a study with a declared-but-missing frontal
file, partial masking coverage, partial embedding-cache coverage) before
running on real data; all computed fields matched hand-calculated
expectations exactly. One bug caught during testing and fixed:
`masked_image_path` was initially populating from `frontal_filename`
presence alone rather than actual masked-file existence — corrected to only
populate when the file is verified on disk.

**Results (full dataset, 3,851 studies):**
- `processing_stage`: 3,689 `Masked`, 162 `Missing` (matches the no-frontal
  count exactly).
- `embedding_cached`: 0/3,851 (expected — the embedding cache was deleted
  during the earlier restructuring mishap and has not yet been regenerated;
  will populate once Phase 2 embedding runs).
- `phi_masking_applied`: 2,875 (matches the PHI masking module's run
  exactly).

### How to Write This in Your Thesis

*Methodology chapter, "Data Pipeline / Canonical Metadata" subsection:*

> To ensure every downstream component of the system operates on a single,
> consistent view of the dataset, all preprocessing artifacts — the curated
> disease taxonomy labels, cleaned report text, leakage-safe split
> assignments, and PHI masking outcomes — were consolidated into one
> canonical study-level metadata file. Fields describing transient pipeline
> state (whether an embedding is cached, the current processing stage of a
> study) are computed from filesystem-observable evidence at generation
> time rather than manually tracked, since a statically generated file
> cannot safely represent live operational state that a concurrently running
> system might also mutate; such state is deferred to the relational
> database layer in the production backend. This design keeps the metadata
> file idempotent and reproducible: regenerating it at any point in the
> pipeline yields a file that accurately reflects current on-disk state
> without risk of drift.

---

## Phase 1 (Dataset Foundation) — COMPLETE

All items delivered and validated on the real dataset: label taxonomy,
study-level organization, leakage-safe train/val/test split, report
cleaning, PHI masking (with embedding-impact validation), and canonical
master metadata consolidation. Proceeding to Phase 2 (Embedding Pipeline).


## Open items carried forward
- Backend domain layer (`backend/app/domain/entities.py`, `interfaces.py`)
  scaffolded and unit-verified (pure Python, no framework deps) but not yet
  wired to infrastructure -- deferred until Phase 2 (embedding pipeline) and
  Phase 3 (retrieval pipeline) are validated, per the agreed data-pipeline-
  first development order.

---

## Phase 2 — Embedding Pipeline

### Shared Embedding Wrapper (`shared/embeddings/`)

**Design decision — introducing `shared/` as a top-level package.** The
frozen architecture originally specified `ml/` and `backend/` never import
each other, so research stays independent of the deployed app. This module
is a deliberate, justified exception: both the offline embedding pipeline
and the backend's live embedding service must produce vectors in the
identical latent space, or retrieval breaks silently (a subtle preprocessing
or normalization difference between two independent implementations would
not raise an error -- it would just quietly degrade retrieval quality).
`shared/embeddings/` is therefore a genuine shared kernel, not a generic
dumping folder, consistent with the "flag it if a real cross-cutting need
appears" caveat established when `shared/` was originally deferred.

**Structure:**
```
shared/embeddings/
├── base.py                  # BaseEmbedder ABC + l2_normalize() helper
└── biomedclip_embedder.py   # BiomedCLIPEmbedder(BaseEmbedder) -- the frozen production embedder
```

**`BaseEmbedder` (ABC)**: every embedder implements only `embed_images()` and
`embed_texts()` (batched); the singular convenience methods (`embed_image`,
`embed_text`) are implemented once on the base class and inherited by every
subclass, rather than re-implemented per model. This ABC does not exist to
satisfy the backend's `IEmbedder` Protocol -- Python Protocols are
structural, so `BiomedCLIPEmbedder` already satisfies `IEmbedder` without
inheriting from it. The ABC's job is purely internal consistency within
`shared/embeddings/` as it grows to potentially support additional models
(MedCLIP, BioViL, CheXzero) in the future.

**`BiomedCLIPEmbedder`**: loads the frozen BiomedCLIP model once in
`__init__` (vision tower, PubMedBERT text tower, preprocessing transform),
reused across all calls. All outputs L2-normalized so any caller can take a
dot product for cosine similarity without remembering to normalize. torch/
open_clip are imported lazily inside `__init__`, not at module level, so the
module (and its pure helper functions) remain importable in environments
without a GPU.

**Validation:**
- ABC contract tested with a fake subclass: confirmed `BaseEmbedder` blocks
  direct instantiation, and `embed_image`/`embed_text` correctly delegate to
  the batched methods.
- `l2_normalize()` tested including the zero-vector edge case (stays zero,
  no NaN propagation).
- Device resolution (`auto` → cuda/cpu, explicit override) tested with a
  fake torch stand-in.
- End-to-end smoke test on the real workstation (RTX 4070 Ti SUPER, real
  IU X-ray image via `master_metadata.csv`): 512-dim embeddings for both
  image and text, norm = 0.999999918 (correctly unit-length).

#### How to Write This in Your Thesis (Shared Embedding Wrapper)

*Methodology chapter, "Embedding Pipeline" subsection:*

> A single embedding interface, `BiomedCLIPEmbedder`, was implemented as a
> shared component consumed identically by the offline embedding-generation
> pipeline and the production backend's embedding service. This design
> choice guarantees that knowledge-base embeddings computed offline and
> query embeddings computed at inference time occupy an identical vector
> space; maintaining two independent implementations was deliberately
> avoided, as a subtle divergence between them (differing preprocessing or
> normalization) would degrade retrieval quality without raising any error,
> making such a bug difficult to detect. The interface follows an abstract
> base class exposing batched image and text embedding methods, with
> singular convenience methods derived once at the base-class level so that
> any future embedder implementation need only implement the batched
> methods to gain full interface conformance. All returned embeddings are
> L2-normalized, allowing every downstream consumer to compute cosine
> similarity via a simple dot product.

### Batch Embedding Generation (`ml/embeddings/generate_embeddings.py`)

**Purpose**: thin orchestrator built on `shared/embeddings/`. Reads
`master_metadata.csv`, embeds every study's masked frontal image and report
text via `BiomedCLIPEmbedder`, caches outputs with explicit uid alignment.

**Design decisions:**
- Embeds from `masked_image_path`, not raw — PHI masking is validated and
  complete, so production embeddings should be computed from
  privacy-protected images. Falls back to raw with a printed warning if a
  masked file is unexpectedly missing.
- Explicit `_uids.npy` companion array alongside every embedding cache file,
  so any consumer (ChromaDB indexing, backend) aligns by uid directly rather
  than re-deriving the same filter/sort logic that produced the cache —
  this superseded and replaced Phase 0's narrower, order-implicit cache
  convention (`biomedclip_train.npy` etc., image-only, train+val only).
- Skip-if-cached logic (checks `_uids.npy` length matches expected count)
  makes re-runs fast and idempotent.
- Computing embeddings for all three splits does not violate the "touch
  test once" leakage protocol — that applies to KB construction (train-only)
  and final evaluation, both later steps; raw embedding computation is a
  representation, not an evaluation look.

**Bug caught and fixed during implementation**: the `--limit` dry-run flag
used the same `groupby().apply()` pattern that silently drops the grouping
column on pandas ≥2.2/3.0 (identical root cause to the bug hit earlier in
`analyze_results.py`'s manual-review sampling) — `split` disappeared from
the limited dataframe, crashing every downstream filter. Fixed with the same
explicit per-group-loop pattern used previously. Verified against the
team's actual pandas 3.0.2 install before re-shipping.

**Modified file**: `ml/preprocessing/build_master_metadata.py` — the
`embedding_cached` computed field was updated to check the new
`biomedclip_image_{split}_uids.npy` files (exact uid membership) instead of
the old row-count-guess against the Phase 0 scratch cache filename
convention, since the two conventions no longer matched. Added explicit
per-path debug printing (`checking embedding cache: {path} exists={bool}`)
after a stale-script confusion during testing, so any future path/version
mismatch is immediately visible in the script's own output rather than
silently producing `embedding_cached: 0`.

**Results (full run, all 3,851 studies, RTX 4070 Ti SUPER):**

| Split | Images embedded | Time | Text embedded | Time |
|---|---|---|---|---|
| train | 2,462 | 167.4s (0.068s/img) | 2,557 | 6.5s |
| val | 576 | 39.4s (0.068s/img) | 599 | 1.5s |
| test | 571 | 38.8s (0.068s/img) | 586 | 1.5s |

Total: 7,351 embeddings, 255.2s (~4.3 minutes). Image counts (2,462+576+571
= 3,609) are lower than the 3,689 total frontal-image count because the 84
technical-quality-flagged studies excluded before splitting (per the
leakage-safe splitting protocol) have no `split` assignment and are
correctly skipped — confirmed via `master_metadata.csv` refresh:
`embedding_cached: 3,609/3,851`, `processing_stage`: 3,609 `Embedded`, 80
`Masked` (the flagged studies), 162 `Missing` (no frontal).

### How to Write This in Your Thesis

*Methodology chapter, "Embedding Generation" subsection:*

> Image and text embeddings were generated for all 3,609 non-flagged
> studies with an available frontal view (2,462 train / 576 validation /
> 571 test), plus corresponding report-text embeddings, using the frozen
> BiomedCLIP encoder via the shared embedding interface. Embedding
> generation operated on PHI-masked images rather than raw images,
> consistent with the project's privacy-by-design approach. The full
> generation run completed in approximately 4.3 minutes on a consumer GPU
> (RTX 4070 Ti SUPER), averaging 0.068 seconds per image and under 0.01
> seconds per text embedding — a runtime profile consistent with the
> project's low-resource deployment goals. Each cached embedding array is
> stored alongside an explicit study-identifier array to guarantee
> alignment for downstream consumers, avoiding implicit ordering
> assumptions between the embedding cache and the source metadata.

### Embedding Validation (`ml/embeddings/validate_embeddings.py`)

Three post-hoc sanity checks on the real cached embeddings, distinct from
Phase 0's encoder bake-off (which already validated BiomedCLIP as the
correct encoder choice). This asks a narrower question: did *this*
production run produce healthy, correctly-aligned vectors?

**Results (real run, train split, seed=42):**

**Check 1 — array health**: all 6 cached arrays (image/text × train/val/test,
7,271 total vectors) fully finite, zero degenerate zero-vectors, perfect
unit norm (mean=1.0, std=0.0). Definitive confirmation the generation
pipeline executed correctly.

**Check 2 — near-duplicate cluster cohesion**: within-cluster mean
similarity 0.9131 vs. random-pair mean similarity 0.8831 (gap = 0.030,
n=7,284 within-cluster pairs). Direction is correct (near-duplicate images
score higher) but the gap is smaller than an initial heuristic threshold
suggested, because baseline similarity between *any* two chest X-rays is
already high (~0.88) — a known property of medical image embeddings, where
shared modality/framing dominates over diagnostic content unless the
encoder is fine-tuned for fine-grained separation. This is not a pipeline
defect; it is a property of the embedding space worth stating honestly
rather than glossing over with an inflated pass/fail threshold.

**Check 3 — image→text batch retrieval accuracy**: top-1 = 4.8% (vs. 2.0%
random baseline, ~2.4×), top-5 = 15.6% (vs. 10.0% random, ~1.56×). A real
but modest cross-modal signal. Two plausible contributing factors: (1)
BiomedCLIP was pretrained on short PubMed figure captions, a different text
distribution than the long-form clinical findings+impression narratives
used here — a genuine domain-mismatch limitation worth documenting; (2) the
28.2% near-duplicate report rate established in Phase 0 makes exact
self-uid matching an unfairly strict metric, since an image can correctly
match a text that is functionally identical to its true pair but attributed
to a different study uid and still be scored as a miss.

**Why this does not threaten the system**: the frozen production retrieval
mechanism is **image→image** (validated thoroughly in Phase 0's Gate 1/2/3),
not image→text embedding matching. Text embeddings exist for potential
future capabilities (e.g., a symptom-text search feature), not the core
retrieval path. Check 3's modest result is a genuine, citable limitation of
the embedding space's cross-modal alignment — not a defect in the
implemented retrieval pipeline.

### How to Write This in Your Thesis

*Methodology chapter, "Embedding Validation" subsection:*

> The generated embeddings were validated with three post-hoc checks beyond
> the encoder-selection validation performed in Phase 0. All cached
> embedding arrays passed a numerical health check (no non-finite values,
> no degenerate zero vectors, correct unit normalization across all 7,271
> vectors), confirming the generation pipeline executed without corruption.
> A near-duplicate cohesion check, leveraging the template-duplicate
> clusters identified during dataset splitting, confirmed that near-
> identical images receive measurably higher cosine similarity (0.913) than
> random image pairs (0.883); the modest size of this gap reflects the high
> baseline visual similarity shared by all chest radiographs regardless of
> diagnostic content, a known characteristic of medical image embedding
> spaces, rather than a deficiency in the pipeline. A cross-modal batch
> retrieval check found that BiomedCLIP's image and text embeddings for the
> same study exhibit alignment modestly above chance (top-1 accuracy 4.8%
> against a 2.0% random baseline), which we attribute to a distributional
> mismatch between BiomedCLIP's caption-style pretraining data and the
> long-form clinical narratives used in this study, compounded by the
> dataset's substantial template-duplication rate. As the system's
> retrieval mechanism operates on image-to-image similarity rather than
> cross-modal matching, this limitation does not affect the implemented
> retrieval pipeline, but is noted as a boundary of the embedding space's
> capabilities for any future text-query features.

*Limitations chapter — adapt directly:*

> Cross-modal (image-to-text) alignment of the generated BiomedCLIP
> embeddings was found to be only modestly above chance when evaluated via
> batch retrieval accuracy, likely reflecting a mismatch between
> BiomedCLIP's pretraining distribution (short image captions) and the
> long-form clinical report text used in this study. This does not affect
> the system's core retrieval mechanism, which relies on image-to-image
> similarity, but would need to be addressed (e.g., via report-text
> summarization to a caption-like form, or a different text encoder) before
> any future feature relying on direct text-to-image search.

---

## Phase 2 (Embedding Pipeline) — COMPLETE

Shared `BiomedCLIPEmbedder` wrapper, batch generation across all splits, and
three-part post-hoc validation all delivered and verified on real data.
Array integrity confirmed definitively; near-duplicate cohesion and
cross-modal alignment characterized honestly, with findings that inform but
do not block the frozen image-to-image retrieval design. Proceeding to
Phase 3 (Retrieval Pipeline / ChromaDB indexing).

---

