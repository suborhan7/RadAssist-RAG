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

    def get_by_ids(self, uids: list[str]) -> list[RetrievedCase]:
        """Phase 8: ID-based fetch (collection.get()), not a similarity search --
        reconstructs full case content (findings/impression/labels) for a
        session's stored study_uids, since retrieved_evidence (Phase 4) only
        persists study_uid/rank/similarity, not the full case content.

        Reuses map_chroma_results (the exact same mapper query() already goes
        through) rather than a second, divergent mapping path: collection.get()'s
        flat result shape is wrapped into query()'s nested-per-query shape before
        calling it.

        No ranking is involved in a direct ID fetch, so there is no real
        similarity score to report. distance is forced to 0.0 for every result,
        which maps through map_chroma_results' existing (1 - distance) formula
        to similarity = 1.0. This was chosen over "reuse the original similarity
        from first retrieval" because get_by_ids has no access to that original
        query's distance -- it isn't threaded through this interface -- and 1.0
        reads honestly as "not a ranked result" rather than fabricating a
        plausible-looking but meaningless score.

        collection.get(ids=...) does NOT guarantee the returned order matches
        the input `uids` order (verified empirically against the real
        collection -- see Phase 8 Step 2 dev log entry). Results are explicitly
        reordered here to match the caller's requested order, since downstream
        code (re-voting, context building) assumes result order corresponds to
        what was asked for.

        A uid not found in the collection is silently dropped from the output,
        not raised as an error -- deliberate, because get_by_ids' expected
        caller (ReportGenerationService, Phase 8) only ever passes a session's
        own previously-persisted, already-known-valid study_uids read back out
        of retrieved_evidence; a miss here would mean the ChromaDB collection
        was mutated/rebuilt out from under an existing session, not a bad
        caller input worth failing loudly on. The practical consequence a
        future caller must know: the returned list can be SHORTER than `uids`
        if any id no longer exists, so callers must not assume
        len(result) == len(uids).
        """
        if not uids:
            return []

        raw_get_result = self._collection.get(ids=uids, include=["metadatas"])
        wrapped = {
            "ids": [raw_get_result["ids"]],
            "distances": [[0.0] * len(raw_get_result["ids"])],
            "metadatas": [raw_get_result["metadatas"]],
        }
        cases_by_uid = {case.source_uid: case for case in map_chroma_results(wrapped)}
        # silently drop any requested uid absent from the collection -- see
        # docstring above for why this is a deliberate non-error, not an oversight
        return [cases_by_uid[uid] for uid in uids if uid in cases_by_uid]
