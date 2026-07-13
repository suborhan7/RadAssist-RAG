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

## Phase 3 — Retrieval Pipeline: Architecture (FROZEN)

**Status: approved and frozen.** Not to be redesigned without a critical
correctness issue.

### Corrections made to the initial proposal before freezing

1. **No new `SplitManager` module.** `master_metadata.csv` (Phase 1, frozen)
   already carries the `split` column. Introducing a split-decision module
   would mean re-touching frozen Phase 1 output. Instead: a new,
   Phase-3-owned `prepare_train_metadata.py` filters the existing frozen
   file — satisfies single-responsibility (the Indexer never decides split
   membership) without redesigning anything upstream.
2. **`image_path` in ChromaDB metadata must be the masked path, not raw.**
   Phase 2 embeddings were computed from `masked_image_path`. Pointing
   metadata at raw images would mean any future explainability feature
   displays a different image than the one actually embedded — a silent
   correctness bug.
3. **`indexed_at` is a distinct field from `master_metadata`'s own
   `created_at`** — the former is when a record enters ChromaDB, the latter
   is when the study record was first generated; conflating them loses
   information.

### Architecture

```
master_metadata.csv (Phase 1, frozen)
        |
        v
prepare_train_metadata.py   [NEW, Phase 3]
        |  filters: split=='train' AND has_frontal AND embedding_cached
        v
train_metadata.csv
        |
        |         biomedclip_image_train.npy
        |         biomedclip_image_train_uids.npy   (Phase 2, frozen)
        |                    |
        v                    v
        build_chroma_index.py   [NEW, Phase 3]
                    |
                    v
              Validation gate (hard-fail, DB untouched if fail)
                    |
                    v
         Delete old collection -> Create new (cosine space) -> Batch upsert
                    |
                    v
         Persistent ChromaDB collection + index_summary.json + log
```

### Module responsibilities

| Module | Responsibility | Must NOT do |
|---|---|---|
| `prepare_train_metadata.py` | Read `master_metadata.csv`, filter to indexable train rows, write `train_metadata.csv` | Touch embeddings, touch ChromaDB, decide split logic |
| `build_chroma_index.py` | Load `train_metadata.csv` + embedding cache, validate, create/populate collection, write summary + log | Generate embeddings, re-derive split membership, proceed past a validation failure |

### Folder structure

```
ml/retrieval/
├── prepare_train_metadata.py
└── build_chroma_index.py

ml/datasets/metadata/
└── train_metadata.csv            # derived, same home as other *_metadata.csv files

ml/outputs/retrieval/
├── chroma_db/                    # ChromaDB persistent store (gitignored)
└── index_summary.json

ml/outputs/logs/
└── chroma_indexing_{timestamp}.log
```

**`.gitignore` addition required**: `ml/outputs/retrieval/chroma_db/` (large, regeneratable binary store).

### ChromaDB metadata schema

| Field | Source | Notes |
|---|---|---|
| `study_uid` | `master_metadata.study_uid` | Chroma document ID |
| `patient_uid` | `master_metadata.patient_uid` | synthetic; future longitudinal-demo linkage |
| `image_path` | `master_metadata.masked_image_path` | masked, matches what was embedded |
| `projection` | fixed `"Frontal"` | frontal-only per frozen decision |
| `primary_label` | `master_metadata.primary_label` | |
| `label_set` | `master_metadata.label_set` | semicolon-joined |
| `is_normal` | computed | cheap boolean filter |
| `findings` | `master_metadata.findings_clean` | direct explainability use, no second join |
| `impression` | `master_metadata.impression_clean` | |
| `dataset` | fixed `"IU_XRay"` | supports future multi-dataset collections |
| `embedding_model` | `master_metadata.embedding_model` | `"biomedclip"` |
| `embedding_version` | `master_metadata.embedding_version` | `"v1"` |
| `split` | fixed `"train"` | defense-in-depth, redundant with collection name |
| `cluster_id` | `master_metadata.cluster_id` | near-dup diagnostic at retrieval time |
| `indexed_at` | generated at index time | distinct from metadata's `created_at` |

### Collection naming

`{dataset}_{embedding_model}_{embedding_version}_{split}` -> e.g.
`iu_cxr_biomedclip_v1_train`. Must satisfy ChromaDB's real naming
constraints (alphanumeric/underscore/hyphen, start/end alphanumeric,
3-63 chars) -- a hard runtime error if violated, not a style preference.

### Validation strategy (hard-fail, checked before any DB mutation)

- Every row has `split == 'train'` (defense-in-depth leakage guard)
- Set-equality between metadata uids and embedding-cache uids (exact
  mismatch list on failure, not just a count)
- No duplicate `study_uid`
- No missing/null `masked_image_path`, `primary_label`, `study_uid`
- Embedding array: correct dimension (512), all finite, unit-norm, zero
  degenerate vectors (re-running Phase 2's health check at index time)
- Collection name passes naming-constraint check
- Post-insertion: `collection.count()` exactly equals validated input count

### Index summary (`index_summary.json`)

Fields: `collection_name`, `dataset`, `embedding_model`, `embedding_version`,
`pipeline_version`, `split`, `source_row_count`, `num_indexed`,
`failed_records`, `duplicate_count`, `embedding_dimension`,
`class_distribution`, `distinct_neardup_clusters_represented`,
`validation_passed`, `warnings`, `execution_time_sec`, `timestamp`.

### Sequence diagram

```mermaid
sequenceDiagram
    participant U as User
    participant P as prepare_train_metadata.py
    participant I as build_chroma_index.py
    participant MM as master_metadata.csv
    participant EMB as embedding cache (.npy)
    participant CH as ChromaDB

    U->>P: run
    P->>MM: read
    P->>P: filter split=='train' & has_frontal & embedding_cached
    P->>P: write train_metadata.csv

    U->>I: run --dry-run
    I->>I: read train_metadata.csv + embedding cache
    I->>I: run full validation
    I-->>U: print report only, DB untouched

    U->>I: run (real)
    I->>I: read + validate (same checks)
    alt validation fails
        I-->>U: abort, write log, exit non-zero, old collection untouched
    else validation passes
        I->>CH: delete existing collection (if present)
        I->>CH: create_collection(name, hnsw:space="cosine")
        loop batches
            I->>CH: upsert(ids, embeddings, metadatas)
        end
        I->>CH: collection.count()
        I->>I: verify count == expected
        I->>I: write index_summary.json + log
        I-->>U: print summary
    end
```

### Architecture diagram

```mermaid
flowchart TD
    A[master_metadata.csv<br/>Phase 1, frozen] --> B[prepare_train_metadata.py]
    B --> C[train_metadata.csv]
    D[biomedclip_image_train.npy<br/>+ _uids.npy<br/>Phase 2, frozen] --> E[build_chroma_index.py]
    C --> E
    E --> F{Validation}
    F -->|fail| G[Abort - old collection untouched]
    F -->|pass| H[Delete old collection if exists]
    H --> I[Create collection<br/>cosine space]
    I --> J[Batch upsert]
    J --> K[Post-insert count check]
    K --> L[(ChromaDB store<br/>ml/outputs/retrieval/chroma_db/)]
    K --> M[index_summary.json]
    E --> N[chroma_indexing log]
```

### Key implementation decisions carried into code

- Validate entirely in-memory **before** deleting the old collection (a
  mid-run failure must never leave zero working collections).
- `--dry-run` flag: runs every validation check, prints would-be summary,
  never touches ChromaDB.
- Explicit `hnsw:space: "cosine"` on collection creation -- ChromaDB
  defaults to L2 otherwise; for unit-normalized vectors L2 and cosine
  produce identical rankings mathematically, but leaving this implicit is a
  classic RAG bug source if normalization assumptions ever change.
  Stated explicitly, not left implicit.
- Local `PersistentClient` (embedded, file-backed) -- no separate DB server
  process, appropriate for a local thesis deployment.
- Whole pipeline safely re-runnable end to end (idempotent), consistent
  with every prior module.

### Implementation & Validation

**`prepare_train_metadata.py`** (`ml/retrieval/`): tested against synthetic
fixtures covering every filter branch (not-train, no-frontal, no-cached-
embedding) and a missing-masked-path edge case (correctly triggers a
warning). Real run: 3,851 source rows -> 2,462 filtered (1,288 dropped as
not-train, 101 dropped as no-frontal, 0 dropped for missing embeddings --
confirming Phase 2 completed cleanly).

**`build_chroma_index.py`** (`ml/retrieval/`): all 6 validation checks
individually proven, via a mocked ChromaDB client, to both pass clean data
and correctly catch their target failure (non-train leakage row, uid
mismatch between metadata and embedding cache, duplicate uids, NaN-
corrupted embeddings, wrong embedding dimension, invalid collection name).
Orchestration logic proven against the mock: uid alignment is correct even
when the embedding cache array order differs from the metadata row order
(embeddings and metadata both independently verified to land on the correct
uid); a validation failure leaves a pre-existing collection completely
untouched, confirming the "validate before delete" safety property holds in
practice, not just in the sequence diagram.

Real ChromaDB installation was not testable in the development sandbox (no
network access); the mocked-client tests above cover all logic up to the
real `chromadb.PersistentClient` API calls themselves, which were verified
on the actual workstation (see results below).

**Results (real run, RTX 4070 Ti SUPER):**
- Dry run: validation passed, 0 warnings, 0 errors, would index 2,462 records.
- Real run: deleted (no prior collection existed), created, indexed all
  2,462 records in **1.03 seconds**, post-insert `collection.count()`
  verified exact match.
- Post-hoc query test: `collection.count()` = 2,462 confirmed independently;
  sample records returned correct uids, labels, and **masked** image paths
  (not raw), confirming the Correction 2 fix (image_path must be the masked
  path) is functioning correctly in the real index.

**Class distribution indexed** (train split, matches Phase 1's known split
exactly): Normal 918, Other Abnormality 301, Degenerative/Bone 162,
Granuloma 131, Cardiomegaly 110, Support Devices 109,
Calcinosis/Atherosclerosis 100, Atelectasis 97, Scarring 91, Emphysema/COPD
77, Nodule/Mass 70, Pleural Effusion 66, Lung Opacity 61, Edema/Congestion
57, Hernia/Diaphragm 49, Pneumonia 25, Fibrosis/Interstitial 21,
Pneumothorax 17.

### How to Write This in Your Thesis

*Methodology chapter, "Retrieval Index Construction" subsection:*

> The retrieval knowledge base was constructed as a persistent ChromaDB
> collection, built exclusively from the training split's cached image
> embeddings, consistent with the leakage-prevention protocol established
> during dataset splitting. Indexing followed a two-stage pipeline enforcing
> strict separation of responsibilities: a metadata-preparation stage
> filtered the canonical study metadata to the subset of train-split studies
> with both an available frontal image and a successfully cached embedding,
> and a separate indexing stage performed exhaustive validation — checking
> for split-membership leakage, embedding/metadata identifier mismatches,
> duplicate records, missing required fields, and embedding numerical health
> (finite values, correct dimensionality, unit normalization) — entirely
> in-memory before any modification to the persistent database. This
> ordering guarantees that a validation failure never leaves the system
> without a working retrieval index. All 2,462 eligible training studies
> were successfully indexed in 1.03 seconds, with post-insertion record
> counts verified to exactly match the validated input, and a subsequent
> independent query confirmed both correct record counts and correct
> retrieval of privacy-masked (rather than raw) image paths.

---

## Phase 3 core (Retrieval Indexing) — COMPLETE

`prepare_train_metadata.py` and `build_chroma_index.py` both implemented,
tested (mocked-client unit tests + real end-to-end run), and validated on
real data. Persistent, queryable, leakage-safe ChromaDB collection
(`iu_cxr_biomedclip_v1_train`, 2,462 records) confirmed working. Remaining
Phase 3 work: the retrieval query interface (image query -> ChromaDB ->
ranked results), which the backend's future `RetrievalService` will wrap.

---

## Phase 4 — Backend Assembly: Architecture (FROZEN)

**Status: approved and frozen.** Not to be redesigned without a critical
correctness issue. Objective: expose the validated Phase 0-3 ML pipeline
through a clean backend architecture. Must NOT modify preprocessing,
embeddings, ChromaDB indexing, or evaluation -- those are complete.

### Corrections/decisions made before freezing

1. **`SimilaritySearchPolicy` is not a pass-through.** It owns real logic:
   top-K selection + a minimum-similarity threshold cutoff. Near-duplicate
   cluster deduplication (using `cluster_id`, given the known 28.2%
   template-duplication rate from Phase 1) is a documented future
   extension point, not implemented in Phase 4.
2. **`session_id` is generated at the API/DB layer, not inside
   `RetrievalService`.** The service stays session-agnostic and DB-free --
   pure orchestration, trivially unit-testable with fakes.
3. **Only `retrieval_sessions` is built in Phase 4, not the broader
   `sessions` cache table.** The latter has nothing to cache until context
   building and report generation exist; building it now means an
   unexercised table. Deferred to whichever phase introduces report
   generation.
4. **Weighted-voting formula frozen explicitly** (was underspecified since
   Fork A): for each label L among retrieved cases,
   `weight(L) = sum(similarity_i for cases carrying L)`;
   `predicted label = argmax(weight(L))`;
   `agreement = fraction of retrieved cases carrying the predicted label`.
   Maps directly onto the existing `VotedLabel` entity.
5. **PHI masking is not wired into the `/retrieve` upload path in Phase 4.**
   Stated explicitly as a scope boundary, not hidden as an oversight --
   real future work.

### Module dependency diagram

```mermaid
flowchart TD
    subgraph API["backend/app/api/"]
        R1["POST /retrieve"]
    end
    subgraph SVC["backend/app/services/"]
        RS[RetrievalService]
        LV[LabelVotingService]
        IV[ImageValidator]
        SS[SimilaritySearchPolicy]
    end
    subgraph INFRA["backend/app/infrastructure/"]
        EA[BiomedCLIPAdapter]
        VS[ChromaVectorStore]
        RM[ChromaResultMapper]
    end
    subgraph DOM["backend/app/domain/"]
        IE[IEmbedder]
        IVS[IVectorStore]
        IIV[IImageValidator - new]
        ISS[ISimilaritySearchPolicy - new]
        ILV[ILabelVoter]
        ENT[RetrievedCase, VotedLabel]
    end
    subgraph DB["backend/app/models/ + database/"]
        RSESS[(retrieval_sessions)]
    end

    R1 --> RS
    R1 --> LV
    R1 --> RSESS
    RS --> IV
    RS --> EA
    RS --> VS
    RS --> SS
    VS --> RM
    EA -.implements.-> IE
    VS -.implements.-> IVS
    IV -.implements.-> IIV
    SS -.implements.-> ISS
    LV -.implements.-> ILV
    EA --> ENT
    VS --> ENT
    RM --> ENT
```

### Retrieval Service interfaces

Two new domain Protocols added to `domain/interfaces.py`:
```
IImageValidator.validate(image_path: str) -> None       # raises ValueError on invalid input
ISimilaritySearchPolicy.select(raw_results, top_k, min_similarity) -> list[RetrievedCase]
```

`RetrievalService` -- pure orchestrator, constructor-injected:
```
__init__(validator: IImageValidator, embedder: IEmbedder,
          vector_store: IVectorStore, search_policy: ISimilaritySearchPolicy)
retrieve(image_path: str, top_k: int = 5, min_similarity: float = 0.0) -> list[RetrievedCase]
```
Sequence: validate -> embed -> `vector_store.query()` -> `search_policy.select()` -> return.
No business logic in the service itself -- if logic accumulates here, it belongs
in a collaborator instead.

### RetrievedCase entity gap (found during implementation, fixed)

The domain entity `RetrievedCase` (scaffolded before Phase 3's metadata
schema existed) was missing `image_path` and `cluster_id` -- both required
by the frozen response contract below, with `image_path` specifically
carrying forward the Phase 3 Correction-2 fix (masked, not raw, path).
Fixed by adding two fields with safe defaults (`image_path: str = ""`,
`cluster_id: int = -1`) so no existing construction site breaks.
`primary_label` was deliberately NOT added as a new field -- by convention,
it is `labels[0]` when `labels` is non-empty, keeping the entity minimal.

### Input/output contracts

**Request** (multipart upload):
```
POST /retrieve
  file: UploadFile (image)
  top_k: int = 5
  min_similarity: float = 0.0
```

**Response:**
```json
{
  "session_id": "uuid",
  "retrieval_time_ms": 124,
  "embedding_model": "biomedclip",
  "embedding_version": "v1",
  "collection_name": "iu_cxr_biomedclip_v1_train",
  "retrieved_cases": [
    {
      "rank": 1, "similarity": 0.95, "study_uid": "...",
      "primary_label": "...", "label_set": "...", "cluster_id": 42,
      "findings": "...", "impression": "...",
      "image_path": "ml/datasets/masked/...png"
    }
  ]
}
```

### Folder structure

```
backend/app/
|-- domain/            entities.py, interfaces.py (existing + Phase 4 additions)
|-- services/           image_validator.py, similarity_search.py,
|                        retrieval_service.py, label_voting_service.py
|-- infrastructure/     biomedclip_adapter.py, chroma_store.py, chroma_result_mapper.py
|-- models/             SQLAlchemy: retrieval_sessions (+ others deferred)
|-- core/config.py      Settings
|-- database/           session factory, Alembic env
|-- api/retrieval.py    POST /retrieve, GET /health
`-- main.py

backend/tests/
|-- unit/          test_retrieval_service.py, test_label_voting_service.py,
|                   test_chroma_result_mapper.py
`-- integration/    test_retrieval_integration.py (real ChromaDB + real embedder)
```

### Database model overview (Phase 4 scope)

| Table | Purpose |
|---|---|
| `retrieval_sessions` | one row per `/retrieve` call |
| `retrieved_evidence` | one row per returned case, FK to session -- audit trail |

`patients`, `studies`, `study_images`, `reports`, broader `sessions` deferred
to the phase introducing report generation.

### Testing strategy

- Unit -- `RetrievalService`: all 4 collaborators faked, assert call order + correct mapping.
- Unit -- `LabelVotingService`: pure function, hand-calculated expected output.
- Unit -- `ChromaResultMapper`: pure function, fake Chroma-shaped input.
- Integration: real `BiomedCLIPAdapter` + real ChromaDB collection + real FastAPI `TestClient`.

### Sequence diagram

```mermaid
sequenceDiagram
    participant C as Client
    participant API as POST /retrieve
    participant RS as RetrievalService
    participant IV as ImageValidator
    participant EA as BiomedCLIPAdapter
    participant VS as ChromaVectorStore
    participant SS as SimilaritySearchPolicy
    participant DB as retrieval_sessions

    C->>API: upload image, top_k, min_similarity
    API->>RS: retrieve(image_path, top_k, min_similarity)
    RS->>IV: validate(image_path)
    IV-->>RS: OK (or raises)
    RS->>EA: embed_image(image_path)
    EA-->>RS: query_vector
    RS->>VS: query(query_vector, top_k)
    VS-->>RS: raw results (mapped to RetrievedCase)
    RS->>SS: select(results, top_k, min_similarity)
    SS-->>RS: filtered ranked list
    RS-->>API: RetrievalResult
    API->>DB: persist retrieval_sessions + retrieved_evidence
    API-->>C: JSON response (with session_id)
```

### Development order (must complete each step before the next)

1. Interface definitions -> 2. Infrastructure adapters -> 3. RetrievalService
-> 4. Unit tests -> 5. Integration tests -> 6. Freeze RetrievalService ->
7. LabelVotingService -> 8. Freeze LabelVoting -> 9. Database layer ->
10. Alembic migration -> 11. FastAPI skeleton -> 12. Swagger validation.

**Status as of this entry: Step 1 (interfaces) complete and verified in the
development sandbox. `biomedclip_adapter.py` written. Steps 1 (entity fix)
through 5 (integration test) handed to Claude Code for implementation.**

---

## Phase 4 Steps 1–5 — RetrievalService — Implementation & Validation

### Folder setup

`backend/app/{domain,infrastructure,services}/` and
`backend/tests/{unit,integration}/` created with `__init__.py` package
markers. The two files developed in the sandbox — `interfaces.py` and
`biomedclip_adapter.py` — were placed at repo root for handoff and moved
into `backend/app/domain/` and `backend/app/infrastructure/` respectively;
`entities.py` was handed off as pasted content rather than a placed file
and was written directly to `backend/app/domain/entities.py` from that
content.

### Step 1 — `RetrievedCase` entity gap, fixed

Confirmed via grep that `entities.py` did not yet exist anywhere in the
repository before this step (the earlier claim that it had already been
"moved" was not reflected on disk) — written from the handed-off content,
then the gap described in the Phase 4 freeze above was fixed: two fields
added to `RetrievedCase`, both with safe defaults so no existing
construction site breaks:
```python
image_path: str = ""        # masked path (Phase 3 Correction-2), matches what was embedded
cluster_id: int = -1        # near-dup cluster diagnostic; -1 = unset
```
`primary_label` deliberately not added as a field, per the frozen decision
— recovered as `labels[0]` by convention. Verified: `RetrievedCase`
instantiates correctly both with and without the new fields, and
`domain/interfaces.py` imports cleanly against the updated entity.

### Step 2 — Infrastructure adapters

**`chroma_result_mapper.py`**: pure function, `raw_result -> list[RetrievedCase]`.
Before trusting the distance→similarity conversion, queried the real
`iu_cxr_biomedclip_v1_train` collection with an embedding taken directly
from a stored record — self-query returned `distance == 0.0` for that
record, confirming Chroma's `hnsw:space="cosine"` returns **cosine
distance**, not similarity, so the mapper uses `similarity = 1.0 -
distance`. Verified once more on a hand-built input (`distance=0.0 ->
similarity=1.0`, `distance=0.25 -> similarity=0.75`) before writing
`chroma_store.py` on top of it.

**`chroma_store.py`**: implements `IVectorStore`, wraps
`chromadb.PersistentClient` pointed at `ml/outputs/retrieval/chroma_db`,
collection name defaults to `iu_cxr_biomedclip_v1_train` (constructor
parameter, not hardcoded). `query()` verified end-to-end against the real
collection: self-query similarity was exactly `1.0`, and the top-3 results
returned real masked image paths, correct `cluster_id`, and correct
`primary_label`.

*Environment note:* `chromadb` was not previously installed (Phase 0's
`requirements.txt` had it commented out as backend-only); installed
`chromadb>=0.4` and uncommitted the requirement, since Phase 3/4 now
depend on it directly.

### Step 3 — `RetrievalService` and collaborators

`image_validator.py` (file exists, non-empty, openable via Pillow),
`similarity_search.py` (threshold filter + top-K by similarity descending,
near-dup dedup left as a documented future extension per the freeze), and
`retrieval_service.py` (pure orchestrator, no business logic) all written
per spec. Smoke-tested inline before the formal test suite: validator
correctly accepted a real masked image and correctly raised `ValueError`
on a missing file; `SimilaritySearchPolicy.select()` correctly filtered
and ranked a synthetic input; `RetrievalService.retrieve()` correctly
orchestrated fakes end to end.

### Step 4 — Unit tests (`backend/tests/unit/`)

`pytest` was not previously a dependency (no test suite existed before
Phase 4); installed and added to `requirements.txt`.

- `test_chroma_result_mapper.py` — 4 tests: distance→similarity conversion,
  metadata field mapping, result order preservation, empty-result edge case.
- `test_retrieval_service.py` — 2 tests: call order is exactly
  `[validate, embed_image, query, select]` with the final return value
  being the exact object `search_policy.select()` returned; when the
  validator raises, `embed_image`/`query`/`select` are never called
  (call log is `[validate]` only).

```
backend/tests/unit/test_chroma_result_mapper.py::test_distance_to_similarity_conversion PASSED
backend/tests/unit/test_chroma_result_mapper.py::test_field_mapping PASSED
backend/tests/unit/test_chroma_result_mapper.py::test_result_order_preserved PASSED
backend/tests/unit/test_chroma_result_mapper.py::test_empty_result PASSED
backend/tests/unit/test_retrieval_service.py::test_call_order_and_return_value PASSED
backend/tests/unit/test_retrieval_service.py::test_validator_raises_short_circuits_pipeline PASSED
6 passed in 0.02s
```

### Step 5 — Integration test (`backend/tests/integration/`)

`test_retrieval_integration.py` uses the **real** `BiomedCLIPAdapter` (real
BiomedCLIP model, GPU-loaded) and **real** `ChromaVectorStore` against the
actual `iu_cxr_biomedclip_v1_train` collection on disk, querying with a
real image from `ml/datasets/masked/`. Four assertions, all real
end-to-end behavior, not mocks:

```
backend/tests/integration/test_retrieval_integration.py::test_retrieval_returns_nonempty_results PASSED
backend/tests/integration/test_retrieval_integration.py::test_retrieved_image_paths_exist PASSED
backend/tests/integration/test_retrieval_integration.py::test_similarities_descending PASSED
backend/tests/integration/test_retrieval_integration.py::test_top1_similarity_reasonably_high PASSED
4 passed in 9.46s
```

Full suite (unit + integration) together: **10 passed in 9.00s**.

### How to Write This in Your Thesis

*Methodology chapter, "Retrieval Service Implementation" subsection:*

> The retrieval query path was implemented as a constructor-injected
> orchestration service (`RetrievalService`) depending only on
> Protocol-typed interfaces for image validation, embedding, vector search,
> and result selection — never on concrete infrastructure classes — so that
> each stage is independently substitutable and unit-testable in isolation.
> A domain-entity gap was identified during implementation: the
> `RetrievedCase` entity, scaffolded prior to the retrieval index's
> metadata schema, lacked the masked image path and near-duplicate cluster
> identifier required by the response contract; this was resolved by
> extending the entity with two backward-compatible optional fields rather
> than introducing a parallel representation. The distance-to-similarity
> conversion for the cosine-space ChromaDB collection was empirically
> verified against the real index before being relied upon elsewhere,
> confirming that Chroma reports cosine distance rather than similarity.
> The service was validated at two levels: a unit-test suite exercising
> call ordering and error short-circuiting against fake collaborators, and
> an integration test exercising the complete real pipeline — real encoder,
> real vector store — confirming non-empty, correctly ordered, and
> file-verified results against the production retrieval index.

---

## Phase 4 Steps 1–5 (RetrievalService) — COMPLETE

`RetrievedCase` gap fixed, `ChromaResultMapper`/`ChromaVectorStore`/
`ImageValidator`/`SimilaritySearchPolicy`/`RetrievalService` all
implemented and verified — 6 unit tests (fakes) + 4 integration tests
(real BiomedCLIP + real ChromaDB) passing, 10/10. Per the frozen
development order, Step 6 (freeze `RetrievalService`) is a decision for
the thesis author, not implied by tests passing; `LabelVotingService`
(Step 7) intentionally not started pending that confirmation.

**Step 6: confirmed frozen.** `chroma_store.py`'s CWD-relative default
path was fixed (anchored via `Path(__file__)`, no longer dependent on the
process's working directory); the separate `shared/` import CWD issue
(only reproduces when pytest is invoked from `backend/`, not repo root) is
deliberately deferred to Steps 9–11, where the real FastAPI entrypoint and
its import resolution get decided — `backend/tests/conftest.py` added
(test-scope only) so the test suite itself is CWD-independent in the
meantime.

---

## Phase 4 Step 7 — LabelVotingService — Implementation & Validation

### Design note: resolving plural `VotedLabel` against the frozen formula

The frozen weighted-voting formula (Phase 4 architecture section,
correction 4) defines a single predicted label — `weight(L) = sum(similarity_i
for cases carrying L)`, `predicted label = argmax(weight(L))`, `agreement =
fraction of retrieved cases carrying the predicted label` — but
`ILabelVoter.vote()` returns `list[VotedLabel]`, and `ClinicalContext`
already declared `voted_labels: tuple[VotedLabel, ...]` as plural before
this step. Rather than silently picking an interpretation, this was
flagged before implementation: `LabelVotingService` computes `weight(L)`
and `agreement(L)` for **every** label present across the retrieved cases
— `agreement(L) = fraction of retrieved cases carrying L`, generalizing
the frozen single-label definition — and returns the list sorted
descending by `vote_weight`, so the first element is exactly the frozen
argmax + agreement case. Confirmed as the correct, and only interpretation
consistent with the existing plural `ClinicalContext` field.

### Implementation & Validation

`label_voting_service.py`: pure function over `list[RetrievedCase]`, no
I/O. A case contributes its full similarity weight to every label it
carries (relevant once multi-label `RetrievedCase.labels` tuples are
populated beyond the current single-label convention — see the Step 2 TODO
in `chroma_result_mapper.py`). Two hand-calculated test cases, plus an
empty-input edge case:

```
backend/tests/unit/test_label_voting_service.py::test_single_label_weighted_vote_hand_calculated PASSED
  # 3 cases: similarity 0.9->Normal, 0.6->Cardiomegaly, 0.5->Normal
  # weight(Normal)=1.4, weight(Cardiomegaly)=0.6
  # agreement(Normal)=2/3, agreement(Cardiomegaly)=1/3
backend/tests/unit/test_label_voting_service.py::test_multi_label_case_contributes_to_every_label_it_carries PASSED
  # case carrying (Pneumonia, Effusion) with similarity 0.8 contributes to both;
  # second case similarity 0.4->Pneumonia only
  # weight(Pneumonia)=1.2, weight(Effusion)=0.8
  # agreement(Pneumonia)=2/2=1.0, agreement(Effusion)=1/2=0.5
backend/tests/unit/test_label_voting_service.py::test_empty_retrieved_list_returns_empty_vote PASSED
3 passed in 0.02s
```

Full suite (Steps 1–7 combined, unit + integration): **13 passed in 9.09s**.

### How to Write This in Your Thesis

*Methodology chapter, "Similarity-Weighted Label Voting" subsection:*

> Predicted findings were derived from the retrieved case set via a
> similarity-weighted vote: for each label present among the retrieved
> neighbors, a vote weight was computed as the sum of the cosine
> similarities of all neighbors carrying that label, and an agreement
> score was computed as the fraction of retrieved neighbors carrying it —
> a direct confidence signal independent of the vote weight's magnitude.
> The label with the highest vote weight constitutes the primary
> prediction, with agreement expressing what fraction of retrieved
> evidence supports it; the full ranked set of labels is retained (rather
> than only the top prediction) so that downstream context construction
> can draw on secondary findings when relevant. The formula was validated
> against hand-calculated expected values for both single-label and
> multi-label retrieved cases prior to being trusted in the pipeline.

---

## Phase 4 Steps 1–8 (RetrievalService + LabelVotingService) — COMPLETE

All of Phase 4's retrieval and voting logic is implemented, tested, and
frozen: `RetrievedCase` entity gap fixed (Step 1); `ChromaResultMapper` and
`ChromaVectorStore` built and verified against the real
`iu_cxr_biomedclip_v1_train` collection, including a since-fixed
CWD-relative default path (Step 2); `ImageValidator`, `SimilaritySearchPolicy`,
and the pure-orchestrator `RetrievalService` (Step 3); `LabelVotingService`
implementing the frozen weighted-voting formula, generalized to a ranked
`list[VotedLabel]` (Step 7). 13/13 tests passing — 9 unit (fakes/hand-
calculated), 4 integration (real BiomedCLIP + real ChromaDB). Both
`RetrievalService` and its collaborators (Step 6) and `LabelVotingService`
(Step 8) are confirmed frozen. The `shared/` import CWD fragility remains
a deliberately deferred open item, to be resolved when the real FastAPI
entrypoint is built (Steps 9–11) rather than patched ahead of that
decision. Next: Step 9, Database Layer.

---

## Phase 4 Step 9 — Database Layer — Implementation & Validation

Scoped to exactly the two tables the frozen architecture's "Database model
overview" specifies -- `retrieval_sessions` and `retrieved_evidence` --
not the deferred `patients`/`studies`/`study_images`/`reports`/broader
`sessions` cache.

**Built**: `backend/app/core/config.py` (`Settings`, pydantic-settings,
`.env`-backed); `backend/app/database/base.py` (SQLAlchemy 2.0
`DeclarativeBase`, engine, `sessionmaker`); `backend/app/models/
retrieval_session.py` and `retrieved_evidence.py` (typed `Mapped[]`/
`mapped_column()` ORM models, `sqlalchemy.Uuid` for the dialect-agnostic
primary/foreign keys, bidirectional `relationship()`). SQLAlchemy was not
previously a dependency anywhere in the repo -- flagged and confirmed
before adding `sqlalchemy>=2.0` rather than assumed.

**Verification highlight 1 -- config parity is asserted, not eyeballed.**
`CHROMA_PERSIST_PATH` and `CHROMA_COLLECTION_NAME` must default to
exactly what `chroma_store.py` already hardcodes, so nothing changes
behavior once Step 11 wires `Settings` in. Rather than visually comparing
the two files, a runtime assertion imported both defaults and compared
them directly:
```
Settings.CHROMA_PERSIST_PATH: C:\...\archive\ml\outputs\retrieval\chroma_db
CHROMA_PERSIST_PATH matches chroma_store.py DEFAULT_PERSIST_PATH exactly: CONFIRMED
```

**Verification highlight 2 -- the FK constraint test is proven meaningful
via a negative control.** SQLite does not enforce `FOREIGN KEY`
constraints by default, per connection -- so `database/base.py` installs a
`PRAGMA foreign_keys=ON` connect-listener. Before trusting the constraint
test, a second, bare SQLite engine was built *without* that listener and
the same orphaned insert was attempted against it: the commit succeeded
silently (`row count: 1`, no error), confirming the pragma is genuinely
load-bearing rather than the constraint check passing for an unrelated
reason.

**Real test output** (`backend/tests/integration/test_database_layer.py`,
real SQLite file at `backend/dev.db`, tables dropped at teardown so
repeated runs don't accumulate rows):
```
test_insert_and_query_relationship_both_directions PASSED
test_foreign_key_constraint_rejects_unknown_session_id PASSED
2 passed in 0.26s
```
Full suite (Steps 1–9 combined, unit + integration): **15 passed in 9.37s**.

Not wired into `RetrievalService` or any frozen code yet -- models exist
and are verified in isolation only, per the frozen development order
(wiring happens at Step 11, the FastAPI skeleton).

### How to Write This in Your Thesis

*Methodology chapter, "Session Persistence Layer" subsection:*

> A minimal relational persistence layer was introduced to record an audit
> trail of retrieval activity, scoped deliberately to the two tables
> required at this stage -- one row per retrieval request and one row per
> piece of returned evidence, linked by foreign key -- rather than
> anticipating schema needs for functionality (patient records, report
> storage) not yet built. The object-relational models were implemented
> using SQLAlchemy's typed declarative style, with a dialect-agnostic
> identifier type chosen so that the eventual migration from a local
> SQLite development database to a production Postgres instance requires
> no schema changes. Two properties were verified empirically rather than
> assumed: that the vector-store connection configuration newly centralized
> in an application settings object was byte-for-byte identical to the
> configuration it was intended to replace, confirmed via a direct runtime
> comparison; and that referential integrity between the two tables was
> genuinely enforced, confirmed via a negative control in which the same
> constraint-violating insert was repeated against a database connection
> deliberately configured without the enforcement mechanism, and shown to
> succeed silently -- demonstrating that the positive test result on the
> real configuration was not coincidental.

---

## Phase 4 Steps 1–9 (RetrievalService + LabelVotingService + Database Layer) — COMPLETE

Retrieval, voting, and persistence foundations are all implemented, tested,
and (through Step 8) frozen: `RetrievedCase` entity gap fixed (Step 1);
`ChromaResultMapper`/`ChromaVectorStore` verified against the real
`iu_cxr_biomedclip_v1_train` collection (Step 2); `ImageValidator`,
`SimilaritySearchPolicy`, `RetrievalService` (Step 3, frozen Step 6);
`LabelVotingService` implementing the frozen weighted-voting formula,
generalized to a ranked `list[VotedLabel]` (Step 7, frozen Step 8);
`Settings`, SQLAlchemy `Base`/engine/session factory, and the
`retrieval_sessions`/`retrieved_evidence` ORM models, verified in
isolation with a real SQLite database (Step 9). 15/15 tests passing — 9
unit (fakes/hand-calculated), 6 integration (real BiomedCLIP + real
ChromaDB + real SQLite). Deferred, open items carried forward unchanged:
the `shared/` import CWD fragility, and Step 9's models are not yet wired
into `RetrievalService` or any frozen code -- both intentionally left for
the Steps 10-11 entrypoint work. Next: Step 10, Alembic migrations.

---

## Phase 4 Step 10 — Alembic Migrations — Implementation & Validation

Step 10 also resolved the `shared/` import CWD fragility deferred at Steps
6/8, rather than patching it a second time -- Alembic's `env.py` needed a
real import strategy regardless, making this the natural point to settle
it.

### Package-separation decision

Two options were on the table: (a) `shared/` becomes its own tiny
installable package, with `backend/` depending on it as a sibling editable
install; or (b) `backend/pyproject.toml`'s package discovery reaches across
to the repo-root `shared/` directory via a `package_dir` mapping outside
its own project tree. Option (a) was chosen. Reasoning: a `package_dir`
entry pointing at a sibling directory (`{"shared": "../shared"}`) works,
but is a less standard, more surprising monorepo pattern than each
subproject owning its own minimal `pyproject.toml` -- fewer ways for a
future setuptools version to change this behavior silently. The one trap
avoided in `shared/pyproject.toml`: plain flat-layout auto-discovery would
have made the installed top-level package `embeddings` rather than
`shared.embeddings`, silently breaking every existing `from
shared.embeddings...` import, including `ml/`'s own `sys.path.insert(0,
str(data_root))` pattern. Fixed with an explicit self-referential
`package-dir = {"shared" = "."}` remap -- zero files moved, `ml/`'s
existing imports untouched. This preserves `shared/`'s status as the
deliberate, one-off `ml/`-`backend/` boundary exception (see the Phase 0
architecture notes) rather than folding it into `backend/`'s own package.

### Verification 1 -- editable installs work from a location outside the repo entirely

Before trusting the fix, both packages were imported from `/tmp` -- not
just a different directory inside the repo, but outside it altogether,
with zero `sys.path` manipulation:
```
shared.embeddings import OK from /tmp (no repo dir in cwd at all)
app.domain import OK from /tmp
```
`backend/tests/conftest.py` (the Step 8 sys.path shim) was then deleted as
genuinely redundant, not just simplified.

### Verification 2 -- three-CWD test suite run (real proof the issue is gone, not moved)

```
repo root:        15 passed in 9.68s
backend/:         15 passed in 9.37s
backend/tests/:    15 passed in 9.45s
```
Identical pass count from all three; the fix generalizes rather than
happening to work from one launch directory.

### Alembic setup

`backend/alembic/` + `backend/alembic.ini` initialized. `env.py` imports
`app.models` (registers `RetrievalSession`/`RetrievedEvidence` on `Base`'s
mapper registry for autogenerate), sets `target_metadata = Base.metadata`,
and pulls `sqlalchemy.url` from `Settings.DATABASE_URL` at runtime --
`alembic.ini`'s own `sqlalchemy.url` is left blank with a comment
explaining why, so the connection string is defined in exactly one place.

**Migration file read in full before running anything** (per the
project's standing rule): confirmed both tables, all columns with the
types Step 9 specified, the `retrieved_evidence.session_id` foreign key
constraint, the index, and a `downgrade()` that reverses everything in
correct dependency order (index and child table dropped before the
parent):
```python
op.create_table('retrieval_sessions', id: Uuid PK, query_image_path, top_k,
                 min_similarity, num_results, retrieval_time_ms,
                 created_at DEFAULT CURRENT_TIMESTAMP)
op.create_table('retrieved_evidence', id: Uuid PK,
                 session_id: Uuid FK->retrieval_sessions.id,
                 study_uid, rank, similarity)
op.create_index('ix_retrieved_evidence_session_id', 'retrieved_evidence', ['session_id'])
```

### Fresh-database verification

`alembic upgrade head` run against `backend/alembic_verify.db` -- a file
never touched by Step 9's manual `create_all` script, to prove the
migration itself creates the schema correctly, independent of the earlier
manual verification (deleted afterward as a throwaway artifact). Real
`sqlite3`/`PRAGMA` inspection of the resulting schema:
```
Tables: [('alembic_version',), ('retrieval_sessions',), ('retrieved_evidence',)]
FOREIGN KEY(session_id) REFERENCES retrieval_sessions (id)
ix_retrieved_evidence_session_id  CREATE INDEX ... ON retrieved_evidence (session_id)
```

### Downgrade/upgrade reversibility

```
downgrade base -> Tables: [('alembic_version',)]                                   # both dropped
upgrade head   -> Tables: [alembic_version, retrieval_sessions, retrieved_evidence] # restored
                  FK still intact: [(0, 0, 'retrieval_sessions', 'session_id', 'id', ...)]
```
Confirms the migration is genuinely reversible and re-runnable, not
one-directional.

Full suite after this step: **15 passed** (unchanged from Step 9 -- this
step touched packaging and migrations, not application logic).

### How to Write This in Your Thesis

*Methodology chapter, "Schema Migration and Package Structure" subsection:*

> Database schema evolution was managed through Alembic, configured to
> derive both its target schema and its connection string from the
> application's own object-relational models and settings object rather
> than maintaining a second, independently-hardcoded copy of either --
> eliminating a class of drift where a migration could silently diverge
> from the models it was meant to describe. Prior to execution, the
> autogenerated migration was manually inspected against the intended
> schema rather than trusted uncritically, and its correctness was verified
> empirically in two ways: by applying it to a database file with no prior
> history and directly inspecting the resulting schema and foreign-key
> constraints, and by exercising a full downgrade-then-upgrade cycle to
> confirm the migration was reversible rather than one-directional. This
> step also resolved a previously-deferred packaging inconsistency: the
> project's shared model-embedding component, which by design is imported
> by both the offline research pipeline and the backend service to
> guarantee they occupy an identical vector space, was packaged as an
> independently installable component depended upon by the backend, rather
> than being absorbed into the backend's own package -- preserving its
> role as a deliberate, singular exception to the boundary between the
> research and backend codebases, and eliminating a working-directory
> dependency that had previously required a test-only path-manipulation
> workaround.

---

## Phase 4 Steps 1–10 (RetrievalService + LabelVotingService + Database Layer + Migrations) — COMPLETE

Retrieval, voting, persistence, and schema migration are all implemented,
tested, and (through Step 8) frozen. Steps 1-9 unchanged from the prior
banner. Step 10 adds: `shared/` and `backend/` both editable-installed as
independent local packages (`shared/pyproject.toml`, `backend/pyproject.toml`),
resolving the Step 6/8-deferred `shared/` import CWD fragility -- proven via
imports from outside the repo entirely and an identical-result three-CWD
test run, not assumed fixed; `backend/tests/conftest.py` deleted as
redundant; Alembic initialized and configured to read schema and connection
string from the application's own models/settings (no duplicated
connection string); the initial migration manually reviewed before
execution, applied to a genuinely fresh database with the resulting schema
independently inspected, and proven reversible via a downgrade/upgrade
cycle. 15/15 tests passing throughout -- this step touched packaging and
migration tooling, not application logic. Next: Step 11, FastAPI skeleton.

---

## Phase 4 Step 11 — FastAPI Skeleton — Implementation & Validation

The first true end-to-end slice of the backend: a real HTTP request now
flows through validation, embedding, vector search, label voting, and
persistence, and back out as a response.

### Contract extension (flagged and approved before implementation)

The frozen response contract (Phase 4 architecture section) predates
`LabelVotingService` (Step 7) and had no field for its output. Approved
extension: a `voted_labels` array (`label`, `vote_weight`, `agreement`,
mirroring `VotedLabel` exactly), populated by calling
`LabelVotingService.vote(retrieved_cases)` after retrieval, before the
response is built. Nothing else in the frozen contract changed.

### Two contract-field gaps, sourced without touching frozen code

- **`embedding_model`/`embedding_version`**: not available anywhere as
  named values (only embedded as substrings inside `collection_name`, e.g.
  `"biomedclip"`/`"v1"` inside `"iu_cxr_biomedclip_v1_train"`, confirmed
  against the literal arguments `build_collection_name("iu_cxr",
  "biomedclip", "v1", "train")` in `ml/retrieval/build_chroma_index.py`).
  Added `CHROMA_EMBEDDING_MODEL`/`CHROMA_EMBEDDING_VERSION` to `Settings`
  (not one of the five frozen classes) with a runtime assertion that
  reconstructing the collection name from them exactly matches
  `CHROMA_COLLECTION_NAME`, the same parity-proof pattern used for
  `CHROMA_PERSIST_PATH` at Step 9:
  ```
  reconstructed: iu_cxr_biomedclip_v1_train
  actual CHROMA_COLLECTION_NAME: iu_cxr_biomedclip_v1_train
  PARITY CONFIRMED
  ```
- **`label_set`**: `RetrievedCase` has no field for it at all --
  `chroma_result_mapper.py`'s multi-label parsing was explicitly deferred
  as a TODO at Step 2, so only a single-label `labels` tuple is available.
  The response serializes `label_set` as `";".join(case.labels)`, which is
  currently degenerate (identical to `primary_label`) until that Step 2
  TODO is addressed. Flagged rather than silently presented as full
  multi-label data -- not a Step 11 regression, an inherited gap.

### Build

`backend/app/main.py`: `lifespan` context manager constructs
`BiomedCLIPAdapter` (loads the model), `ChromaVectorStore`,
`ImageValidator`, `SimilaritySearchPolicy` exactly once at startup, wires
them into `RetrievalService`, and stores both `RetrievalService` and a
`LabelVotingService` on `app.state`. `backend/app/api/retrieval.py`:
`GET /health` (liveness only), `POST /retrieve` (multipart upload -> temp
file -> `RetrievalService.retrieve()` -> `LabelVotingService.vote()` ->
single-transaction DB persistence -> response). `RetrievalService`,
`LabelVotingService`, `ChromaVectorStore`, `ImageValidator`,
`SimilaritySearchPolicy` were not modified.

### Thin-route audit (every line of `POST /retrieve`, as requested)

| Lines | Content | Category |
|---|---|---|
| 113-118 | Parameter signature (`file`, `top_k`, `min_similarity`, `db`) | Validate (FastAPI's own typing) |
| 123-124 | `request.app.state.retrieval_service` / `.label_voting_service` | Does not cleanly fit -- DI attribute access, zero logic |
| 126 | `with _saved_upload(file) as temp_path:` | Does not cleanly fit -- request I/O plumbing, factored into a helper, flagged rather than inlined |
| 127, 133 | `start = time.perf_counter()` / elapsed-time arithmetic | Does not cleanly fit -- timing instrumentation, no reasoning about data |
| 129-131 | `retrieval_service.retrieve(...)` + `except ValueError -> HTTPException(422)` | Call service (the 422 translation is explicitly spec'd behavior, not inferred logic) |
| 132 | `label_voting_service.vote(retrieved_cases)` | Call service |
| 135 | `session_id = uuid.uuid4()` | Call service / persistence-prep (explicitly the one place session_id is created, per the frozen rule) |
| 136-153 | Construct `RetrievalSession`/`RetrievedEvidence` rows, `db.add()`/`db.add_all()` | Call service, in the broad sense -- the frozen sequence diagram shows the API layer talking directly to the DB (no repository abstraction specified for Phase 4); the `enumerate(..., start=1)` rank derivation is positional bookkeeping, not reasoning about label/similarity values |
| 154-158 | `db.commit()` / `except Exception: db.rollback(); raise` | Call service (explicitly spec'd: commit once, rollback and re-raise on failure) |
| 160 | `return _build_response(...)` | Serialize response |

No line examines or branches on label values, recomputes similarity, or
retries anything -- the class of violation the three-way split is meant to
catch is genuinely absent. The lines that don't cleanly fit the three
named categories are structural glue (DI lookup, timing, temp-file I/O),
not business/medical logic, and are called out explicitly rather than
asserted compliant by default.

### Validation -- all real execution, real BiomedCLIP model, real ChromaDB collection

```
test_health_returns_ok                                            PASSED
test_retrieve_with_real_image_returns_full_contract                PASSED
test_db_rows_match_successful_response                             PASSED
test_retrieve_with_corrupt_file_returns_422_and_no_db_rows          PASSED
test_model_loaded_once_requests_much_faster_than_startup            PASSED
test_transaction_atomicity_on_persistence_failure                  PASSED
6 passed in 9.80s
```

**Model-reload proof** (timing-based): lifespan startup (real model load)
took 8.397s; both subsequent `/retrieve` requests took ~0.1s each --
roughly 1% of load time, not a comparable duration, confirming the model
is loaded exactly once and reused.
```
[model-reload check] lifespan startup (model load): 8.397s, request 1: 0.094s, request 2: 0.097s
```

**Atomicity proof**: not a trivial short-circuit. `Session.commit` was
monkeypatched to call the real `flush()` (genuinely sending the pending
INSERT statements within the still-open transaction) before raising --
simulating a failure between "rows sent to the DB" and "transaction
finalized" (e.g. a late constraint violation or dropped connection),
which is strictly harder to roll back cleanly than a failure before any
SQL executes. Row counts across both tables were identical before and
after the simulated failure.

Full suite (Steps 1-11 combined): **21 passed** (15 prior + 6 new) from
repo root.

### How to Write This in Your Thesis

*Methodology chapter, "API Layer and End-to-End Validation" subsection:*

> The retrieval pipeline was exposed through a single HTTP endpoint
> designed to contain no domain logic of its own: the route function's
> only responsibilities are framework-level request validation, delegating
> to the already-validated service layer, and serializing already-computed
> results, with expensive resources -- most importantly the vision-language
> encoder -- constructed exactly once at application startup rather than
> per request. This separation was verified rather than assumed by two
> targeted tests: a timing comparison showing that individual requests
> complete in roughly one-hundredth the time taken to load the encoder at
> startup, demonstrating the model is not reconstructed per request; and a
> simulated mid-transaction persistence failure, in which the pending
> database writes were deliberately flushed to the database connection
> before the failure was injected -- a strictly stronger test than failing
> before any write occurs -- confirming that a session record and its
> associated evidence records are committed as a single atomic unit with
> no partial state possible. A minor extension to the previously frozen
> response contract was identified and approved prior to implementation:
> the similarity-weighted label vote, computed after retrieval and before
> response construction, was added as an additional field rather than
> retrofitted into the retrieved-case representation, keeping per-case
> evidence and aggregate label predictions as clearly separate concerns in
> the API surface.

---

## Phase 4 Steps 1–11 (RetrievalService + LabelVotingService + Database Layer + Migrations + FastAPI Skeleton) — COMPLETE

The first true end-to-end backend slice is live: `POST /retrieve` accepts a
real image upload and returns validated, persisted, evidence-backed
predictions. Steps 1-10 unchanged from the prior banner. Step 11 adds:
`backend/app/main.py` (lifespan-managed singletons -- the BiomedCLIP model
loads exactly once, not per request) and `backend/app/api/retrieval.py`
(`GET /health`, `POST /retrieve`), built entirely on top of the frozen
Steps 1-8 services without modifying any of them. A `voted_labels` field
was added to the frozen response contract (flagged and approved before
implementation) to surface `LabelVotingService`'s output, which the
original contract predated. Two contract-field gaps (`embedding_model`/
`embedding_version`, `label_set`) were sourced without touching frozen
code -- the former added to `Settings` with a verified parity assertion,
the latter flagged as a currently-degenerate value inherited from a
still-open Step 2 TODO, not a new regression. The route function was
audited line-by-line against a strict validate/call-service/serialize
split; no line contains data-dependent branching, similarity
recomputation, or retry logic. 21/21 tests passing (15 prior + 6 new),
including a timing-based proof the model loads once and a transaction-
atomicity proof strong enough to survive a failure injected after rows
are flushed to the database but before the transaction commits. Next:
Step 12, Swagger validation (the final step of the frozen Phase 4
development order).

---

## Phase 4 Step 12 — Swagger Validation — Implementation & Validation

The final step of the frozen Phase 4 development order. Checked, rather
than assumed, that the auto-generated OpenAPI schema actually matches the
real contract -- not just that `/docs` returns 200.

### Initial finding: request side accurate, response side under-specified

`GET /docs` (200, `text/html`) and `GET /openapi.json` (200, valid schema)
both worked immediately, and both endpoints appeared. The request side of
`POST /retrieve` was already fully accurate against the frozen contract --
`file` (required, binary), `top_k` (integer, default 5), `min_similarity`
(number, default 0.0) -- and `422` correctly referenced the standard
`HTTPValidationError` schema. But both routes returned a bare `-> dict`
rather than a typed Pydantic model, so FastAPI could not introspect field
names or types for the response: the generated schema for both `/health`
and `/retrieve` was simply `{"additionalProperties": true, "type":
"object"}` -- not incorrect, but undocumented. Anyone reading `/docs` to
understand what `/retrieve` actually returns would see nothing useful.
Flagged rather than treated as passing, since "matches the actual
contract" was the explicit bar for this step.

### Fix: typed response models

Added `backend/app/api/schemas.py` -- `HealthResponse`,
`RetrievedCaseResponse`, `VotedLabelResponse`, `RetrieveResponse` --
Pydantic DTOs living at the API boundary, deliberately kept out of
`app/domain/entities.py` (which stays framework-free by design; see that
file's own docstring). `_build_response()` in `retrieval.py` now
constructs a `RetrieveResponse` directly instead of a dict literal, and
both routes declare `response_model=`. This is a genuine code change, not
just a verification step -- confirmed with the user before making it,
since Step 12 was originally scoped as "just open `/docs` and confirm."

### Verification

Post-fix, the OpenAPI schema documents every field of both response
types, field-for-field against the frozen contract:
```
RetrieveResponse required: session_id, retrieval_time_ms, embedding_model,
  embedding_version, collection_name, retrieved_cases, voted_labels
RetrievedCaseResponse required: rank, similarity, study_uid, primary_label,
  label_set, cluster_id, findings, impression, image_path
```
`/docs` and `/openapi.json` re-verified working (200 for both, `paths:
['/health', '/retrieve']`) after the change. Full suite re-run: **21
passed** -- the response-model change did not alter any response content,
only its declared schema, so no test assertions needed to change.

### How to Write This in Your Thesis

*Methodology chapter, "API Documentation Validation" subsection:*

> The automatically generated OpenAPI schema was checked against the
> intended API contract rather than assumed correct from a successful
> build. This check surfaced a real gap: because the route handlers
> initially returned untyped dictionaries, the generated schema documented
> the request shape precisely but described every response as an
> unconstrained object, providing no field-level documentation despite the
> contract being well-defined internally. The fix -- introducing explicit
> response schema classes at the API boundary, kept separate from the
> underlying domain model to preserve the latter's independence from any
> web framework -- brought the generated documentation into exact
> agreement with the contract, with no change to the runtime behavior or
> content of any response. This illustrates a general point relevant to
> reproducibility: an API "working" in the sense of returning correct data
> is a distinct property from that API being correctly self-documenting,
> and the latter was not guaranteed by the former in this framework's
> default configuration.

---

## Phase 4 — Backend Assembly — COMPLETE (all 12 steps)

Every step of the frozen development order (interface definitions ->
infrastructure adapters -> RetrievalService -> unit tests -> integration
tests -> freeze RetrievalService -> LabelVotingService -> freeze
LabelVoting -> database layer -> Alembic migration -> FastAPI skeleton ->
Swagger validation) is implemented, tested with real execution at every
step, and frozen where the process called for freezing. The validated
Phase 0-3 ML pipeline is now reachable through a working HTTP API:
`POST /retrieve` accepts a real image, runs it through the frozen
BiomedCLIP-backed retrieval and similarity-weighted voting pipeline,
persists a full audit trail atomically, and returns a response whose
generated OpenAPI documentation was checked -- and, where it fell short,
fixed -- to match the contract exactly. Two real gaps surfaced and
resolved along the way rather than papered over: the Step 6/8-deferred
`shared/` import CWD fragility (Step 10, editable local packages) and the
under-specified response schema (Step 12, typed Pydantic response
models). One inherited gap remains open and documented rather than
silently masked: `label_set` is degenerate pending `chroma_result_mapper.py`'s
still-open Step 2 multi-label TODO. Full test suite: 21/21 passing.
Not yet built (explicitly out of Phase 4 scope per the frozen
architecture): `patients`/`studies`/`reports`/the broader `sessions`
cache table, PHI masking on the upload path, and report generation --
all deferred to whichever future phase introduces them.

---
## Phase 5 — Context Builder: Architecture (FROZEN)

**Status: approved and frozen.** Not to be redesigned without a critical
correctness issue. Scope narrowed from an earlier broader Phase 5 draft
(which had bundled Questionnaire, PromptBuilder, LLM, Explainability, and
Report Generation together) to Context Builder alone -- each future stage
is now its own independently-freezable phase, a better decomposition than
the original draft.

### Objective

Bridge Retrieval and the future LLM stage: transform raw
`RetrievalService` + `LabelVotingService` output into one deterministic,
structured `ClinicalContext`. Organizes and partitions evidence only --
no diagnosis, no report generation, no LLM calls, no prompt construction,
no textual summarization of any kind.

### Gaps identified and resolved before freezing

1. **Interface/pipeline-order conflict**: the pre-existing
   `IContextBuilder.build()` signature required `questionnaire_answers`
   and `clinical_notes` as mandatory parameters, but the revised pipeline
   places Clinical Questionnaire (a later phase) AFTER Context Builder --
   making it impossible to supply data that doesn't exist yet at this
   point. Fixed by making both parameters optional with empty defaults.
   A future phase will re-hydrate the context once questionnaire data
   exists; the exact mechanism is deliberately not decided here.
2. **`ClinicalContext` had no fields for organized evidence.** Fixed via
   one additive field, `evidence_summary: EvidenceSummary | None = None`,
   composed from new entities rather than flattening new fields directly
   onto `ClinicalContext` (keeps single-responsibility at the entity level).
3. **No second confidence metric introduced.** `VotedLabel.agreement`
   (frozen since Fork A) remains the only confidence signal in the system;
   Context Builder organizes and exposes it, never recomputes it.
4. **No textual summarization inside Context Builder.** An earlier draft
   proposed `representative_findings`/`representative_impression` single
   strings -- rejected as this would require synthesis, which needs an
   LLM and is explicitly out of scope here. Replaced with
   `findings_evidence`/`impressions_evidence`: structured tuples of raw,
   deduplicated per-case text, deterministically ordered. Prompt Builder
   (a future phase) performs any synthesis, not Context Builder.
5. **No new API endpoint or persistence in Phase 5** -- Context Builder is
   an internal, session-agnostic, in-memory service (mirrors
   `RetrievalService`'s frozen session-agnostic design from Phase 4),
   invoked by a future orchestrator, not directly client-facing.

### Two refinements added after initial freeze review

1. **`RetrievalMetadata` for auditability/reproducibility.** Context
   Builder's `build()` had no channel to receive retrieval-time metadata
   (`collection_name`, `embedding_model`, `embedding_version`) even though
   this data already exists in Phase 4's `/retrieve` response contract --
   it was simply never threaded one layer further. Fixed with one more
   additive optional parameter carrying a new `RetrievalMetadata` value
   object, stored on `EvidenceSummary`.
2. **Generalized, non-hardcoded label partitioning for future Differential
   Diagnosis.** Rather than fields hardcoded to "the top label" only, the
   internal partitioning logic is a single generic helper parameterized by
   *label* (not hardcoded), producing a `LabelEvidencePartition` per label
   called. Phase 5's implementation calls it once, for the top voted
   label, yielding a 1-element `label_evidence` tuple. A future
   Differential Diagnosis phase can call the identical helper in a loop
   over multiple labels -- zero type changes, zero redesign, only a
   different call site. Convention: `label_evidence[0]` is always the top
   voted label's partition, mirroring the existing `labels[0] ==
   primary_label` convention from Phase 4's maintenance fix.

### Domain Entities (final)

```python
@dataclass(frozen=True)
class RetrievalStats:
    num_cases: int
    num_cases_after_dedup: int
    num_near_duplicates_collapsed: int
    mean_similarity: float
    min_similarity: float
    max_similarity: float
    num_unique_labels: int
    num_clusters_represented: int

@dataclass(frozen=True)
class RetrievalMetadata:
    collection_name: str
    embedding_model: str
    embedding_version: str
    retrieved_at: str   # ISO 8601, caller-supplied

@dataclass(frozen=True)
class LabelEvidencePartition:
    label: str
    vote_weight: float
    agreement: float
    supporting_cases: tuple[RetrievedCase, ...]
    contradictory_cases: tuple[RetrievedCase, ...]

@dataclass(frozen=True)
class EvidenceSummary:
    top_retrieved_case: RetrievedCase | None
    findings_evidence: tuple[str, ...]
    impressions_evidence: tuple[str, ...]
    retrieval_stats: RetrievalStats
    retrieval_metadata: RetrievalMetadata | None
    label_evidence: tuple[LabelEvidencePartition, ...]

# ClinicalContext (existing, frozen) -- one additive field:
@dataclass(frozen=True)
class ClinicalContext:
    retrieved_cases: tuple[RetrievedCase, ...]
    voted_labels: tuple[VotedLabel, ...]
    questionnaire_answers: dict[str, str] = field(default_factory=dict)
    clinical_notes: str = ""
    evidence_summary: EvidenceSummary | None = None
```

### Interface (final)

```python
class IContextBuilder(Protocol):
    def build(
        self,
        retrieved: list[RetrievedCase],
        voted_labels: list[VotedLabel],
        questionnaire_answers: dict[str, str] = ...,
        clinical_notes: str = ...,
        retrieval_metadata: RetrievalMetadata | None = ...,
    ) -> ClinicalContext: ...
```

### Folder structure

```
backend/app/
|-- domain/
|   |-- entities.py       (+ RetrievalStats, RetrievalMetadata, LabelEvidencePartition,
|   |                        EvidenceSummary, ClinicalContext.evidence_summary)
|   `-- interfaces.py     (IContextBuilder: 3 optional params)
`-- services/
    `-- context_builder.py

backend/tests/
|-- unit/
|   `-- test_context_builder.py
`-- integration/
    `-- test_context_builder_integration.py
```

No new API route, no new DB table, no new `infrastructure/` file.

### Determinism rules (explicit, tested, not assumed)

Core principle: no output collection's order may ever depend on Python
dict/set iteration order -- every returned tuple's order comes from an
explicit final sort with a stated key.

- All input cases explicitly sorted by `(-similarity, study_uid)` first,
  before any grouping/dedup logic.
- Near-dup collapse (by `cluster_id`): highest similarity survives, ties
  broken by `study_uid` ascending -- a consequence of the initial sort.
- `top_retrieved_case`: first element of the post-dedup sorted sequence;
  `None` if input is empty.
- `findings_evidence`/`impressions_evidence`: built by iterating the
  post-dedup sorted sequence in order, deduplicating exact-duplicate text
  via first-seen-in-sorted-order (never via unordered set operations).
- Supporting/contradictory partition: exact set-intersection on `labels`
  vs. the partition's label; output tuples preserve post-dedup sorted order.
- `label_evidence`: ordered by `vote_weight` descending, ties broken by
  `label` alphabetically.
- Empty-input case: zero retrieved cases -> `EvidenceSummary` with empty
  tuples, `top_retrieved_case=None`, zeroed stats, `label_evidence=()` --
  must not raise.

### Sequence diagram

```mermaid
sequenceDiagram
    participant T as Test/Future Orchestrator
    participant RS as RetrievalService (frozen)
    participant LV as LabelVotingService (frozen)
    participant CB as ContextBuilder (Phase 5)

    T->>RS: retrieve(image_path, top_k)
    RS-->>T: list[RetrievedCase]
    T->>LV: vote(retrieved_cases)
    LV-->>T: list[VotedLabel]
    T->>CB: build(retrieved_cases, voted_labels, retrieval_metadata=...)
    CB->>CB: sort by (-similarity, study_uid) [explicit, deterministic]
    CB->>CB: collapse near-duplicates by cluster_id
    CB->>CB: partition_for_label(cases, top_voted_label)
    CB->>CB: expose findings_evidence / impressions_evidence (deduped, no synthesis)
    CB->>CB: identify top_retrieved_case
    CB->>CB: compute retrieval_stats
    CB-->>T: ClinicalContext(evidence_summary=...)
```

### Dependency diagram

```mermaid
flowchart TD
    subgraph SVC["backend/app/services/"]
        RS[RetrievalService - frozen]
        LV[LabelVotingService - frozen]
        CB[ContextBuilder - NEW]
    end
    subgraph DOM["backend/app/domain/"]
        ICB[IContextBuilder]
        ENT1[RetrievedCase, VotedLabel - existing]
        ENT2[RetrievalStats, RetrievalMetadata,<br/>LabelEvidencePartition, EvidenceSummary - NEW]
        ENT3[ClinicalContext - extended]
    end

    RS -->|list of RetrievedCase| CB
    LV -->|list of VotedLabel| CB
    CB -.implements.-> ICB
    CB --> ENT2
    CB --> ENT3
    ENT3 --> ENT2
```

### Unit testing strategy

Pure function tests, no collaborators to fake:
- global sort correctness + tie-break
- near-dup collapse correctness (hand-built `cluster_id` groups)
- `top_retrieved_case` correctness incl. `None`-on-empty-input
- generic label-partition helper correctness, tested with more than one
  label to prove it is NOT hardcoded to "the top label" internally
- `findings_evidence`/`impressions_evidence` dedup + order correctness
- `retrieval_stats` correctness against hand-calculated values
- `RetrievalMetadata` passthrough correctness
- **determinism regression test**: run `build()` twice on the same
  shuffled input, assert byte-identical output -- the test that actually
  enforces the determinism rules, not just documents them
- empty-input edge case; all-cases-share-one-cluster edge case

### Integration testing strategy

Real `RetrievalService` + real `LabelVotingService` (frozen, unmodified)
against a real test image -> real output fed into `ContextBuilder.build()`
-> assert: label_evidence sums to num_cases_after_dedup with no
overlap/gaps for the represented label, `evidence_summary` fully
populated, `top_retrieved_case` matches the highest-similarity case in the
real result, no exceptions.

### Future compatibility (documented seams, not built now)

Questionnaire enrichment mechanism deferred to its own future phase.
Multimodal frontal+lateral support flagged as a known gap (`RetrievedCase`
has no `projection` field yet) -- not speculatively added now. Differential
Diagnosis extends `label_evidence` by calling the existing generic
partition helper across multiple labels -- no redesign required, per
refinement 2 above. Longitudinal Patient History and Explainability Chat
are additive consumers of `EvidenceSummary`/`top_retrieved_case`, not
requiring changes to this phase's output shape.

### Risks

1. Determinism is only actually verified by the regression test in the
   unit test list above -- without it, "deterministic" is a claim, not a
   proven property.
2. `findings_evidence`/`impressions_evidence` must never be described as
   "summaries" in the thesis -- they are structured raw evidence, full
   stop; a precise sentence in the methodology chapter avoids overclaiming,
   consistent with how the `label_set` and cross-modal alignment
   limitations were handled honestly elsewhere in this log.
3. The `IContextBuilder`/`ClinicalContext` changes are real edits to
   long-frozen domain files -- explicitly confirmed by the user before
   implementation, not silently introduced.

---

## Phase 5 — Context Builder — Implementation & Validation

Implemented step by step against the frozen architecture above, with real
execution and explicit confirmation gating each step, same discipline as
every Phase 4 step. Four steps; all touched files listed per step below.

### Step 1 — Domain layer changes

Added the four new frozen entities (`RetrievalStats`, `RetrievalMetadata`,
`LabelEvidencePartition`, `EvidenceSummary`) to `app/domain/entities.py`
and the one additive `ClinicalContext.evidence_summary: Optional[...] =
None` field, field-for-field against the frozen spec. Relaxed
`IContextBuilder.build()` in `app/domain/interfaces.py` to the 5-parameter
signature (`questionnaire_answers`/`clinical_notes` now optional,
`retrieval_metadata: RetrievalMetadata | None = ...` added), matching the
Protocol-stub convention of `= ...` placeholders rather than real defaults
(Protocols declare shape, not runtime behavior). Grepped the codebase for
every existing constructor of `ClinicalContext` and every
implementer/caller of `IContextBuilder` before editing -- none existed yet
outside the two frozen files themselves, so the additive change had
nothing to break. Regression check: all 24 pre-existing Phase 4 tests
re-run unchanged and passing.

### Step 2 — `ContextBuilder` service (`app/services/context_builder.py`)

Implemented `build()` exactly per the frozen determinism rules: one
explicit `sorted(retrieved, key=lambda c: (-c.similarity, c.source_uid))`
first, near-dup collapse by `cluster_id` as a direct consequence of that
sort (first-seen-per-cluster, no independent re-sort), a single generic
`_partition_for_label(cases, label)` helper called once for
`voted_labels[0].label`, first-seen-in-sorted-order text dedup for
`findings_evidence`/`impressions_evidence`, and an explicit empty-input
branch returning a fully-populated-but-zeroed `EvidenceSummary` rather
than raising.

**Naming correction caught before implementation:** the frozen spec's
prose described the tie-break key as `study_uid`; `RetrievedCase`'s actual
frozen field (since Phase 3/4) is `source_uid` -- a documentation error in
the spec text, not a code discrepancy. Used `source_uid` throughout; spec
text corrected separately.

**Two correctness catches worth highlighting, both caught before writing
formal tests, via a hand-built smoke scenario run against real code:**

1. **`cluster_id == -1` is a sentinel meaning "not part of any cluster,"
   not a groupable key.** A naive "collapse by `cluster_id`" implementation
   would treat every unset case as belonging to the same group and
   incorrectly collapse them all down to one survivor. Fixed by special-
   casing `cluster_id == -1` to always pass through as its own singleton,
   never compared against other `-1` cases. Verified with a scenario
   containing two real near-dup clusters plus two independent `cluster_id
   = -1` cases and confirming all four survived as distinct entries where
   expected (the two real clusters correctly collapsed, the two singletons
   correctly did not).
2. **The concrete implementation must not carry the Protocol's `= ...`
   placeholder into real code.** `IContextBuilder.build()`'s Protocol stub
   correctly uses `= ...` (a valid stub placeholder, not a real default);
   the concrete `ContextBuilder.build()` uses actual defaults
   (`questionnaire_answers: dict[str, str] | None = None`, converted to
   `{}` inside the body -- avoiding the classic Python mutable-default-
   argument bug -- `clinical_notes: str = ""`, `retrieval_metadata:
   RetrievalMetadata | None = None`). Caught as a review note before
   implementation began, then verified directly: a smoke call to `build()`
   omitting all three optional arguments returned `{}`/`""`/`None`, not
   `Ellipsis`, and the same case was later formalized as its own unit test
   (below).

### Step 3 — Unit tests (`backend/tests/unit/test_context_builder.py`)

13 pure-function tests, no collaborators to fake, hand-calculated expected
values throughout (same convention as
`test_label_voting_service.py`): global sort + tie-break, near-dup
collapse (including the `cluster_id == -1` singleton case and the
all-cases-share-one-cluster edge case), `top_retrieved_case` correctness
including `None`-on-empty, the generic label-partition helper proven with
two different labels producing genuinely different partitions,
`findings_evidence`/`impressions_evidence` dedup proven across cases in
*different* clusters (isolating text-content dedup from cluster-collapse
dedup as the actual mechanism), hand-calculated `RetrievalStats`,
two-way `RetrievalMetadata` passthrough (present and `None`), the
single-tuple `label_evidence` shape, a determinism regression test
(shuffled input, full dataclass-equality output comparison), the
omitted-optional-args/no-Ellipsis-leak test, and the empty-input edge
case. Real output:

```
backend\tests\unit\test_context_builder.py::test_global_sort_tie_break PASSED
backend\tests\unit\test_context_builder.py::test_near_dup_collapse_keeps_highest_similarity PASSED
backend\tests\unit\test_context_builder.py::test_unset_cluster_id_singletons_not_collapsed PASSED
backend\tests\unit\test_context_builder.py::test_all_cases_share_one_cluster_collapses_to_single_survivor PASSED
backend\tests\unit\test_context_builder.py::test_top_retrieved_case_first_post_dedup_and_none_on_empty PASSED
backend\tests\unit\test_context_builder.py::test_partition_for_label_is_generic_across_different_labels PASSED
backend\tests\unit\test_context_builder.py::test_findings_and_impressions_dedup_by_text_across_different_clusters PASSED
backend\tests\unit\test_context_builder.py::test_retrieval_stats_hand_calculated PASSED
backend\tests\unit\test_context_builder.py::test_retrieval_metadata_passthrough_and_default_none PASSED
backend\tests\unit\test_context_builder.py::test_build_label_evidence_is_single_tuple_for_top_voted_label PASSED
backend\tests\unit\test_context_builder.py::test_determinism_shuffled_input_same_output PASSED
backend\tests\unit\test_context_builder.py::test_build_with_only_required_args_has_no_ellipsis_leak PASSED
backend\tests\unit\test_context_builder.py::test_empty_input_returns_zeroed_evidence_summary_without_raising PASSED
13 passed in 0.03s
```

### Step 4 — Integration test (`backend/tests/integration/test_context_builder_integration.py`)

Real `RetrievalService` + real `LabelVotingService` (frozen, unmodified
since Phase 4) against a real masked image from `ml/datasets/masked/`, fed
into `ContextBuilder.build()` -- no fakes/mocks anywhere in the path.
`retrieval_metadata` was deliberately constructed from the real
`app.core.config.settings` values (`CHROMA_COLLECTION_NAME`/
`CHROMA_EMBEDDING_MODEL`/`CHROMA_EMBEDDING_VERSION`) that `/retrieve`'s own
`_build_response()` uses for this identical retrieval call, rather than a
synthetic value or the untested-elsewhere `None` branch (already covered
in Step 3) -- so the integration test exercises the real production
config path and lands on a fully-populated `EvidenceSummary` with zero
`None` fields. Asserted: `label_evidence[0]`'s supporting + contradictory
case UIDs are disjoint and sum to exactly `num_cases_after_dedup`;
`top_retrieved_case.similarity` matches the true maximum similarity in
both the raw and post-dedup retrieved lists; no exception anywhere in the
real retrieve -> vote -> build pipeline. Real output:

```
backend\tests\integration\test_context_builder_integration.py::test_context_builder_against_real_retrieval_and_voting PASSED
1 passed, 1 warning in 9.20s
```

### Full regression (Phase 4 + Phase 5 combined)

Run from repo root after every step and one final time at the close of
Step 5:

```
======================= 38 passed, 4 warnings in 19.73s =======================
```

24 Phase 4 tests + 13 Phase 5 unit tests + 1 Phase 5 integration test, all
green, zero regressions introduced by the additive domain changes.

### How to Write This in Your Thesis

*Methodology chapter, "Context Builder Implementation" subsection:*

> The Context Builder was implemented directly against its frozen
> architecture, in four verified steps: additive domain-entity changes,
> the deterministic organizing service itself, a pure-function unit test
> suite, and an integration test exercising the real retrieval and voting
> services against a genuine chest X-ray image. Two implementation-level
> correctness issues were caught and fixed before being formalized as
> regression tests, illustrating why "matches the design on paper" and
> "behaves correctly in code" are distinct claims worth verifying
> separately. First, the near-duplicate cluster identifier carries a
> sentinel value denoting "not part of any cluster"; a naive grouping
> implementation would have silently merged every unclustered case into a
> single entry, which was caught by constructing a scenario with multiple
> independent unclustered cases and confirming each survived distinctly.
> Second, the service's optional parameters were verified to fall back to
> genuine empty defaults (an empty dictionary, an empty string, `None`)
> rather than leaking the placeholder value used in the abstract
> interface's type stub, confirmed by a dedicated test that omits every
> optional argument and inspects the returned values directly. The
> resulting suite adds 13 unit tests and 1 integration test to the
> existing Phase 4 suite, bringing the full backend test suite to 38
> passing tests with no regressions, and the integration test in
> particular was deliberately configured to exercise a production
> configuration path (real collection/model/version metadata) rather than
> a synthetic stand-in, so that the audit-trail fields introduced by this
> phase are proven against genuine values, not placeholders.

---

## Phase 5 (Context Builder) — COMPLETE

All four steps of the frozen development order (domain entities ->
`ContextBuilder` service -> unit tests -> integration test) implemented,
tested with real execution at every step, and confirmed by the user
before proceeding at each gate -- same discipline as Phase 4. No new API
route, no new DB table, no new `infrastructure/` file, per the frozen
scope. One documentation-only correction surfaced during implementation
and fixed: the frozen spec's prose named the sort/tie-break key
`study_uid`; the actual frozen `RetrievedCase` field is `source_uid` --
code uses the real field name, spec text corrected to match. Full backend
test suite: **38/38 passing** (24 Phase 4 + 13 Phase 5 unit + 1 Phase 5
integration). Not yet built (explicitly out of Phase 5 scope per the
frozen architecture): the questionnaire-enrichment mechanism, multimodal
frontal+lateral support, and Differential Diagnosis's multi-label loop
over the now-generic `_partition_for_label` helper -- all deferred to
whichever future phase introduces them.
---

## Phase 6 — Prompt Builder: Architecture (FROZEN)

**Status: approved and frozen.** Not to be redesigned without a critical
correctness issue. Phase ordering revised from the original roadmap:
Prompt Builder and LLM Orchestrator now precede Clinical Questionnaire,
Explainability Chat, and Longitudinal History -- rationale: since
`ClinicalContext.questionnaire_answers`/`clinical_notes` were already made
optional in Phase 5, Questionnaire is no longer a blocker for producing a
complete report, and proving the full generation pipeline works end-to-end
is higher priority than adding more input surfaces to an unproven pipeline.
Revised order: Phase 6 (Prompt Builder) -> Phase 7 (LLM Orchestrator) ->
Phase 8 (Response Validator + Hospital Report Formatter) -> Phase 9
(Clinical Questionnaire) -> Phase 10 (Explainability Chat) -> Phase 11
(Longitudinal History) -> Phase 12 (Frontend).

### Objective

Transform a `ClinicalContext` (Phase 5's output) into a deterministic
prompt string for a specific language. Pure text construction only -- no
LLM calls, no response parsing, no report formatting, no clinical judgment.

### Gaps identified and resolved before freezing

1. **Scope narrowed from `IPromptBuilder`'s three pre-existing methods to
   one.** `build_generation_prompt` is implemented in Phase 6.
   `build_explanation_prompt` remains an unimplemented placeholder for
   Phase 10. `build_translation_prompt` is not implemented -- bilingual
   output is produced by the LLM generating directly in the target
   language via a `language` parameter on `build_generation_prompt`, not
   via a separate translation pass (avoids translation-quality loss and an
   extra LLM call/failure point).
2. **Retry/correction prompt ownership resolved in favor of Prompt
   Builder, not LLM Orchestrator.** The originally proposed Phase 7 scope
   ("response validation" as an LLM Orchestrator responsibility) would have
   put prompt-text composition inside a module whose own stated boundary
   is "no prompt construction" -- a direct contradiction if retry-prompt
   text were composed ad hoc there. Resolved by adding
   `build_retry_prompt(context, language, previous_response,
   validation_errors) -> str` to `IPromptBuilder` now. Prompt Builder owns
   ALL prompt text, including corrections; Phase 7's LLM Orchestrator only
   calls it and manages retry-loop timing/count -- pure orchestration, zero
   prompt composition, consistent with its own stated boundary.
3. **No timestamps/wall-clock dependence in generation prompts,** for
   determinism and testability. Report date-stamping is Phase 8's concern
   at formatting time, not something the LLM needs during generation.
4. **Mandatory prompt content specified explicitly, not left to
   implementation discretion:** ground only on retrieved evidence, do not
   invent information absent from evidence, use `VotedLabel.agreement` to
   express appropriate uncertainty (not false certainty), output strictly
   JSON with no markdown/code-block wrapping, JSON schema exactly matching
   `ReportContent`'s seven fields (`examination`, `clinical_history`,
   `technique`, `findings`, `impression`, `recommendation`, `disclaimer`).
5. **Response Validator (user's addition, adopted) reconciled against
   Phase 7's stated "response validation" responsibility** -- these
   overlapped as originally described and needed an explicit split to
   avoid redundant or, worse, entirely-skipped checks: Phase 7's LLM
   Orchestrator performs only TRANSPORT/STRUCTURAL validation (syntactically
   valid JSON, required keys present, triggers retry via Prompt Builder on
   failure). Phase 8's Response Validator performs SEMANTIC/CLINICAL
   validation on an already structurally-valid object: missing sections,
   evidence-consistency checks, and a hallucination heuristic. The
   hallucination heuristic is explicitly scoped as deterministic
   term-overlap between the LLM's output text and known evidence labels --
   stated honestly as a limited, documented signal (same honesty
   convention as the Phase 0 label-overlap relevance proxy: 89%
   precision/49% recall, a conservative lower bound, not a solved
   problem), not a guarantee of hallucination-free output. True semantic
   hallucination detection is an open research problem outside this
   phase's scope.

### Interface (final)

```python
class IPromptBuilder(Protocol):
    def build_generation_prompt(self, context: ClinicalContext, language: str) -> str: ...
    def build_retry_prompt(
        self, context: ClinicalContext, language: str,
        previous_response: str, validation_errors: list[str],
    ) -> str: ...
    def build_explanation_prompt(self, report: Report, question: str) -> str: ...   # unimplemented, Phase 10
    def build_translation_prompt(self, content: ReportContent, target_language: str) -> str: ...  # unimplemented
```

### Data contracts

**Input:** `ClinicalContext` (with `evidence_summary` populated, per
Phase 5), `language: str` (`"en"`/`"bn"`, matching the frozen `Language`
enum). Retry variant additionally takes `previous_response: str`,
`validation_errors: list[str]`.

**Output:** one deterministic `str` per call -- the complete prompt
including the schema instruction block (all 7 `ReportContent` fields),
JSON-only output instruction, grounding/anti-hallucination instruction,
confidence/agreement framing, and the serialized evidence from
`EvidenceSummary` (`findings_evidence`, `impressions_evidence`,
`label_evidence`), in the order Phase 5 already guarantees deterministic.

### Folder structure

```
backend/app/
|-- domain/
|   `-- interfaces.py       (IPromptBuilder: + build_retry_prompt)
`-- services/
    `-- prompt_builder.py

backend/tests/
`-- unit/
    `-- test_prompt_builder.py
```

No integration test folder in this phase -- Prompt Builder has no live
collaborators to integration-test against until Phase 7 exists to consume
its output; its integration proof arrives naturally as part of Phase 7's
integration test (a real LLM call against a real generated prompt).

### Determinism rules

Prompt output is a pure function of `(context, language)`, and additionally
`(previous_response, validation_errors)` for the retry variant -- no
timestamps, no random ordering, no dependence on anything outside the
stated inputs. Since `ClinicalContext`'s collections are already
deterministically ordered (Phase 5), Prompt Builder only serializes in the
given order, never re-sorts.

### Sequence diagram

```mermaid
sequenceDiagram
    participant O as Future Orchestrator (Phase 7)
    participant PB as PromptBuilder (Phase 6)

    O->>PB: build_generation_prompt(context, language)
    PB->>PB: serialize evidence_summary (deterministic order, from Phase 5)
    PB->>PB: embed schema instruction (ReportContent fields)
    PB->>PB: embed grounding + confidence instructions
    PB-->>O: prompt string

    Note over O: if LLM output fails validation
    O->>PB: build_retry_prompt(context, language, previous_response, errors)
    PB-->>O: correction prompt string
```

### Dependency diagram

```mermaid
flowchart TD
    subgraph SVC["backend/app/services/"]
        CB[ContextBuilder - frozen, Phase 5]
        PB[PromptBuilder - NEW]
    end
    subgraph DOM["backend/app/domain/"]
        IPB[IPromptBuilder]
        ENT[ClinicalContext, EvidenceSummary - frozen]
    end

    CB -->|ClinicalContext| PB
    PB -.implements.-> IPB
    PB --> ENT
```

### Unit testing strategy

Pure string-content assertions, no collaborators to fake:
- schema instruction block present, lists all 7 `ReportContent` fields
- language instruction correctly reflects `"en"` vs `"bn"`
- grounding/anti-hallucination instruction present
- `VotedLabel.agreement`'s actual value appears correctly in the prompt
- all `findings_evidence`/`impressions_evidence` entries appear in output
- empty-`EvidenceSummary` edge case (Phase 5's empty-input path) does not
  crash, produces a sane "no evidence available" prompt
- `build_retry_prompt` includes the previous response and the specific
  validation errors, not a generic "try again"
- **determinism regression test**: same `(context, language)` called
  twice, byte-identical output -- same pattern as Phase 5

### Risks

1. Prompt length/token budget not addressed at `top_k=5` scale -- noted
   for future scaling, not a current concern.
2. `build_translation_prompt` may end up permanently unimplemented if
   direct-language-generation holds through Phase 8 -- a deliberate
   non-implementation to be stated as such, not silently forgotten.
3. `build_retry_prompt`'s interface shape is necessarily provisional until
   Phase 7 exists to exercise it in practice -- real risk that Phase 7
   surfaces a shape mismatch; mitigated by keeping the signature minimal.

---

## Phase 6 — Prompt Builder — Implementation & Validation

Implemented step by step against the frozen architecture above, with real
execution and explicit confirmation gating each step, same discipline as
Phases 4 and 5. Four steps.

### Step 1 — Interface change

Added `build_retry_prompt(context, language, previous_response,
validation_errors) -> str` to `IPromptBuilder` in `app/domain/interfaces.py`,
alongside the existing `build_generation_prompt`. `build_explanation_prompt`
and `build_translation_prompt` left untouched as unimplemented stubs, per
the frozen spec. Grepped the codebase for every existing implementer/caller
of `IPromptBuilder` before editing -- none existed yet, so the additive
change had nothing to break. Regression check: all 38 pre-existing Phase
4/5 tests re-run unchanged and passing.

### Step 2 — `PromptBuilder` service (`app/services/prompt_builder.py`)

Implemented `build_generation_prompt(context, language)` and
`build_retry_prompt(...)` as pure string construction over `(context,
language)` (and additionally `previous_response`/`validation_errors` for
the retry variant) -- no LLM calls, no timestamps, no wall-clock reads.
Only these two `IPromptBuilder` methods are implemented on the class;
`build_explanation_prompt`/`build_translation_prompt` are simply absent
(`IPromptBuilder` is a Protocol, not an ABC, so partial implementation is
valid and matches the frozen spec's scope). `build_retry_prompt` is built
directly on top of `build_generation_prompt`'s own output (full schema,
grounding, confidence, and evidence sections included) plus an appended
retry section carrying `previous_response` and each `validation_errors`
entry verbatim -- satisfying "full context on retry, not just an error
message in isolation" as a structural guarantee rather than a convention
to remember. The empty-`EvidenceSummary` case (Phase 5's zeroed-input
path) and the `evidence_summary is None` case are both handled by the same
guard, degrading to a fixed "no evidence available" message rather than
crashing or emitting a malformed prompt.

**Correctness/UX catch made during review, before Step 3's tests were
written -- not after:** the first working version emitted `agreement`/
`vote_weight` via plain `str()` on the raw float (e.g.
`0.6666666666666666`). Flagged as a real issue, not a style nit: full
float precision is no more accurate to an LLM than a rounded value (both
are pure functions of the same input, so rounding costs nothing on
determinism), and the same `agreement` value appeared twice in the
prompt -- once in the confidence-instruction sentence, once in the label-
evidence block -- at different implicit precision, inviting the reader
(human or model) to wonder whether they were two different numbers. Fixed
by formatting both values as `f"{value:.2f}"` everywhere they appear,
consistently. Verified directly against a real generated prompt before
and after the fix (`0.6666666666666666` -> `0.67` in both locations), and
Step 3 formalized the fix as a regression test that asserts the rounded
value is present *and* that the old full-precision `str()` representation
is absent -- closing the regression rather than only covering the happy
path.

Real example (real `ClinicalContext` built via the actual, frozen
`ContextBuilder` from Phase 5 -- 3 hand-built retrieved cases, 2 voted
labels):

```
You are an AI radiology assistant generating a structured chest X-ray report.

LANGUAGE INSTRUCTIONS:
Respond in English.

OUTPUT FORMAT INSTRUCTIONS:
You must output ONLY a single JSON object and nothing else. Do not wrap the JSON in markdown code fences (no ``` characters), and do not include any explanation, preamble, or trailing text outside the JSON object. The JSON object must contain exactly these 7 string fields, in this shape:
{
  "examination": "<string>",
  "clinical_history": "<string>",
  "technique": "<string>",
  "findings": "<string>",
  "impression": "<string>",
  "recommendation": "<string>",
  "disclaimer": "<string>"
}

GROUNDING INSTRUCTIONS:
You must base your report ONLY on the evidence provided below. Do not invent, infer, or hallucinate any finding, measurement, or clinical detail that is not directly supported by the evidence below. If the evidence is insufficient to support a finding, do not include it.

CONFIDENCE / UNCERTAINTY INSTRUCTIONS:
The top candidate label from retrieval-based voting is "Pneumonia" with an agreement score of 0.67 (the fraction of retrieved neighbor cases agreeing on this label). If this agreement score is low, you MUST express appropriate clinical uncertainty in your findings and impression rather than false certainty. Do not state a diagnosis as certain when the agreement score is low.

EVIDENCE:
Retrieved findings from similar cases (most similar first):
1. Bilateral patchy opacities in the lower lung zones, more prominent on the right.
2. Mild cardiomegaly with clear lung fields.
3. Right lower lobe consolidation with air bronchograms.

Retrieved impressions from similar cases (most similar first):
1. Findings consistent with multifocal pneumonia.
2. Stable cardiac silhouette enlargement, no acute pulmonary process.
3. Findings favor pneumonia over atelectasis.

Label evidence (top voted label partition):
- Label: Pneumonia
- Vote weight: 1.69
- Agreement: 0.67
- Supporting cases: 2
- Contradictory cases: 1

Now generate the JSON report.
```

The empty-evidence path (fed `ContextBuilder().build([], [])` directly)
degrades to:

```
EVIDENCE:
No retrieved evidence is available for this case.
```

with the schema/grounding/confidence sections still fully present above
it -- confirmed not to crash and not to emit a malformed or empty prompt.

### Step 3 — Unit tests (`backend/tests/unit/test_prompt_builder.py`)

12 pure string-content assertion tests, `ClinicalContext`/`EvidenceSummary`
constructed directly (not via `ContextBuilder`) to keep this suite isolated
to `PromptBuilder`'s own behavior. Covers every item in the frozen spec's
unit testing strategy list: the schema block lists all 7 `ReportContent`
fields (read from `dataclasses.fields(ReportContent)`, not a hardcoded
list, so the test cannot silently drift from the entity -- same discipline
as Phase 4's `Settings`/collection-name parity check), the `"en"`/`"bn"`
language instruction, the grounding instruction, the JSON-only/no-markdown
instruction, the rounded `agreement` value present with the old
full-precision string explicitly asserted absent, every
`findings_evidence`/`impressions_evidence` entry present in the output,
both the empty-`EvidenceSummary` and `evidence_summary is None` edge cases,
`build_retry_prompt` carrying the previous response and validation errors
verbatim (with an explicit assertion that no generic "please try again"
text is substituted in), and a determinism regression test for both
`build_generation_prompt` and `build_retry_prompt` (identical inputs called
twice, asserted byte-identical). Real output:

```
backend\tests\unit\test_prompt_builder.py::test_schema_instruction_lists_all_seven_report_content_fields PASSED
backend\tests\unit\test_prompt_builder.py::test_language_instruction_reflects_en_and_bn PASSED
backend\tests\unit\test_prompt_builder.py::test_grounding_instruction_present PASSED
backend\tests\unit\test_prompt_builder.py::test_output_only_json_no_markdown_instruction_present PASSED
backend\tests\unit\test_prompt_builder.py::test_top_label_agreement_value_appears_rounded_in_prompt PASSED
backend\tests\unit\test_prompt_builder.py::test_all_findings_and_impressions_evidence_entries_appear_in_output PASSED
backend\tests\unit\test_prompt_builder.py::test_empty_evidence_summary_produces_no_evidence_message_without_raising PASSED
backend\tests\unit\test_prompt_builder.py::test_none_evidence_summary_produces_no_evidence_message_without_raising PASSED
backend\tests\unit\test_prompt_builder.py::test_build_retry_prompt_includes_previous_response_and_validation_errors_verbatim PASSED
backend\tests\unit\test_prompt_builder.py::test_build_retry_prompt_with_no_validation_errors_uses_fallback_text PASSED
backend\tests\unit\test_prompt_builder.py::test_determinism_same_inputs_produce_byte_identical_generation_prompt PASSED
backend\tests\unit\test_prompt_builder.py::test_determinism_same_inputs_produce_byte_identical_retry_prompt PASSED
12 passed in 0.03s
```

### Full regression (Phase 4 + Phase 5 + Phase 6 combined)

Run after every step and one final time at the close of Step 4:

```
======================= 50 passed, 4 warnings in 20.90s =======================
```

24 Phase 4 tests + 14 Phase 5 tests (13 unit + 1 integration) + 12 Phase 6
unit tests, all green, zero regressions introduced by the additive
interface change or the new service.

### How to Write This in Your Thesis

*Methodology chapter, "Prompt Builder Implementation" subsection:*

> The Prompt Builder was implemented directly against its frozen
> architecture in four verified steps: an additive interface extension, the
> deterministic prompt-construction service itself, a pure string-content
> unit test suite, and a final full-suite regression run. One
> implementation-level issue was caught and corrected before it could be
> locked in by the test suite: the initial implementation rendered
> similarity-derived confidence values (the retrieval-based label
> agreement score) using full floating-point precision, which is
> unnecessary for an autoregressive model to consume correctly and, more
> importantly, caused the same underlying value to appear in two places in
> the prompt at what read as two different levels of precision, creating
> an avoidable source of ambiguity for the model consuming the prompt. The
> fix -- rendering the value at a fixed, consistent precision everywhere it
> appears -- was verified against a real generated prompt both before and
> after the change, and the unit test suite was written to assert not only
> that the corrected value is present but that the original,
> higher-precision representation is absent, so that a future regression
> reintroducing full-precision output would be caught rather than silently
> passing. This illustrates a recurring theme in this project's validation
> approach: catching an issue during implementation review, before it is
> encoded as an assumed-correct baseline in a test suite, is materially
> different from catching it after, since a test suite written against
> already-incorrect behavior would have certified that behavior rather than
> guarded against it.

---

## Phase 6 (Prompt Builder) — COMPLETE

Both steps of the frozen development order that required implementation
(interface extension, `PromptBuilder` service) are built, tested with real
execution at every step, and confirmed by the user before proceeding at
each gate -- same discipline as Phases 4 and 5. No integration test folder
in this phase, per the frozen scope -- Prompt Builder has no live
collaborators to integration-test against until Phase 7's LLM Orchestrator
exists to consume its output. `build_explanation_prompt` (Phase 10) and
`build_translation_prompt` (permanently unimplemented, per the frozen
architecture's decision to generate directly in the target language rather
than translate) remain deliberately absent, not silently forgotten. One
real correctness/UX issue was caught and fixed during implementation, not
discovered afterward: full-precision float formatting of
`agreement`/`vote_weight` values, corrected to a consistent 2-decimal
rounding everywhere those values appear in a prompt. Full backend test
suite: **50/50 passing** (24 Phase 4 + 14 Phase 5 + 12 Phase 6). Not yet
built (explicitly out of Phase 6 scope per the frozen architecture): the
LLM Orchestrator that will actually call `build_generation_prompt`/
`build_retry_prompt` against a real model (Phase 7), and the transport/
structural response validation that will trigger the retry path in
practice.
---

## Phase 7 — LLM Orchestrator: Architecture (FROZEN)

**Status: approved and frozen.** Not to be redesigned without a critical
correctness issue. First phase touching a non-deterministic external
system (a real LLM), and the first phase where "same input -> byte-
identical output" cannot be claimed or tested the same way as every prior
phase -- this limitation is stated explicitly below rather than glossed
over.

### Objective

Orchestrate: build prompt (via frozen Phase 6 `PromptBuilder`) -> call the
LLM -> structurally validate the response -> retry with a correction
prompt on failure -> return a structurally-valid `ReportContent` draft, or
raise a specific exception when a retry budget is exhausted. Zero prompt
composition (Phase 6's responsibility), zero semantic/clinical judgment
(Phase 8's responsibility), zero persistence, zero business logic of its
own -- pure sequencing of injected collaborators, same discipline as
`RetrievalService` (Phase 4).

### Decisions frozen

1. **Model**: Ollama, `llama3.1:8b-instruct-q4_K_M` as the configured
   default. Treated as a tunable config value, not an architectural
   commitment -- switching models later is a config change, not an
   interface change.
2. **No persistence in this phase.** `ReportContent` is returned to the
   caller; the `reports` table and all persistence logic are deferred to
   Phase 8, once a fully validated, formatted report exists to save.
3. **No new API endpoint in this phase.** Validated at the service layer
   directly (unit + integration tests). The real generation endpoint
   arrives in Phase 8 once the full draft -> semantic-validate -> format
   chain exists to expose.
4. **Two independent retry budgets, two distinct exceptions** -- transport
   failure (Ollama unreachable/timeout) and content failure (malformed/
   incomplete JSON) are different problems and must not share one retry
   count: retrying a content-correction prompt against an unreachable
   server is nonsensical. `LLMTransportError` on transport-budget
   exhaustion; `LLMGenerationValidationError` (carrying the last raw
   response and last validation errors) on content-budget exhaustion.
5. **`temperature=0.0` as the default**, to minimize (not eliminate)
   output variance. Explicitly documented limitation: true determinism
   cannot be guaranteed for an LLM call even at temperature 0, due to
   well-understood floating-point non-associativity effects in batched
   inference. Stated plainly in the thesis as an understood, accounted-for
   boundary of the deterministic-by-design discipline that has held since
   Phase 5, not an oversight.
6. **`StructuralValidator` validates structure only**: valid JSON, all 7
   `ReportContent` fields present, all string-typed. Does **not** reject
   empty-string field values -- content quality/completeness is explicitly
   Phase 8's Response Validator's responsibility, not this phase's.
7. **`IStructuralValidator` is its own Protocol**, separate from
   `ILLMOrchestrator` -- mirrors the `ImageValidator`/`SimilaritySearchPolicy`
   split from Phase 4, enabling the orchestrator's retry-*loop* logic to be
   unit-tested against a fake validator (always-pass/always-fail)
   independently of the real JSON-parsing edge cases, which get their own
   focused test file.
8. **Markdown code-fence handling: lenient, bounded.** If a response is
   wrapped in a well-known fence pattern (e.g. ` ```json ... ``` `), strip
   it, then parse strictly. No fuzzy extraction beyond that single
   stripping step -- an unparseable-after-stripping response is a genuine
   content-validation failure, triggering the normal retry path.
9. **Phase 7's responsibility is strictly**: call `PromptBuilder`, call
   Ollama, structurally validate, manage retries, return `ReportContent`.
   Explicitly excludes: business logic, diagnosis, report formatting,
   semantic validation, persistence, API responsibility.

### Interfaces (new)

```python
class ILLMOrchestrator(Protocol):
    def generate_draft(self, context: ClinicalContext, language: str) -> ReportContent: ...

class IStructuralValidator(Protocol):
    def validate(self, raw_response: str) -> tuple[bool, ReportContent | None, list[str]]:
        """Returns (is_valid, parsed_content_or_None, validation_errors)."""
        ...
```

`ILLMClient` (frozen since early domain scaffolding) is unchanged --
`complete(prompt: str) -> str` remains sufficient; `OllamaClient` owns its
own model/timeout/temperature configuration internally, constructor-
injected from `Settings`, same pattern as every other infrastructure
adapter. Smaller footprint on frozen files than Phase 5 or 6 required.

### Exceptions (new, `backend/app/services/exceptions.py`)

```python
class LLMTransportError(Exception):
    """Ollama unreachable or timed out after the transport retry budget."""

class LLMGenerationValidationError(Exception):
    """Content retry budget exhausted; structural validation never passed."""
    def __init__(self, last_raw_response: str, last_validation_errors: list[str]): ...
```

### Folder structure

```
backend/app/
|-- domain/
|   `-- interfaces.py          (+ ILLMOrchestrator, + IStructuralValidator)
|-- services/
|   |-- structural_validator.py
|   |-- llm_orchestrator.py
|   `-- exceptions.py
|-- infrastructure/
|   `-- ollama_client.py       (implements ILLMClient)
`-- core/config.py              (+ OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS,
                                    LLM_CONTENT_RETRY_COUNT, LLM_TRANSPORT_RETRY_COUNT, LLM_TEMPERATURE)

backend/tests/
|-- unit/
|   |-- test_structural_validator.py   (pure JSON/shape checks, no LLM)
|   `-- test_llm_orchestrator.py       (fake PromptBuilder + fake ILLMClient + fake StructuralValidator)
`-- integration/
    `-- test_llm_orchestrator_integration.py   (real Ollama call; structural assertions ONLY, never exact content)
```

### Data contracts

**Input:** `ClinicalContext`, `language: str`.
**Output:** `ReportContent` -- all 7 fields present and string-typed;
content quality/non-emptiness explicitly not guaranteed by this phase.
**Failure:** raises `LLMTransportError` or `LLMGenerationValidationError`,
never returns a partially-valid object.

### Sequence diagram

```mermaid
sequenceDiagram
    participant O as LLMOrchestrator (Phase 7)
    participant PB as PromptBuilder (frozen, Phase 6)
    participant LLM as OllamaClient
    participant SV as StructuralValidator

    O->>PB: build_generation_prompt(context, language)
    PB-->>O: prompt
    loop up to LLM_TRANSPORT_RETRY_COUNT+1 times
        O->>LLM: complete(prompt)
        alt timeout/connection error
            LLM-->>O: raises transport error
        else success
            LLM-->>O: raw_response
        end
    end
    Note over O: transport budget exhausted -> raise LLMTransportError

    loop up to LLM_CONTENT_RETRY_COUNT+1 times
        O->>SV: validate(raw_response)
        alt valid
            SV-->>O: (True, ReportContent, [])
            O-->>O: return ReportContent
        else invalid
            SV-->>O: (False, None, validation_errors)
            O->>PB: build_retry_prompt(context, language, raw_response, validation_errors)
            PB-->>O: retry_prompt
            O->>LLM: complete(retry_prompt)
            LLM-->>O: raw_response (new attempt)
        end
    end
    Note over O: content budget exhausted -> raise LLMGenerationValidationError
```

### Dependency diagram

```mermaid
flowchart TD
    subgraph SVC["backend/app/services/"]
        PB[PromptBuilder - frozen, Phase 6]
        SV[StructuralValidator - NEW]
        O[LLMOrchestrator - NEW]
    end
    subgraph INFRA["backend/app/infrastructure/"]
        OC[OllamaClient - NEW]
    end
    subgraph DOM["backend/app/domain/"]
        ILO[ILLMOrchestrator]
        ISV[IStructuralValidator]
        ILC[ILLMClient - frozen]
        ENT[ClinicalContext, ReportContent - frozen]
    end

    O --> PB
    O --> OC
    O --> SV
    O -.implements.-> ILO
    SV -.implements.-> ISV
    OC -.implements.-> ILC
    O --> ENT
```

### Determinism rules (revised for this phase's real constraint)

`StructuralValidator` and the retry-*loop mechanics* remain fully
deterministic and are tested as such (fakes, canned responses, byte-for-
byte assertions). The LLM call itself is explicitly NOT claimed
deterministic -- `temperature=0.0` minimizes variance but does not
guarantee identical output run-to-run.

### Unit testing strategy

**`StructuralValidator`**: valid complete JSON passes; missing key fails
with a specific error message identifying which key; wrong-typed value
fails; JSON wrapped in a known markdown fence is stripped then parsed
successfully; JSON that remains unparseable after stripping fails as a
genuine content error (not a crash); empty-string field values PASS
(explicitly not this validator's concern).

**`LLMOrchestrator`** (fake `PromptBuilder`, fake `ILLMClient`, fake
`StructuralValidator`): success-on-first-attempt path; success-after-N-
retries path; content-budget-exhausted raises `LLMGenerationValidationError`
carrying the correct last-response/errors; transport-budget-exhausted
raises `LLMTransportError`; confirms `build_retry_prompt` (not
`build_generation_prompt`) is called on retry attempts, with the actual
validation errors from the immediately preceding failed attempt, not
stale ones from an earlier attempt.

### Integration testing strategy

Real `OllamaClient` + real `PromptBuilder` + a real `ClinicalContext`
(built via the real, frozen `ContextBuilder`) -> real
`LLMOrchestrator.generate_draft()`. Assert STRUCTURAL properties only:
returns a `ReportContent`, all 7 fields present and are strings. Does NOT
assert exact content -- asserting against non-deterministic output would
be the wrong thing to lock a test to.

### Risks

1. The `OLLAMA_TIMEOUT_SECONDS` default is an unmeasured starting guess
   against real local hardware; expect tuning after the first real
   integration run, as a config change, not an architecture change.
2. This is the first phase whose thesis section states a limitation
   (non-determinism) rather than a guarantee -- written to read as
   understood and accounted for, not as an unaddressed gap.
3. `IStructuralValidator`'s lenient-fence-stripping behavior is a stated,
   bounded exception to strict parsing -- must not silently expand into
   broader fuzzy-parsing tolerance over time without a deliberate,
   flagged decision to do so.

---

## Phase 7 — LLM Orchestrator — Implementation & Validation

Implemented step by step against the frozen architecture above, with real
execution and explicit confirmation gating each step, same discipline as
Phases 4-6. First phase touching a real, non-deterministic external
system (a local Ollama model), and the first phase whose integration test
output cannot be asserted byte-for-byte.

### Step 1 — Config + domain layer

Added `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS`,
`LLM_CONTENT_RETRY_COUNT`, `LLM_TRANSPORT_RETRY_COUNT`, `LLM_TEMPERATURE`
to `Settings`; `ILLMOrchestrator` and `IStructuralValidator` to
`interfaces.py`; `LLMTransportError`/`LLMGenerationValidationError` to the
new `app/services/exceptions.py`, the latter storing `last_raw_response`/
`last_validation_errors` as real attributes with a message that surfaces
the validation errors directly rather than requiring a caller to know to
inspect an attribute. Grepped for existing implementers/callers of the new
interfaces/exceptions first -- none existed, purely additive. Regression
check: all 50 pre-existing Phase 4/5/6 tests re-run unchanged and passing.

### Step 2 — `StructuralValidator` (`app/services/structural_validator.py`)

Structure-only validation: well-known markdown-fence stripping (bounded,
single step) -> strict JSON parse -> all 7 `ReportContent` fields (read
from `dataclasses.fields(ReportContent)`, same discipline as Phase 6's
schema test) present and string-typed. Two behaviors verified with real,
explicit assertions rather than left as assumed-correct: empty-string
field values explicitly PASS (Phase 8's Response Validator's concern, not
this validator's), and a response wrapped in a fence but still unparseable
JSON *after* stripping correctly falls through to a genuine content
validation failure rather than crashing or silently passing.

### Step 3 — `OllamaClient` (`app/infrastructure/ollama_client.py`)

Thin `ILLMClient` adapter over Ollama's `POST /api/generate` (non-
streaming), all four tunables (`base_url`/`model`/`timeout_seconds`/
`temperature`) defaulting from `Settings`. `httpx.HTTPError` (covering
connection errors, timeouts, and non-2xx status via `raise_for_status()`)
is caught and re-raised as `LLMTransportError` -- one exception type for
every way the transport layer can fail to produce a usable response.
`httpx` promoted from a transitive-only dependency to an explicit
`requirements.txt` line, same precedent as Step 11's `fastapi`/`uvicorn`
promotion in Phase 4.

**Real-hardware gap found before writing any code**: the frozen spec's
default model, `llama3.1:8b-instruct-q4_K_M`, was not pulled on this
machine (`ollama list` showed only `llama3:8b` available). Confirmed with
the user rather than assumed; resolved by changing `Settings.OLLAMA_MODEL`'s
default to `llama3:8b` -- a config-value swap to what's actually available
locally, not an architecture change, exactly matching the frozen spec's
own framing of the model choice as tunable config, not an architectural
commitment. Documented in `config.py` at the point of change.

Verified directly against the real, running local Ollama instance (not
just unit-testable in isolation): a real `complete()` call returned `'OK'`
for a trivial prompt, and a deliberately unreachable port correctly raised
`LLMTransportError` rather than hanging or raising something the
orchestrator couldn't distinguish from success.

### Step 4 — `LLMOrchestrator` (`app/services/llm_orchestrator.py`)

Pure sequencing over three injected collaborators, two independent retry
budgets, per the frozen sequence diagram: build the initial prompt once,
call the LLM, structurally validate, retry with `build_retry_prompt` on
content failure using the *current* attempt's raw response/errors, return
on success, raise `LLMGenerationValidationError` (carrying the last raw
response/errors) on content-budget exhaustion or `LLMTransportError` on
transport-budget exhaustion.

**Real gap found and fixed during this step, before Step 5's tests were
written around the old, narrower behavior -- the same "matches the design
on paper" vs. "correct in practice" distinction Phase 6's float-precision
catch illustrated:** the first working version wrapped the transport-retry
budget around only the very first `complete()` call, exactly as the
frozen sequence diagram literally drew it. Flagged as a real gap, not a
style nit, by re-reading the diagram against the actual failure semantics
it was meant to express: a transport failure (Ollama unreachable/timed
out) is the same category of problem regardless of *when* in the sequence
it happens, so a call made during a content-retry attempt was getting zero
transport protection purely as an artifact of where it appeared in the
method, not because that failure mode is somehow less real on a retry.
Fixed by refactoring to a single internal helper,
`_call_llm_with_transport_retry(prompt)`, that owns the full "call the
LLM, retry up to `LLM_TRANSPORT_RETRY_COUNT` times on transport failure,
raise `LLMTransportError` if exhausted" behavior, used at every real call
site -- the initial call and every content-retry's call -- so each
invocation gets its own fresh transport-retry budget, fully independent of
the content-retry budget and of how many content-retries have already
happened. The frozen architecture doc's sequence diagram itself contained
this gap (confirmed with the user, who traced it to their own diagramming
error, not an implementation deviation) and is to be corrected to match.

Verified with five hand-run scenarios against fakes before any formal test
was written: (A) success after 2 content retries, using deliberately
*different* error messages per attempt to prove `build_retry_prompt`
receives the immediately-preceding attempt's errors, never stale ones from
an earlier attempt; (B) content-budget exhaustion raising
`LLMGenerationValidationError` with the correct last response/errors; (C)
transport-budget exhaustion raising `LLMTransportError` with the same
prompt resent unchanged across retries; (D) a transport hiccup on the
*first* call recovering before content validation ever runs; (E, added
specifically to prove the fix) a transport failure occurring on a
*content-retry's* call correctly retried at the transport level using the
same retry prompt, recovering, rather than raising immediately as the
pre-fix version would have. All five, plus an explicit standalone
assertion that `build_generation_prompt` is called exactly once across
multiple retries, were then formalized as named tests in Step 5.

### Step 5 — Unit tests

`test_structural_validator.py` (8 tests): valid JSON, missing key, wrong
type, both fence forms (`` ```json `` and bare `` ``` ``), fenced-but-
still-invalid, unfenced-unparseable, and empty-string-fields-explicitly-
pass. `test_llm_orchestrator.py` (7 tests): the five scenarios above as
named tests plus a first-attempt-success baseline and the standalone
call-count-exactly-once test. Real output:

```
backend\tests\unit\test_structural_validator.py::test_valid_complete_json_passes PASSED
backend\tests\unit\test_structural_validator.py::test_missing_key_fails_with_specific_error PASSED
backend\tests\unit\test_structural_validator.py::test_wrong_typed_value_fails_with_specific_error PASSED
backend\tests\unit\test_structural_validator.py::test_fenced_json_with_language_tag_strips_and_parses PASSED
backend\tests\unit\test_structural_validator.py::test_fenced_json_without_language_tag_strips_and_parses PASSED
backend\tests\unit\test_structural_validator.py::test_fenced_but_still_invalid_json_fails_as_content_error_not_crash PASSED
backend\tests\unit\test_structural_validator.py::test_unparseable_json_without_fence_fails_as_content_error_not_crash PASSED
backend\tests\unit\test_structural_validator.py::test_empty_string_field_values_explicitly_pass PASSED
backend\tests\unit\test_llm_orchestrator.py::test_success_on_first_attempt PASSED
backend\tests\unit\test_llm_orchestrator.py::test_scenario_a_success_after_n_content_retries_uses_current_not_stale_errors PASSED
backend\tests\unit\test_llm_orchestrator.py::test_scenario_b_content_budget_exhausted_raises_with_last_response_and_errors PASSED
backend\tests\unit\test_llm_orchestrator.py::test_scenario_c_transport_budget_exhausted_raises_llm_transport_error PASSED
backend\tests\unit\test_llm_orchestrator.py::test_scenario_d_transport_retry_recovers_before_content_validation PASSED
backend\tests\unit\test_llm_orchestrator.py::test_scenario_e_transport_failure_during_content_retry_gets_its_own_budget PASSED
backend\tests\unit\test_llm_orchestrator.py::test_build_generation_prompt_called_exactly_once_across_multiple_retries PASSED
15 passed in 0.04s
```

### Step 6 — Integration test (`test_llm_orchestrator_integration.py`)

Real `RetrievalService` + `LabelVotingService` + `ContextBuilder` (the
frozen Phase 4/5 pipeline, against a real masked image) building a real
`ClinicalContext`, fed into a real `PromptBuilder` + real `OllamaClient` +
real `StructuralValidator`, driving a real `LLMOrchestrator.generate_draft()`
-- no fakes anywhere in this path. Asserts structural properties only
(returns a `ReportContent`, all 7 fields present and string-typed), per
the frozen spec's explicit instruction not to assert exact content against
non-deterministic output.

```
backend\tests\integration\test_llm_orchestrator_integration.py::test_llm_orchestrator_generates_structurally_valid_report PASSED
1 passed, 1 warning in 15.18s
```

`generate_draft()`'s own wall-clock time: **5.95s**, against
`OLLAMA_TIMEOUT_SECONDS=120` -- roughly 20x headroom on this hardware for
a single clean call with zero retries. No evidence yet that the default
needs tuning either direction; Risk #1 above remains open pending a run
that actually exercises retries or heavier load.

The real generated `ReportContent`, verbatim, model `llama3:8b`,
`temperature=0.0`, from the single real run above -- **presented as one
genuine, valid example of the pipeline working, not as a reproducible
fixture**: per this phase's own frozen Decision 5 and Determinism rules,
an LLM call is explicitly not guaranteed to produce identical output on a
future run even at temperature 0.0, so this exact text should not be
expected to recur and must never be asserted against in a test:

```
--- examination ---
Chest X-ray
--- clinical_history ---
Unknown
--- technique ---
Posteroanterior (PA) view
--- findings ---
Increased opacity within the right upper lobe with possible mass and associated area of atelectasis or focal consolidation. Opacity in the left midlung overlying the posterior left 5th rib may represent focal airspace disease.
--- impression ---
Increased opacity in the right upper lobe with possible mass and associated atelectasis or focal consolidation, possibly representing a focal consolidation or mass lesion. Recommend chest CT for further evaluation.
--- recommendation ---
Chest CT
--- disclaimer ---
Clinical uncertainty due to low agreement score (0.60)
```

Worth stating plainly, not just noting the test passed: this output is
concrete evidence that Phase 6's confidence-framing and grounding
instructions are actually being followed by the model, not merely
producing well-formed JSON that happens to read plausibly. The
`disclaimer` field cites the real, specific agreement score (0.60) from
this run's actual `VotedLabel.agreement` value rather than generic
boilerplate, and `clinical_history: "Unknown"` is an honest admission of
absent information rather than a fabricated history -- exactly the
grounding behavior Phase 6's prompt was designed to elicit, now observed
working end to end against a real model for the first time.

### Full regression (Phase 4 + Phase 5 + Phase 6 + Phase 7 combined)

Run after every step and one final time at the close of Step 7:

```
======================= 66 passed, 5 warnings in 29.15s =======================
```

24 Phase 4 + 14 Phase 5 (13 unit + 1 integration) + 12 Phase 6 unit + 16
Phase 7 (15 unit + 1 integration), all green, zero regressions.

### How to Write This in Your Thesis

*Methodology chapter, "LLM Orchestrator Implementation" subsection:*

> The LLM Orchestrator was implemented and validated in seven steps,
> culminating in the first real, end-to-end execution of the full
> retrieval -> voting -> context-building -> prompt-construction ->
> generation pipeline against a genuine local language model. Two
> implementation-level issues were caught and corrected before they could
> be locked in by their respective test suites, continuing the pattern
> established in Phase 6: the initial retry-orchestration logic protected
> against transport failure (the LLM being unreachable or timing out) only
> for the very first call in a generation attempt, an artifact of
> following the architecture's sequence diagram literally rather than
> re-deriving the failure semantics it was meant to express. Since a
> transport failure is the same category of problem irrespective of which
> call in the sequence it occurs on, this was corrected to apply the
> transport-retry budget uniformly to every real call the orchestrator
> makes, and a dedicated regression scenario was added specifically to
> prove a transport failure occurring mid-retry now recovers rather than
> failing immediately. This phase also required addressing, rather than
> deferring, a property no earlier phase in this pipeline had to contend
> with: genuine non-determinism. Every phase through Prompt Builder
> produced output that was a pure, reproducible function of its inputs,
> verified by byte-identical regression tests; a real language model call,
> even configured at temperature zero, does not carry that same guarantee,
> owing to well-understood floating-point non-associativity effects in
> batched inference. This limitation was treated as an anticipated,
> designed-for boundary rather than a discovered flaw -- the architecture
> was frozen with this constraint already stated, the integration test was
> written from the outset to assert only structural properties (a
> complete, correctly-typed report object) rather than exact wording, and
> the one real generated report captured during validation is presented
> in this thesis as a single illustrative example of the pipeline
> functioning correctly, not as a reproducible artifact. That example is,
> nonetheless, informative on its own merits: the model's response
> demonstrably incorporated the retrieval-derived confidence signal (citing
> the actual agreement score rather than a generic caveat) and declined to
> fabricate clinical history it had not been given, both concrete evidence
> that the grounding and uncertainty-framing instructions constructed in
> the Prompt Builder phase were substantively followed, not merely
> satisfied at the level of output formatting.

---

## Phase 7 (LLM Orchestrator) — COMPLETE

All seven steps of the frozen development order (config + domain layer ->
`StructuralValidator` -> `OllamaClient` -> `LLMOrchestrator` -> unit tests
-> integration test -> full regression) are built, tested with real
execution at every step -- including a real local Ollama model, not a
fake -- and confirmed by the user before proceeding at each gate, same
discipline as Phases 4-6. Two real implementation-level gaps were caught
and fixed before being locked in by tests, not discovered afterward: the
`OLLAMA_MODEL` config default (changed to the model actually pulled on
this machine, `llama3:8b`, documented as a config change) and the
transport-retry budget scope (widened from "only the first call" to
"every real call," with the frozen architecture doc's sequence diagram
itself acknowledged as the source of the gap). No new API endpoint, no
persistence, per the frozen scope -- both arrive in Phase 8 once a fully
validated, formatted report exists to save and expose. Full backend test
suite: **66/66 passing** (24 Phase 4 + 14 Phase 5 + 12 Phase 6 + 16 Phase
7). This phase's thesis treatment states its one real limitation --
LLM output non-determinism, even at `temperature=0.0` -- directly and
plainly, as an anticipated and designed-for boundary of the pipeline, not
an unaddressed gap. Not yet built (explicitly out of Phase 7 scope):
Phase 8's semantic/clinical Response Validator, Hospital Report Formatter,
persistence, and the real generation API endpoint.

---

## Phase 8 — Response Validator + Hospital Report Formatter: Architecture (FROZEN)

**Status: approved and frozen.** Not to be redesigned without a critical
correctness issue. Largest phase since Phase 4 -- broken into 9 smaller,
independently-confirmed implementation steps rather than the 4-7 step
pattern used in Phases 5-7, given its size.

### Objective

Close the loop from a persisted retrieval session to a stored, formatted
report draft: reconstruct evidence from a session, re-run the frozen
retrieval/voting/context/generation chain, semantically validate the LLM's
output as a set of warnings (not a gate), format into a structured
hospital-style object, and persist -- with full reproducibility metadata
(LLM model/temperature, embedding model/version, collection name) stored
alongside every generated report.

### Structural boundary (reaffirmed, stated explicitly per direct request)

Phase 8 is entirely `backend/`. No `frontend/` files created or modified.
Every new file lands in its correct existing Clean Architecture subfolder
(`domain/`, `services/`, `infrastructure/`, `models/`, `api/`, `tests/`).
The one shared-contract surface (the `/generate-report` response shape)
stays backend-owned in `app/api/schemas.py`, same precedent as Phase 4's
`RetrieveResponse` -- no cross-language shared code created at this stage.
PDF/print rendering and all UI concerns remain explicitly out of scope,
deferred to Phase 12 (Frontend).

### Decisions frozen

1. **No automatic semantic retry.** `ResponseValidator` produces
   `SemanticValidationResult` as warnings surfaced to a human reviewer,
   never a pass/fail gate that triggers automated LLM regeneration. An
   automated "fix the hallucination and regenerate" loop is a real safety
   risk for a medical system -- a second LLM attempt is not guaranteed to
   be less hallucinated, only differently worded, and could optimize
   toward passing the heuristic rather than being correct. Consistent
   with the human-in-the-loop framing established since the PHI-masking
   design discussion: the AI drafts and flags its own uncertainty: a
   clinician decides.
2. **`IVectorStore.get_by_ids(uids: list[str]) -> list[RetrievedCase]`**
   added (additive) to reconstruct full case content for a session, since
   `retrieved_evidence` (Phase 4) only stores `study_uid`/`rank`/
   `similarity`, not findings/impression/labels -- this data lives in
   ChromaDB. This closes a gap flagged as early as the original Phase 5
   scoping discussion and correctly deferred at the time.
3. **Hallucination heuristic is a concrete, grounded, bounded design**:
   reuse the frozen Phase 0 18-class taxonomy (`label_mapping.yaml`) as
   the term dictionary. Scan generated `findings`/`impression` text
   (case-insensitive) for taxonomy-class mentions; flag any mentioned
   class absent from the case's `label_evidence` labels as an unsupported
   term. Stated explicitly, same honesty convention as the Phase 0
   label-overlap proxy: a limited, documented signal, not a hallucination
   guarantee.
4. **`ReportFormatter` produces a structured object only** --
   `FormattedReport`, not rendered PDF/HTML. This is also where the report
   date is generated (a Phase 6 decision deferred date-stamping to
   formatting time, not generation time) -- `report_date` is computed here,
   never inside the LLM prompt.
5. **Bengali section headers require external review before being treated
   as clinically correct** -- proposed candidates are not to be presented
   as verified medical terminology without a domain reviewer's sign-off.
6. **New `ReportGenerationService`** orchestrates the full chain (fetch
   session evidence -> vote -> build context -> generate -> semantically
   validate -> format -> persist), keeping `POST /generate-report`'s route
   thin, per the Phase 4 thin-routes rule.
7. **Reproducibility metadata persisted with every report**: `llm_model`,
   `llm_temperature` read directly from `Settings` at record-keeping time
   (the same source `OllamaClient` itself reads from) rather than by
   extending `LLMOrchestrator`'s frozen return type -- avoids touching a
   frozen Phase 7 interface. `embedding_model`/`embedding_version`/
   `collection_name` sourced from `ClinicalContext.evidence_summary
   .retrieval_metadata`, already threaded through since Phase 5.

### Entities (new)

```python
@dataclass(frozen=True)
class SemanticValidationResult:
    missing_findings: bool
    missing_impression: bool
    unsupported_terms: tuple[str, ...]
    top_label_unreflected: bool
    warnings: tuple[str, ...]
    is_clean: bool

@dataclass(frozen=True)
class FormattedReport:
    content: ReportContent
    language: str
    report_date: str
    section_headers: dict[str, str]

@dataclass(frozen=True)
class GenerationMetadata:
    llm_model: str
    llm_temperature: float
    embedding_model: str
    embedding_version: str
    collection_name: str
```

### Interfaces (new)

```python
class IResponseValidator(Protocol):
    def validate_semantic(
        self, content: ReportContent, evidence_summary: EvidenceSummary,
        voted_labels: list[VotedLabel],
    ) -> SemanticValidationResult: ...

class IReportFormatter(Protocol):
    def format(self, content: ReportContent, language: str, report_date: str) -> FormattedReport: ...

# Additive to frozen IVectorStore (Phase 4):
def get_by_ids(self, uids: list[str]) -> list[RetrievedCase]: ...
```

### Database (new `reports` table)

```
reports:
  id (UUID, PK)
  session_id (UUID, FK -> retrieval_sessions.id)
  language (str)
  status (frozen ReportStatus enum -- AI_DRAFT for all Phase 8 output)
  ai_content (JSON, ReportContent fields)
  validation_warnings (JSON, SemanticValidationResult.warnings)
  report_date (str)
  llm_model (str)
  llm_temperature (float)
  embedding_model (str)
  embedding_version (str)
  collection_name (str)
  created_at, updated_at
```

`final_content`/doctor-edit fields on the frozen `Report` entity remain
null/unused -- a future editing phase's concern, not built here.

### API response (extends Phase 4's precedent)

```json
{
  "report_id": "uuid",
  "session_id": "uuid",
  "formatted_report": { "content": {...}, "language": "en", "report_date": "...", "section_headers": {...} },
  "validation": { "is_clean": true, "warnings": [] },
  "generation_metadata": { "llm_model": "...", "llm_temperature": 0.0, "embedding_model": "...", "embedding_version": "...", "collection_name": "..." }
}
```

### Folder structure

```
backend/app/
|-- domain/interfaces.py       (+ IResponseValidator, + IReportFormatter, IVectorStore.get_by_ids)
|-- services/
|   |-- response_validator.py
|   |-- report_formatter.py
|   `-- report_generation_service.py
|-- infrastructure/chroma_store.py   (+ get_by_ids)
|-- models/report.py            (new)
`-- api/generation.py           (POST /generate-report)
alembic/versions/                (new migration)

backend/tests/
|-- unit/{test_response_validator,test_report_formatter,test_report_generation_service}.py
`-- integration/test_generate_report_integration.py
```

### Sequence diagram

```mermaid
sequenceDiagram
    participant C as Client
    participant API as POST /generate-report
    participant RGS as ReportGenerationService
    participant VS as ChromaVectorStore
    participant LV as LabelVotingService (frozen)
    participant CB as ContextBuilder (frozen)
    participant LLM as LLMOrchestrator (frozen)
    participant RV as ResponseValidator
    participant FMT as ReportFormatter
    participant DB as reports table

    C->>API: session_id, language
    API->>RGS: generate(session_id, language)
    RGS->>DB: fetch retrieval_sessions/retrieved_evidence by session_id
    RGS->>VS: get_by_ids(study_uids)
    VS-->>RGS: list[RetrievedCase]
    RGS->>LV: vote(retrieved_cases)
    LV-->>RGS: list[VotedLabel]
    RGS->>CB: build(retrieved, voted_labels)
    CB-->>RGS: ClinicalContext
    RGS->>LLM: generate_draft(context, language)
    LLM-->>RGS: ReportContent
    RGS->>RV: validate_semantic(content, evidence_summary, voted_labels)
    RV-->>RGS: SemanticValidationResult
    RGS->>FMT: format(content, language, report_date)
    FMT-->>RGS: FormattedReport
    RGS->>DB: persist Report (atomic, same pattern as Phase 4)
    RGS-->>API: FormattedReport + SemanticValidationResult
    API-->>C: JSON response
```

### Step breakdown (9 steps, given this phase's size)

1. Domain layer: `get_by_ids` on `IVectorStore`, the 3 new entities,
   `IResponseValidator`/`IReportFormatter` -- regression check.
2. `ChromaVectorStore.get_by_ids()` -- real collection test.
3. `reports` table model + Alembic migration -- schema verification, same
   rigor as Phase 4 Step 10.
4. `ResponseValidator` (taxonomy-heuristic hallucination check,
   missing-section checks) -- unit tests.
5. `ReportFormatter` -- unit tests.
6. `ReportGenerationService` -- unit tests (fakes), including the atomic-
   persistence-failure test (same pattern as Phase 4).
7. `POST /generate-report` endpoint -- thin-route audit, same standard as
   Phase 4 Step 11.
8. Integration test -- real end-to-end chain.
9. Full regression + dev log entry.

### Unit testing strategy

- `ResponseValidator`: empty findings/impression flagged; a taxonomy term
  in output text absent from evidence flagged; high-agreement top label
  missing from output flagged; clean, well-supported input produces
  `is_clean=True` with no false positives.
- `ReportFormatter`: correct headers per language; `report_date` correctly
  injected; pure function, deterministic.
- `ReportGenerationService`: all collaborators faked, correct sequencing,
  atomic persistence (same transaction-failure test pattern as Phase 4).

### Integration testing strategy

Full real chain: real session -> real `get_by_ids` -> real vote/context/
generate/validate/format/persist -> real DB row assertions, same rigor as
Phase 4's `/retrieve` integration tests.

### Risks

1. Largest phase since Phase 4 -- mitigated by the 9-step breakdown above.
2. The taxonomy-term hallucination heuristic will have false positives/
   negatives -- stated as a limited signal in the thesis, same honesty
   convention as every other heuristic in this project.
3. Bengali terminology needs real domain review before being presented as
   clinically validated, not accepted from an LLM-proposed default.

---

## Phase 8 — Response Validator + Hospital Report Formatter — Implementation & Validation

Implemented across the frozen 9-step breakdown, with real execution and
explicit confirmation gating every step, same discipline as every prior
phase. The largest phase since Phase 4, and the phase that finally closes
the loop from a persisted retrieval session to a stored, formatted report
draft. Three real bugs were caught and fixed along the way -- each is
called out at its own step below, not folded together, since each is a
distinct kind of mistake worth remembering separately.

### Step 1 — Domain layer

Added `get_by_ids(uids: list[str]) -> list[RetrievedCase]` to `IVectorStore`
(additive); the three new entities (`SemanticValidationResult`,
`FormattedReport`, `GenerationMetadata`) to `domain/entities.py`; and
`IResponseValidator`/`IReportFormatter` to `interfaces.py`. Grepped for
every existing implementer/caller of `IVectorStore` first (only
`ChromaVectorStore` implements it, only `RetrievalService` depends on it as
a constructor type hint) and confirmed zero `isinstance(x, IVectorStore)`
checks exist anywhere in the codebase -- meaning `ChromaVectorStore` could
correctly continue satisfying the *old* interface shape even before
`get_by_ids` existed on it, since Python doesn't enforce Protocol
completeness at call time. Verified this by running the full suite rather
than reasoning about it alone: **66 passed** (unchanged from Phase 7).

### Step 2 — `ChromaVectorStore.get_by_ids()`

Real fetch (`collection.get(ids=...)`), not a similarity search, so
`similarity` is set to `1.0` for every result -- stated explicitly as a
deliberate choice (no ranking is involved, and the original retrieval-time
distance isn't threaded through this interface, so `1.0` reads honestly as
"not a ranked result" rather than fabricating a plausible-but-meaningless
score). Reuses `map_chroma_results` (the exact mapper `query()` already
uses) by wrapping `get()`'s flat result shape into `query()`'s
nested-per-query shape, rather than writing a second, divergent mapping
path.

**Real, non-obvious API behavior caught by testing against the actual
collection, not assumed either way:** ChromaDB's `collection.get(ids=...)`
does **not** preserve the requested id order --

```
requested order: ['10', '3', '7', '2']
raw get() returned ids order: ['2', '3', '7', '10']
ORDER PRESERVED: False
```

Chroma silently returns results sorted by its own internal order (here,
lexicographic), not the caller's request order. Left unhandled, this would
have been a silent, hard-to-diagnose bug the first time `get_by_ids` fed
into anything order-sensitive downstream. Fixed by explicitly reordering
`get_by_ids`'s output to match the caller's requested order before
returning:

```
returned source_uid order: ['10', '3', '7', '2']
ORDER MATCHES REQUEST: True
```

A uid absent from the collection is silently dropped from the output
(documented explicitly, both in the docstring and an inline comment, as
deliberate -- the expected caller only ever passes a session's own
previously-persisted, already-known-valid study_uids, so a miss here means
the collection was mutated out from under an existing session, not a bad
caller input worth failing loudly on). Verified end to end against the
real `iu_cxr_biomedclip_v1_train` collection: correct count, correct field
mapping (masked `image_path`, full `findings`/`impression`/`labels`),
missing-uid and empty-input edge cases. Full suite: **66 passed**.

### Step 3 — `reports` table + Alembic migration

Schema exactly per the frozen spec: `session_id` FK to
`retrieval_sessions`, `ai_content`/`validation_warnings` as JSON columns,
the 5 reproducibility columns, `status` as a real 4-value `Enum`. Following
Phase 4 Step 10's exact precedent of not trusting the live `dev.db` (which
turned out to be independently drifted -- empty `alembic_version`, no data
tables, unrelated to this phase), two throwaway SQLite files were used
instead: one brought to the current pre-Phase-8 schema state to autogenerate
a clean diff, another completely fresh one to verify the full migration
chain from scratch. Migration file read in full before running anything.

**Naming collision caught and fixed, not left as a documented risk:** the
ORM model was initially named `Report`, identically to the frozen domain
entity in `domain/entities.py`. Flagged as a real correctness risk, not
cosmetic -- an import alias only protects call sites that remember to use
it, and the first author who forgets gets a silent type-shadowing bug at
exactly the domain/infrastructure boundary this architecture exists to
protect. Renamed to `ReportRecord` (table name `reports` unaffected); the
newly-introduced infrastructure class was renamed, not the frozen,
foundational domain concept. Re-verified schema-neutral after the rename:

```
Tables: [alembic_version, retrieval_sessions, retrieved_evidence, reports]
downgrade base -> Tables: [('alembic_version',)]
upgrade head   -> Tables: [alembic_version, retrieval_sessions, retrieved_evidence, reports]
                  FK still intact: [(0, 0, 'retrieval_sessions', 'session_id', 'id', ...)]
```

Identical to the pre-rename result. Full suite: **66 passed**.

### Step 4 — `ResponseValidator`

Structure-only semantic checks: empty findings/impression, a taxonomy-term
hallucination heuristic (reusing the frozen Phase 0 18-class taxonomy from
`label_mapping.yaml`, loaded directly rather than importing across the
frozen `ml/`<->`backend/` boundary -- no clean, importable loader exists;
the only existing one is a private helper inside an `ml/`-only CLI script),
and a high-agreement-top-label-unreflected check
(`TOP_LABEL_AGREEMENT_THRESHOLD = 0.5`, stated explicitly as "a majority of
retrieved neighbor cases agree," not left as an unexamined magic number).

**Real bug caught by the test suite itself, not a happy-path oversight:**
the first implementation used naive substring containment to scan for
taxonomy terms, which flagged `Normal` as an unsupported hallucinated term
because `"normal"` is literally a substring of `"abnormality"`
(**ab** + normal + **ity**) -- a report that never claimed anything was
normal was incorrectly flagged. Caught by
`test_low_agreement_top_label_absent_from_text_not_flagged`, a test
written specifically to catch over-eager flagging, not just
under-flagging. Fixed with `\b`-word-boundary regex matching instead of
plain substring `in`:

```
_contains_term('abnormality noted', 'Normal')                      -> False (fixed)
_contains_term('no acute process, normal exam', 'Normal')            -> True  (still catches real mentions)
_contains_term('life support devices in place', 'Support Devices')   -> True  (multi-word phrases still work)
```

A second, non-obvious correctness decision: `_evidence_labels` unions
labels from **both** `supporting_cases` and `contradictory_cases` in
`label_evidence`, not just `supporting_cases` -- since Phase 5's partition
is exhaustive over every retrieved case (proven by Phase 5's own
integration test), this is the only way to avoid flagging a real,
evidence-backed secondary finding (e.g. `Atelectasis`, living in the
*contradictory* bucket for a *Pneumonia* partition) as hallucinated just
because it isn't the top voted label. Verified with 7 unit tests including
a dedicated test for exactly this scenario:

```
test_clean_well_supported_report_is_clean_with_no_false_positives PASSED
test_empty_findings_flagged PASSED
test_empty_impression_flagged PASSED
test_taxonomy_term_absent_from_evidence_flagged_as_unsupported PASSED
test_high_agreement_top_label_absent_from_text_flagged PASSED
test_low_agreement_top_label_absent_from_text_not_flagged PASSED
test_zero_false_positives_with_varied_phrasing_and_secondary_evidence_backed_finding PASSED
7 passed in 0.05s
```

Full suite: **73 passed** (66 + 7 new).

### Step 5 — `ReportFormatter`

Pure, deterministic `format(content, language, report_date) ->
FormattedReport`. `report_date` is passed through exactly as given, never
generated internally -- confirming the division of responsibility with
Step 6's `ReportGenerationService`, which owns wall-clock time.

Two decisions stated explicitly, as required: an unsupported/unknown
`language` raises `ValueError` rather than silently falling back to
`"en"` -- a caller passing an unexpected language code is a real bug worth
surfacing immediately, since silently defaulting to English headers while
the LLM was asked (Phase 6's `PromptBuilder`) to respond in a different
language would produce a mismatched, mislabeled report, a worse failure
mode in a medical-report system than a loud error. Bengali section headers
are marked explicitly as provisional/unreviewed placeholder terms in code
comments, per the frozen spec's Decision 5 -- the unit test deliberately
does not assert exact Bengali wording, only that a non-empty label exists
per field, so the test suite itself cannot silently certify unvalidated
medical terminology as if it were a verified spec.

```
test_correct_headers_for_english PASSED
test_correct_headers_for_bengali PASSED
test_report_date_passed_through_unchanged PASSED
test_determinism_same_inputs_produce_identical_output PASSED
test_unsupported_language_raises_value_error PASSED
5 passed in 0.02s
```

Full suite: **78 passed** (73 + 5 new).

### Step 6 — `ReportGenerationService`

Pure sequencing over its six injected collaborators, per the frozen
sequence diagram: fetch session + evidence -> `get_by_ids` -> vote ->
build context -> generate -> validate -> format -> persist.

**Real bug caught by the test suite itself:** `generate(session_id: str,
...)` originally passed the raw string straight into a filter against
`RetrievalSession.id`, a `Uuid`-typed column. SQLAlchemy's `Uuid` type
processor expects an actual `uuid.UUID` object, not a string -- it failed
deep inside DBAPI parameter binding
(`AttributeError: 'str' object has no attribute 'hex'`), not as a clean
"not found." Exactly the kind of failure that is brutal to debug in
production: a type mismatch surfacing as a cryptic internal error several
layers away from the actual cause. Fixed by parsing `session_id` into
`uuid.UUID` once at the top of `generate()`, raising the new
`SessionNotFoundError` for both a genuinely-missing session and a
malformed UUID string -- a dedicated regression test
(`test_malformed_session_id_raises_specific_error_not_a_crash`) was added
so this specific failure mode cannot silently reappear.

Two decisions stated explicitly: `LLMTransportError`/
`LLMGenerationValidationError` from `llm_orchestrator.generate_draft()`
propagate **unchanged**, uncaught -- mirrors Phase 4's exact precedent
(`RetrievalService` lets `ValueError` propagate to the one place that
translates domain exceptions into HTTP statuses); catching and re-wrapping
here would duplicate that responsibility. And a reproducibility-metadata
gap, flagged rather than silently worked around: `RetrievalSession`
(Phase 4's frozen schema) does not persist `collection_name`/
`embedding_model`/`embedding_version` per-session, so these are sourced
from `Settings` (the current config) at generation time -- a real, named
limitation if that config changes between a session's original retrieval
and a later report-generation call.

Return signature was extended mid-step, after initial confirmation, from
`(FormattedReport, SemanticValidationResult)` to `(report_id: uuid.UUID,
FormattedReport, SemanticValidationResult, GenerationMetadata)` so Step 7's
API layer would not need to re-query the DB for `report_id`/
`generation_metadata`. `report_id` is returned as a native `uuid.UUID`
(the domain/service layer's own working type throughout), converted to
`str` only at the API/JSON boundary in Step 7 -- the same convention
`app/api/retrieval.py` already uses for `session_id`.

Unit tests use a real, throwaway in-memory SQLite session (not a hand-built
fake) for DB access -- faking SQLAlchemy's query/filter/order_by mechanics
would be more complex and less trustworthy, and it is what let the
atomic-persistence-failure test prove genuine rollback behavior, same
pattern as Phase 4's own `test_transaction_atomicity_on_persistence_failure`.
Every non-DB collaborator is a hand-built fake.

```
test_correct_sequencing_and_data_flow PASSED
test_session_not_found_raises_specific_error_before_touching_collaborators PASSED
test_malformed_session_id_raises_specific_error_not_a_crash PASSED
test_llm_transport_error_propagates_unchanged_and_nothing_persisted PASSED
test_llm_generation_validation_error_propagates_unchanged_and_nothing_persisted PASSED
test_atomic_persistence_failure_leaves_zero_rows PASSED
6 passed in 0.29s
```

Full suite: **84 passed** (78 + 6 new).

### Step 7 — `POST /generate-report`

Typed Pydantic response models (`ReportContentResponse`,
`FormattedReportResponse`, `ValidationResponse`,
`GenerationMetadataResponse`, `GenerateReportResponse`) built from the
start, deliberately avoiding a repeat of Phase 4 Step 12's untyped-dict gap
that had to be retrofitted after the fact. Confirmed route registration
via `app.openapi()` without needing to trigger the expensive real-model
lifespan: `['/health', '/retrieve', '/generate-report']`.

Exception -> HTTP status mapping, each reasoned through rather than
defaulted: `SessionNotFoundError` -> 404; `LLMTransportError` -> **502 Bad
Gateway**, not 503 -- this server is healthy, the failure is an upstream
dependency (Ollama) failing to produce a usable response, and 503 would
incorrectly imply this server itself is overloaded/down;
`LLMGenerationValidationError` -> 422, with `last_raw_response`/
`last_validation_errors` included in the response body so a caller can see
exactly what went wrong.

Thin-route audit (every line of `generate_report`, same standard as Phase 4
Step 11): no line examines or branches on report content values,
recomputes anything beyond field renaming/passthrough, or makes a clinical
judgment -- the same conclusion as Phase 4's own audit.

A small, deliberately-not-deferred fix: `get_db()` had been duplicated
identically in `api/retrieval.py` and the new `api/generation.py`.
Consolidated into a new `app/api/dependencies.py` (neither call site
touches a frozen interface, so this was a same-step fix, not carried
forward) -- verified as a pure, behavior-neutral refactor:

```
84 passed, 5 warnings in 28.99s
```

### Step 8 — Integration test (real end-to-end chain)

`test_generate_report_integration.py`: a real `POST /retrieve` call
(Phase 4's own frozen endpoint, via `TestClient`) creates a genuine
`RetrievalSession`/`RetrievedEvidence` first -- chosen over calling
`RetrievalService` directly, since it is the more integration-realistic
path and needs no duplicated persistence logic in the test -- then a real
`POST /generate-report` against that real `session_id`, exercising every
real collaborator end to end: DB, `ChromaVectorStore.get_by_ids`,
`LabelVotingService`, `ContextBuilder`, `LLMOrchestrator` (a real Ollama
call), `ResponseValidator`, `ReportFormatter`, persistence. The fixture
checks Ollama's reachability first and skips with an actionable message
if it isn't running, rather than silently faking a response.

```
backend\tests\integration\test_generate_report_integration.py::test_generate_report_full_real_chain PASSED
1 passed, 2 warnings in 15.50s
```

`/generate-report`'s own wall-clock time: **3.84s**. The real response, in
full:

```json
{
  "report_id": "fe30aaa6-154a-4b99-af84-2c2532b88a01",
  "session_id": "34d556b0-c3f5-4884-8d71-fb5fa889318a",
  "formatted_report": {
    "content": {
      "examination": "Chest X-ray",
      "clinical_history": "Unknown",
      "technique": "Posteroanterior (PA) view",
      "findings": "Increased opacity within the right upper lobe with possible mass and associated area of atelectasis or focal consolidation. Opacity in the left midlung overlying the posterior left 5th rib may represent focal airspace disease.",
      "impression": "Focal consolidation or mass lesion with atelectasis in the right upper lobe, possibly representing a benign process. Recommend chest CT for further evaluation.",
      "recommendation": "Chest CT",
      "disclaimer": "Clinical uncertainty due to low agreement score (0.60)"
    },
    "language": "en",
    "report_date": "2026-07-12",
    "section_headers": {
      "examination": "Examination",
      "clinical_history": "Clinical History",
      "technique": "Technique",
      "findings": "Findings",
      "impression": "Impression",
      "recommendation": "Recommendation",
      "disclaimer": "Disclaimer"
    }
  },
  "validation": {
    "is_clean": false,
    "warnings": [
      "Top voted label 'Normal' (agreement 0.60) not reflected in report text"
    ]
  },
  "generation_metadata": {
    "llm_model": "llama3:8b",
    "llm_temperature": 0.0,
    "embedding_model": "biomedclip",
    "embedding_version": "v1",
    "collection_name": "iu_cxr_biomedclip_v1_train"
  }
}
```

Worth stating plainly, not just noting the test passed: this is the first
real, genuine demonstration of `ResponseValidator` doing meaningful work
end to end, not just passing its own unit tests. The retrieval-based top
voted label for this case was `Normal` at 0.60 agreement, but the LLM's
generated findings/impression describe a focal consolidation/mass -- a
real discrepancy between what similarity-weighted voting suggested and
what the model actually wrote, correctly surfaced as `is_clean: false`
with a specific, actionable warning, exactly the human-in-the-loop signal
this phase exists to produce (frozen Decision 1: never an automated gate,
always a warning for a clinician to weigh).

Non-determinism discipline carried over from Phase 7: only structural/
contract properties were asserted (all frozen fields present,
`generation_metadata` matches `Settings` exactly, the persisted
`ReportRecord` row matches the response field-for-field) -- never exact
`ReportContent` wording.

### Full regression (Phase 4 through Phase 8 combined)

Run after every step and one final time at the close of Step 9:

```
======================= 85 passed, 6 warnings in 46.72s =======================
```

24 Phase 4 + 14 Phase 5 + 12 Phase 6 + 16 Phase 7 + 19 Phase 8 (7 + 5 + 6
unit + 1 integration), all green, zero regressions across the whole phase.

### How to Write This in Your Thesis

*Methodology chapter, "Response Validator and Report Formatter
Implementation" subsection:*

> Phase 8 closed the loop from a persisted retrieval session to a stored,
> formatted report draft, integrating every prior phase's frozen
> components into a single orchestrated service for the first time. Three
> implementation-level defects were caught during development and fixed
> before being locked in by their respective test suites, each
> illustrating a different category of mistake worth documenting
> separately. First, a third-party vector database's `get`-by-id operation
> was assumed, then verified, not to preserve caller-specified ordering --
> an easy assumption to get wrong silently, since the failure would only
> manifest as subtly incorrect downstream behavior rather than a crash.
> Second, a naive text-matching heuristic intended to detect
> unsupported clinical claims produced a false positive by matching a
> target term as a sub-string of an unrelated, morphologically similar
> word, caught specifically because a test was written to probe for
> over-eager flagging rather than only confirming correct detection.
> Third, a plain string identifier was passed into a database query
> expecting a strongly-typed identifier object, surfacing as an opaque
> internal error several abstraction layers removed from its actual cause
> rather than as a clear validation failure -- a category of defect that,
> left uncaught, tends to be disproportionately costly to diagnose in a
> deployed system. In each case, the fix was verified directly against
> real infrastructure or a dedicated regression test before proceeding,
> consistent with this project's standing discipline of treating "matches
> the design on paper" and "behaves correctly against real inputs" as
> distinct claims. The phase's closing integration test additionally
> produced the first genuine evidence that the semantic response
> validator adds real value rather than only passing its own unit tests:
> against a real generated report, it correctly identified a case where
> the model's written findings diverged from the retrieval system's own
> top-voted label, surfacing this as an explicit warning for clinician
> review rather than silently accepting or automatically rejecting the
> output -- the exact human-in-the-loop behavior the validator was
> designed to provide.

---

## Phase 8 (Response Validator + Hospital Report Formatter) — COMPLETE

All 9 steps of the frozen development order (domain layer ->
`ChromaVectorStore.get_by_ids()` -> `reports` table/migration ->
`ResponseValidator` -> `ReportFormatter` -> `ReportGenerationService` ->
`POST /generate-report` -> integration test -> full regression) are built,
tested with real execution at every step -- including a real local Ollama
model and a real ChromaDB collection, never faked -- and confirmed by the
user before proceeding at each gate, same discipline as every prior phase.
Three real defects were caught and fixed before being locked in by tests,
not discovered afterward: ChromaDB's non-preserved `get`-by-id ordering
(Step 2), a word-boundary substring-matching false positive in the
hallucination heuristic (Step 4), and a `str`/`uuid.UUID` type mismatch at
a database query boundary (Step 6). The full pipeline -- retrieval, voting,
context building, prompt construction, LLM generation, structural
validation, semantic validation, formatting, and persistence -- now runs
end to end through a single real HTTP endpoint for the first time. Full
backend test suite: **85/85 passing** (24 Phase 4 + 14 Phase 5 + 12 Phase 6
+ 16 Phase 7 + 19 Phase 8).

Not yet built, explicitly out of Phase 8 scope per the frozen architecture
and the revised phase ordering (Phase 6's spec): Clinical Questionnaire
(now Phase 9), Explainability Chat (Phase 10), Longitudinal Patient History
(Phase 11), the Frontend (Phase 12), and the doctor-edit review workflow --
`Report.final_content` and the broader edit/approval fields on the frozen
domain `Report` entity remain null/unused, since every Phase 8 output is
persisted as `ReportStatus.AI_DRAFT` only. No PDF/print rendering exists
yet either, per the frozen spec's explicit deferral to Phase 12.

---
