"""
app/core/config.py
====================================================================
Centralized settings (pydantic-settings). Every configurable value in
Phase 4 code -- DB connection, ChromaDB location/collection -- goes
through this class; no hardcoded paths/URLs/names anywhere else.

Not wired into RetrievalService/ChromaVectorStore yet (that's Step 11,
the FastAPI skeleton) -- CHROMA_PERSIST_PATH and CHROMA_COLLECTION_NAME
below are declared with defaults matching chroma_store.py's current
hardcoded values so that, once wired, nothing about runtime behavior
changes.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchored via this file's own location, not the process's CWD -- same
# reasoning as chroma_store.py's DEFAULT_PERSIST_PATH (see that file's
# comment for the incident that made this necessary).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = Path(__file__).resolve().parents[2]

# Matches chroma_store.py's DEFAULT_PERSIST_PATH exactly.
DEFAULT_CHROMA_PERSIST_PATH = str(_REPO_ROOT / "ml" / "outputs" / "retrieval" / "chroma_db")
# Matches chroma_store.py's DEFAULT_COLLECTION_NAME exactly.
DEFAULT_CHROMA_COLLECTION_NAME = "iu_cxr_biomedclip_v1_train"
# The embedding_model/embedding_version components of DEFAULT_CHROMA_COLLECTION_NAME
# above (see build_collection_name() in ml/retrieval/build_chroma_index.py, called
# with ("iu_cxr", "biomedclip", "v1", "train") when the real collection was built).
# Declared here, not re-hardcoded at the API layer, so the frozen response
# contract's embedding_model/embedding_version fields have exactly one source.
DEFAULT_CHROMA_EMBEDDING_MODEL = "biomedclip"
DEFAULT_CHROMA_EMBEDDING_VERSION = "v1"
# SQLite for now (Step 9 scope) -- Postgres is a deployment decision for later.
DEFAULT_DATABASE_URL = f"sqlite:///{_BACKEND_DIR / 'dev.db'}"

# Phase 7 (LLM Orchestrator) -- Ollama connection + retry-budget tuning.
# Declared here, not hardcoded in ollama_client.py/llm_orchestrator.py, same
# config-is-the-only-source-of-truth discipline as every prior phase.
# OLLAMA_MODEL deviates from the frozen spec's llama3.1:8b-instruct-q4_K_M:
# that tag is not pulled on this machine, only llama3:8b is (confirmed via
# `ollama list` during Phase 7 Step 3) -- a documented config-value swap to
# what's actually available locally, not an architecture change, per the
# frozen spec's own framing of the model choice as tunable config.
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3:8b"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 120
DEFAULT_LLM_CONTENT_RETRY_COUNT = 2
DEFAULT_LLM_TRANSPORT_RETRY_COUNT = 1
DEFAULT_LLM_TEMPERATURE = 0.0
# QA fix -- reported as "uploading the exact same image yields different
# results across attempts", and reproduced directly at the LLM layer: with
# temperature=0.0 and no seed, the same prompt sent to llama3:8b five times
# produced TWO distinct reports, diverging inside the IMPRESSION section
# ("the impression is chronic..." vs "the findings are most consistent
# with chronic..."). Temperature 0 selects the highest-probability token but
# does not pin the sampler's initial state, and Ollama's default seed is
# random; identical logits can still tie-break differently. With a seed set,
# the same five runs were byte-identical.
#
# A thesis that reports generated output has to be able to regenerate it, so
# this is a reproducibility property, not a preference. Declared here like
# every other Ollama parameter -- overridable per run for anyone who
# deliberately wants sampling variation, never hardcoded in the adapter.
DEFAULT_LLM_SEED = 42

# The seed is necessary but was measured NOT to be sufficient. With seed=42
# pinned, the FIRST inference after Ollama loads the model into VRAM still
# differs from every subsequent one. Measured over three unload/load cycles:
#
#   cycle 1: cold=a29be3c2 (246 chars)   warm=4e78b784 (238 chars)
#   cycle 2: cold=a29be3c2               warm=4e78b784
#   cycle 3: cold=a29be3c2               warm=4e78b784
#
# Each state is perfectly reproducible; they are reproducibly DIFFERENT from
# each other. So generation is deterministic conditional on whether the model
# was resident, and Ollama evicts it after 5 minutes idle by default. That is
# exactly the reported symptom: draft a report, come back after a coffee,
# upload the same image, get different words -- with nothing in the system
# having changed.
#
# keep_alive holds the model resident so ordinary use stays on one side of
# that boundary. It does not make cold equal warm -- nothing at this layer
# can, it is llama.cpp warm-up state, not sampling -- so the residual
# limitation is documented rather than papered over: a report generated
# immediately after a backend/Ollama restart may differ in wording from one
# generated during a warm session. Content is grounded in the same retrieved
# evidence either way; it is the phrasing that moves.
DEFAULT_OLLAMA_KEEP_ALIVE = "30m"

# Phase 12 Step 1 -- local dev only (frozen spec's Decision 6: deployment
# packaging/CORS-for-production is explicitly out of scope). The Next.js
# dev server's default origin; a real deployment would set this via env,
# not by editing this default.
DEFAULT_CORS_ALLOWED_ORIGINS = "http://localhost:3000"

# Phase 12 Step 7 -- where POST /retrieve persists the MASKED copy of each
# uploaded query image (see app/api/retrieval.py), so the Comparison page
# can redisplay a past visit's X-ray. Gitignored runtime data, same
# treatment as dev.db -- not committed, not a fixture.
DEFAULT_UPLOADED_IMAGES_DIR = str(_BACKEND_DIR / "uploaded_images")

# Phase 13 -- JWT signing secret for doctor sessions. This default is a
# clearly-labeled dev-only placeholder, not a real secret -- a real
# deployment MUST override this via the JWT_SECRET_KEY env var (self-
# registration having no email/identity verification is already a named
# scope boundary for this thesis demo; a hardcoded signing secret would be
# a second, avoidable one layered on top of it).
DEFAULT_JWT_SECRET_KEY = "dev-only-insecure-secret-do-not-use-in-production"
DEFAULT_JWT_ALGORITHM = "HS256"
DEFAULT_JWT_EXPIRATION_MINUTES = 60 * 24  # 24h -- long enough a doctor isn't logged out mid-demo

# ====================================================================
# Input Admission and Modality Gate (input_admission_modality_gate_
# architecture_v1.0_FROZEN.md, §11.1).
#
# That document's §11.1 Rule is explicit: "Do not write any parameter
# value in the source code. Put all values in the settings object." This
# block IS the settings object -- ImageAdmissionService and
# ModalityGateService read every number below off `settings`, and neither
# module contains a literal threshold, size, dimension, or prompt of its
# own. Gate A values are frozen by that document; Gate B values are
# calibration OUTPUTS and are marked as such individually.
# ====================================================================

# --- Gate A: frozen by §11.1. -------------------------------------
DEFAULT_UPLOAD_ALLOWED_EXTENSIONS = "png,jpg,jpeg"
DEFAULT_UPLOAD_MAX_BYTES = 20 * 1024 * 1024        # §11.1: 20 MB
DEFAULT_UPLOAD_MIN_BYTES = 20 * 1024               # §11.1: 20 kB
DEFAULT_IMAGE_MIN_DIMENSION_PX = 256
DEFAULT_IMAGE_MAX_DIMENSION_PX = 8192
DEFAULT_IMAGE_MAX_PIXELS = 80_000_000

# --- Gate B: calibration outputs, NOT frozen (§11.1, rules F2/F4). ---
#
# The prompt set is split into a POSITIVE list and a NEGATIVE list rather
# than held as one flat list. §6 M4 defines the modality score as the
# softmax result "for the chest radiograph prompt" (singular), which is
# exactly what this split produces while the positive list has one entry
# -- but §11.2 Step 6 explicitly anticipates ADDING a lateral prompt if
# lateral films give a high false-negative rate, and at that point "the
# chest radiograph prompt" is no longer a single index. The split names
# which prompts mean "this IS a chest radiograph" so Step 6 can be
# carried out without having to reinterpret M4. With the §11.1 initial
# set below (one positive), the score is bit-identical to a literal M4.
#
# REVISED 2026-08-19, and this too was changed after seeing a real failure
# rather than ahead of it. With the single positive prompt below, a genuine
# frontal chest radiograph that includes the upper abdomen lost the cosine
# to "an abdominal radiograph" by 0.006 (0.3883 vs 0.3945); at temperature
# 1/85.23 that 0.006 becomes 0.37 vs 0.63, and the film was rejected. The
# §11.2 Step 6 extension point anticipated exactly this ("ADDING a lateral
# prompt if lateral films give a high false-negative rate") -- the same
# reasoning applies to framing that includes abdomen.
#
# The negative list gains three "featureless image" prompts at the same
# time, and they are not optional. Measured: widening the positives alone
# admitted a FLAT GREY IMAGE at 0.6592, because five positives spread the
# probability mass far enough for a picture of nothing to clear 0.60. The
# blank negatives put that back to 0.0082.
#
# Measured on a 10-image probe (6 must-pass, 4 must-reject):
#   1 positive  (previous):  4/6 pass-correct, 4/4 reject-correct
#   5 positives, old negs :  6/6 pass-correct, 3/4 reject-correct  <- grey
#   5 positives + blank negs: 6/6 pass-correct, 4/4 reject-correct <- chosen
#   3 positives + blank negs: 4/6 pass-correct, 4/4 reject-correct
# This is a probe, not the §11.2 calibration procedure. Rule F4 still
# applies: do not report these numbers as a calibration result.
DEFAULT_MODALITY_PROMPTS_POSITIVE = (
    "a chest radiograph"
    "|a chest X-ray"
    "|a frontal chest radiograph"
    "|a PA chest radiograph"
    "|a chest radiograph including the upper abdomen"
)
DEFAULT_MODALITY_PROMPTS_NEGATIVE = (
    "a photograph of an object"
    "|an abdominal radiograph"
    "|a document or a scanned page"
    "|a photograph of a person"
    "|a blank image"
    "|a uniform grey image"
    "|an empty image with no anatomy"
)

# PHI masking: the largest single detected region that will actually be
# blacked out, as a fraction of total image area. See
# shared/phi_masking/masker.py's docstring for the incident. Burned-in PHI
# is small and marginal; anything covering more of the frame than this is a
# watermark, and masking it destroys the diagnostic field it sits on.
DEFAULT_PHI_MASK_MAX_REGION_AREA_FRACTION = 0.08

# §6 M2/M4 say "calculate the cosine similarity ... apply softmax to the
# similarity values" and do not name a temperature. Taken literally
# (temperature 1.0), softmax over raw cosines is near-uniform: measured
# on 8 held-out IU frontals plus one natural photograph, every chest
# radiograph scored 0.228-0.232 and the photograph scored 0.190 against
# the 5-prompt set. The classes DO separate, but the whole range sits far
# below §11.1's provisional 0.60, so a literal temperature of 1.0 makes
# that provisional value unreachable by any real radiograph.
#
# The value below is the reciprocal of BiomedCLIP's own learned
# logit_scale (model.logit_scale.exp() == 85.2322769165039, read off the
# frozen encoder), i.e. the temperature the encoder was contrastively
# trained at -- not a number chosen to make a test pass. At this
# temperature the same probe gives 0.9997-1.0000 for the radiographs and
# 0.0000 for the photograph. This is a Gate B parameter like the
# threshold it feeds: recorded here, measured by ml/calibration/
# calibrate_modality_gate.py, overridable per deployment.
DEFAULT_MODALITY_SOFTMAX_TEMPERATURE = 1.0 / 85.2322769165039

# PROVISIONAL (§11.1). An estimate, not a measured value. §11.1's Warning
# and rule F4 both apply: do not report this number as a result, and do
# not write it into the thesis, until the calibration procedure of §11.2
# has produced real command output for it.
DEFAULT_MODALITY_THRESHOLD = 0.60

# --- Gate A (v1.1 §11.1, frozen): the accepted projections. ------
# DR-4: the system accepts frontal chest radiographs only. A14's permitted
# DECLARED values are a superset of these -- a doctor may declare LATERAL,
# and A16 then rejects it with its own reason code; that is a different
# outcome from declaring an unrecognised value, so the two lists are
# declared separately rather than one derived from the other.
DEFAULT_ACCEPTED_PROJECTIONS = "PA,AP"
DEFAULT_DECLARED_PROJECTION_VALUES = "PA,AP,LATERAL"

# --- Gate B (v1.1 §11.4): PROJECTION_REJECT_THRESHOLD. ------------
# §11.1 lists this as "Not selected". This is a Gate B value and is NOT
# frozen (§11.1); §§5-10 of the architecture are untouched by this change.
#
# SELECTION RULE, REVISED 2026-08-19. The rule now reads:
#
#   RULE: just above the observed lateral maximum top-1 similarity.
#
# It previously read "the midpoint of the observed separation gap between
# the lateral maximum and the frontal minimum", which produced
# 0.8695459067821503 from lateral max 0.84847092628479 and frontal min
# 0.8906208872795105 (gap 0.0421).
#
# THIS RULE WAS CHANGED AFTER SEEING A FAILING IMAGE, AND THAT IS RECORDED
# HERE RATHER THAN PRESENTED AS A PRE-REGISTERED CHOICE. A genuine frontal
# chest radiograph obtained from outside the IU dataset scored top-1
# 0.8582 and was rejected as a projection mismatch. That image sits ABOVE
# every lateral in the calibration set (max 0.84847) and BELOW the old
# midpoint -- i.e. inside the empty gap the midpoint rule placed the
# boundary in the middle of.
#
# The legitimate reason the change is defensible, as opposed to merely
# convenient: the calibration population was IU-only, and DEFAULT_RETRIEVAL_
# FLOOR's §11.5 Step R3 note below already states that this gate's real
# purpose is "detection of a distribution shift at deployment time... a film
# from a diagnostic centre in Bangladesh does not [share scanners,
# processing and patient population]. The IU dataset cannot measure that
# shift." A real out-of-distribution frontal scoring 0.8582 IS that
# predicted shift arriving. The midpoint rule had no evidence behind the
# half of the gap it claimed -- no observation of any kind lies between
# 0.84847 and 0.89062 -- so moving the boundary to the edge of what was
# actually observed removes an unmeasured margin rather than adding one.
#
# What the new value preserves, verified on the same 600-study calibration
# set (ml/outputs/calibration/top1_similarity_by_label.csv):
#   300 of 300 lateral still rejected, 0 of 300 frontal rejected.
# The lateral/frontal separation property this gate exists for is intact;
# only the unobserved margin above the lateral ceiling is given up.
#
# Still true, and still the important caveat: this is an OBSERVED
# SEPARATION POINT, not a validated frontal/lateral boundary. It comes from
# 300 images of each projection from one dataset and does not establish a
# universal cosine boundary.
DEFAULT_PROJECTION_REJECT_THRESHOLD = 0.8500

# --- Gate B (v1.1 §11.5): RETRIEVAL_FLOOR. -------------------------
# The v1.0 value 0.7603 is WITHDRAWN. It was fitted on a calibration
# population that was half lateral, and A16 now rejects lateral inputs, so
# that population no longer reaches the floor.
#
# §11.5 Step R1 requires the lower-tail percentile rule to be written down
# BEFORE the resulting value is calculated. The rule, fixed first:
#
#   RULE: the floor is the 0th percentile (the observed minimum) of the
#         top-1 similarity distribution of the FRONTAL calibration set.
#
# Why that percentile: §11.5's Warning states the frontal distribution has
# no low tail and no separation, and that any value INSIDE that band is a
# chosen percentile rather than a measured boundary. The 0th percentile is
# the only lower-tail percentile that puts the boundary at the edge of the
# observed band instead of inside it, so it does not invent a separation
# the data does not show. A 1st or 5th percentile would cut into the
# observed frontal population and mark already-seen frontal cases weak.
#
# Applied: frontal calibration set n=300, 0th percentile = 0.8906208872795105.
#
# Step R2, reported as a result: 0 of 300 held-out frontal cases fall below
# this value. The low-support mechanism is NOT EXERCISED in this
# distribution.
#
# Step R3, the purpose it does serve: detection of a distribution shift at
# deployment time. The calibration population and the archive share
# scanners, processing and patient population; a film from a diagnostic
# centre in Bangladesh does not. The IU dataset cannot measure that shift.
DEFAULT_RETRIEVAL_FLOOR = 0.8906208872795105

# The high/low agreement boundary of §7.2's support matrix. Same value and
# same reasoning as ResponseValidator's existing TOP_LABEL_AGREEMENT_
# THRESHOLD ("a majority of retrieved neighbor cases agree on this
# label"), declared here rather than imported from that module because
# §11.1's rule puts parameter values in the settings object -- the two
# are deliberately the same number today, but they answer different
# questions (one gates a validation warning, one selects a disclaimer
# cell) and nothing requires them to move together.
DEFAULT_DISCLAIMER_AGREEMENT_THRESHOLD = 0.5


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = DEFAULT_DATABASE_URL
    CHROMA_PERSIST_PATH: str = DEFAULT_CHROMA_PERSIST_PATH
    CHROMA_COLLECTION_NAME: str = DEFAULT_CHROMA_COLLECTION_NAME
    CHROMA_EMBEDDING_MODEL: str = DEFAULT_CHROMA_EMBEDDING_MODEL
    CHROMA_EMBEDDING_VERSION: str = DEFAULT_CHROMA_EMBEDDING_VERSION
    OLLAMA_BASE_URL: str = DEFAULT_OLLAMA_BASE_URL
    OLLAMA_MODEL: str = DEFAULT_OLLAMA_MODEL
    OLLAMA_TIMEOUT_SECONDS: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS
    LLM_CONTENT_RETRY_COUNT: int = DEFAULT_LLM_CONTENT_RETRY_COUNT
    LLM_TRANSPORT_RETRY_COUNT: int = DEFAULT_LLM_TRANSPORT_RETRY_COUNT
    LLM_TEMPERATURE: float = DEFAULT_LLM_TEMPERATURE
    LLM_SEED: int = DEFAULT_LLM_SEED
    OLLAMA_KEEP_ALIVE: str = DEFAULT_OLLAMA_KEEP_ALIVE
    CORS_ALLOWED_ORIGINS: str = DEFAULT_CORS_ALLOWED_ORIGINS
    UPLOADED_IMAGES_DIR: str = DEFAULT_UPLOADED_IMAGES_DIR
    JWT_SECRET_KEY: str = DEFAULT_JWT_SECRET_KEY
    JWT_ALGORITHM: str = DEFAULT_JWT_ALGORITHM
    JWT_EXPIRATION_MINUTES: int = DEFAULT_JWT_EXPIRATION_MINUTES
    # Gate A (frozen §11.1)
    UPLOAD_ALLOWED_EXTENSIONS: str = DEFAULT_UPLOAD_ALLOWED_EXTENSIONS
    UPLOAD_MAX_BYTES: int = DEFAULT_UPLOAD_MAX_BYTES
    UPLOAD_MIN_BYTES: int = DEFAULT_UPLOAD_MIN_BYTES
    IMAGE_MIN_DIMENSION_PX: int = DEFAULT_IMAGE_MIN_DIMENSION_PX
    IMAGE_MAX_DIMENSION_PX: int = DEFAULT_IMAGE_MAX_DIMENSION_PX
    IMAGE_MAX_PIXELS: int = DEFAULT_IMAGE_MAX_PIXELS
    # Gate B (calibration outputs -- see the block above, and rules F2/F4)
    MODALITY_PROMPTS_POSITIVE: str = DEFAULT_MODALITY_PROMPTS_POSITIVE
    MODALITY_PROMPTS_NEGATIVE: str = DEFAULT_MODALITY_PROMPTS_NEGATIVE
    MODALITY_SOFTMAX_TEMPERATURE: float = DEFAULT_MODALITY_SOFTMAX_TEMPERATURE
    PHI_MASK_MAX_REGION_AREA_FRACTION: float = DEFAULT_PHI_MASK_MAX_REGION_AREA_FRACTION
    MODALITY_THRESHOLD: float = DEFAULT_MODALITY_THRESHOLD
    RETRIEVAL_FLOOR: float = DEFAULT_RETRIEVAL_FLOOR
    PROJECTION_REJECT_THRESHOLD: float = DEFAULT_PROJECTION_REJECT_THRESHOLD
    DISCLAIMER_AGREEMENT_THRESHOLD: float = DEFAULT_DISCLAIMER_AGREEMENT_THRESHOLD
    ACCEPTED_PROJECTIONS: str = DEFAULT_ACCEPTED_PROJECTIONS
    DECLARED_PROJECTION_VALUES: str = DEFAULT_DECLARED_PROJECTION_VALUES

    @property
    def accepted_projections(self) -> tuple[str, ...]:
        """DR-4's accepted set: the projections the pipeline will report on."""
        return tuple(p.strip().upper() for p in self.ACCEPTED_PROJECTIONS.split(",") if p.strip())

    @property
    def declared_projection_values(self) -> tuple[str, ...]:
        """A14's permitted DECLARED values -- a superset of the accepted
        set. LATERAL is a permitted thing to declare and a rejected thing
        to submit; that distinction is what gives A16 its own reason code
        instead of collapsing into "not declared"."""
        return tuple(
            p.strip().upper() for p in self.DECLARED_PROJECTION_VALUES.split(",") if p.strip()
        )

    @property
    def modality_prompts_positive(self) -> tuple[str, ...]:
        """§6 M3's prompt set, positive half -- the prompts that mean "this
        IS a chest radiograph". Pipe-separated in the raw setting because
        the prompts themselves contain spaces and commas are the more
        likely character to appear inside a future prompt."""
        return tuple(p.strip() for p in self.MODALITY_PROMPTS_POSITIVE.split("|") if p.strip())

    @property
    def modality_prompts_negative(self) -> tuple[str, ...]:
        return tuple(p.strip() for p in self.MODALITY_PROMPTS_NEGATIVE.split("|") if p.strip())

    @property
    def upload_allowed_extensions(self) -> tuple[str, ...]:
        """§5.1 A1's extension allow-list, normalized to lowercase and
        dot-prefixed exactly once regardless of how it was written in the
        setting or the environment."""
        return tuple(
            "." + e.strip().lower().lstrip(".")
            for e in self.UPLOAD_ALLOWED_EXTENSIONS.split(",")
            if e.strip()
        )


settings = Settings()
