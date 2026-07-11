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
# SQLite for now (Step 9 scope) -- Postgres is a deployment decision for later.
DEFAULT_DATABASE_URL = f"sqlite:///{_BACKEND_DIR / 'dev.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = DEFAULT_DATABASE_URL
    CHROMA_PERSIST_PATH: str = DEFAULT_CHROMA_PERSIST_PATH
    CHROMA_COLLECTION_NAME: str = DEFAULT_CHROMA_COLLECTION_NAME


settings = Settings()
