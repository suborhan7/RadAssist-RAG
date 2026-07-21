"""
app/services/service_health_service.py
====================================================================
Implements the real backend half of design_specification.md §8.2's
four-service status strip (FastAPI/Ollama/ChromaDB/GPU), per §16.1's
reopening note -- GET /health's own long-standing comment already named
this exact gap ("no DB/Chroma reachability check (a documented future
improvement, not required now)"). Each check is a real, independent
probe; a failure in one never raises, it degrades that row's own status
so the other three still report accurately.

ChromaDB: reuses IVectorStore.count() exactly as SystemStatsService
(Phase 16) already does -- not a second implementation of "ask Chroma
how big the collection is."

Ollama: a real GET {OLLAMA_BASE_URL}/api/tags via httpx, matching the
transport client already used for real generation calls
(app/infrastructure/ollama_client.py) rather than reaching for a
different HTTP library. A short, dedicated timeout (this is a liveness
probe, not a generation call -- OLLAMA_TIMEOUT_SECONDS's 120s default
would make a cold/unreachable Ollama block this endpoint for two
minutes, defeating the whole point of a status strip).

GPU: real torch.cuda.is_available()/mem_get_info() -- imported lazily
inside the method, matching shared/embeddings/biomedclip_embedder.py's
own established convention (torch is a heavy import; this module must
stay importable in torch-less environments). Reports a real "not
available" status rather than fabricating a number when no CUDA device
exists -- this system's standing rule against inventing data applies to
infrastructure status exactly as it does to clinical content.

Real bug found and fixed during this same phase's verification, not
theoretical: httpx.get() to a "localhost" URL took ~2.2s on this
environment (confirmed via direct timing) vs. ~0.1s to the equivalent
"127.0.0.1" URL -- a real IPv6-then-IPv4-fallback resolution tax specific
to httpx on this machine (curl to the same "localhost" URL was fast,
ruling out Ollama itself being slow). Scoped fix: this health check
specifically resolves via 127.0.0.1, not a change to the shared
OLLAMA_BASE_URL setting or OllamaClient (used by real generation calls
elsewhere) -- that setting likely pays the same tax, but changing it is
a separate, bigger decision outside a health-check's scope.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.domain.interfaces import IVectorStore

HEALTH_CHECK_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class ServiceStatus:
    status: str  # "ok" | "degraded" | "unreachable"
    detail: str | None = None


@dataclass(frozen=True)
class ServiceHealth:
    fastapi: ServiceStatus
    ollama: ServiceStatus
    chromadb: ServiceStatus
    gpu: ServiceStatus


class ServiceHealthService:
    def __init__(self, vector_store: IVectorStore) -> None:
        self._vector_store = vector_store

    def check_all(self) -> ServiceHealth:
        return ServiceHealth(
            # If this code is executing, FastAPI itself is up -- the one
            # check with no real failure mode to probe for.
            fastapi=ServiceStatus(status="ok"),
            ollama=self._check_ollama(),
            chromadb=self._check_chromadb(),
            gpu=self._check_gpu(),
        )

    def _check_ollama(self) -> ServiceStatus:
        # "localhost" -> "127.0.0.1": see this module's own docstring --
        # a real, confirmed ~2s httpx-specific resolution tax on this
        # environment, not present when connecting via the literal IPv4
        # loopback address.
        base_url = settings.OLLAMA_BASE_URL.replace("localhost", "127.0.0.1")
        try:
            response = httpx.get(f"{base_url}/api/tags", timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
            response.raise_for_status()
        except httpx.HTTPError:
            return ServiceStatus(status="unreachable")

        models = [m.get("name", "") for m in response.json().get("models", [])]
        if any(settings.OLLAMA_MODEL in name for name in models):
            return ServiceStatus(status="ok", detail=settings.OLLAMA_MODEL)
        return ServiceStatus(
            status="degraded", detail=f"{settings.OLLAMA_MODEL} not pulled"
        )

    def _check_chromadb(self) -> ServiceStatus:
        try:
            count = self._vector_store.count()
        except Exception:
            return ServiceStatus(status="unreachable")
        return ServiceStatus(status="ok", detail=f"{count:,}")

    def _check_gpu(self) -> ServiceStatus:
        import torch

        if not torch.cuda.is_available():
            return ServiceStatus(status="degraded", detail="not available")

        free_bytes, total_bytes = torch.cuda.mem_get_info()
        used_gb = (total_bytes - free_bytes) / (1024**3)
        total_gb = total_bytes / (1024**3)
        return ServiceStatus(status="ok", detail=f"{used_gb:.1f}/{total_gb:.1f}GB")
