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
    CORS_ALLOWED_ORIGINS: str = DEFAULT_CORS_ALLOWED_ORIGINS
    UPLOADED_IMAGES_DIR: str = DEFAULT_UPLOADED_IMAGES_DIR


settings = Settings()
