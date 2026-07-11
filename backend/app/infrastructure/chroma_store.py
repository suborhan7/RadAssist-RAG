"""
app/infrastructure/chroma_store.py
====================================================================
Implements IVectorStore. Wraps chromadb.PersistentClient pointed at the
collection built by ml/retrieval/build_chroma_index.py.
"""
from __future__ import annotations

from pathlib import Path

import chromadb

from app.domain.entities import RetrievedCase
from app.infrastructure.chroma_result_mapper import map_chroma_results

DEFAULT_COLLECTION_NAME = "iu_cxr_biomedclip_v1_train"

# Anchored to the repo root via this file's own location, not the process's
# CWD -- a bare relative string here previously meant the collection path
# silently depended on wherever the caller happened to launch from (caught
# during Step 1 verification: a stray `cd backend` produced an empty
# backend/ml/outputs/retrieval/chroma_db instead of erroring).
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PERSIST_PATH = str(_REPO_ROOT / "ml" / "outputs" / "retrieval" / "chroma_db")


class ChromaVectorStore:
    """Satisfies domain.interfaces.IVectorStore."""

    def __init__(
        self,
        persist_path: str = DEFAULT_PERSIST_PATH,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ) -> None:
        self._client = chromadb.PersistentClient(path=persist_path)
        self._collection_name = collection_name
        self._collection = self._client.get_collection(collection_name)

    def query(self, embedding: list[float], top_k: int) -> list[RetrievedCase]:
        raw_result = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["distances", "metadatas"],
        )
        return map_chroma_results(raw_result)

    def upsert(self, uid: str, embedding: list[float], metadata: dict) -> None:
        # Not used by the Phase 4 retrieval path (ml/retrieval/build_chroma_index.py
        # owns indexing) -- implemented for IVectorStore interface completeness.
        self._collection.upsert(ids=[uid], embeddings=[embedding], metadatas=[metadata])
