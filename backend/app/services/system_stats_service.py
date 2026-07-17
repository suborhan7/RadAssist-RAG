"""
app/services/system_stats_service.py
====================================================================
Implements the Phase 16 Settings/System use case (design_specification.md
§8.16's "storage & privacy" + index-stats section).

masked_images_stored is a real directory count (settings.UPLOADED_IMAGES_DIR
-- one masked file persisted per real POST /retrieve call since Phase 12
Step 7). index_size is a real chromadb collection.count() via the
already-injected IVectorStore, not a re-derivation of it.

original_images_stored is NOT a query -- it is a structural constant.
Confirmed by reading app/api/retrieval.py before writing this: POST
/retrieve is the only file-upload endpoint anywhere in this backend, and
the raw upload only ever exists as a tempfile.NamedTemporaryFile,
synchronously deleted in _saved_upload's `finally` block before the
request even returns. There is no directory anywhere in this system that
could ever hold an original, unmasked image at rest, so this is always 0
by construction -- returning a literal 0 here is not a shortcut standing
in for a query that was skipped, it is the only correct answer a query
against a real directory would also produce, forever, given how this
system is built.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.domain.interfaces import IVectorStore


@dataclass(frozen=True)
class SystemStats:
    masked_images_stored: int
    original_images_stored: int
    index_size: int
    embedding_model: str
    embedding_version: str
    collection_name: str


class SystemStatsService:
    def __init__(self, vector_store: IVectorStore) -> None:
        self._vector_store = vector_store

    def get_stats(self) -> SystemStats:
        masked_dir = Path(settings.UPLOADED_IMAGES_DIR)
        masked_images_stored = (
            sum(1 for p in masked_dir.iterdir() if p.is_file()) if masked_dir.is_dir() else 0
        )

        return SystemStats(
            masked_images_stored=masked_images_stored,
            original_images_stored=0,  # structural constant -- see module docstring
            index_size=self._vector_store.count(),
            embedding_model=settings.CHROMA_EMBEDDING_MODEL,
            embedding_version=settings.CHROMA_EMBEDDING_VERSION,
            collection_name=settings.CHROMA_COLLECTION_NAME,
        )
