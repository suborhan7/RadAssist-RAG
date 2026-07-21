"""
Unit tests for ServiceHealthService (design_specification.md §16.1's
reopening -- real backend checks behind §8.2's four-service status
strip). Fakes IVectorStore the same way test_report_detail_service.py
already does; monkeypatches httpx.get for the Ollama check and
torch.cuda for the GPU check, since both are real external calls this
test must not actually make.
"""
from __future__ import annotations

import httpx
import pytest

from app.services.service_health_service import ServiceHealthService


class FakeVectorStore:
    def __init__(self, count_value=None, raises=False):
        self._count_value = count_value
        self._raises = raises

    def query(self, embedding, top_k):
        raise NotImplementedError

    def upsert(self, uid, embedding, metadata):
        raise NotImplementedError

    def get_by_ids(self, uids):
        raise NotImplementedError

    def count(self):
        if self._raises:
            raise RuntimeError("chroma unreachable")
        return self._count_value


class FakeHttpxResponse:
    def __init__(self, json_body, status_code=200):
        self._json_body = json_body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json_body


def test_fastapi_is_always_ok():
    service = ServiceHealthService(vector_store=FakeVectorStore(count_value=5))
    health = service.check_all()
    assert health.fastapi.status == "ok"


def test_chromadb_ok_reports_real_count(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeHttpxResponse({"models": []}))
    service = ServiceHealthService(vector_store=FakeVectorStore(count_value=5412))
    health = service.check_all()
    assert health.chromadb.status == "ok"
    assert health.chromadb.detail == "5,412"


def test_chromadb_unreachable_on_exception(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeHttpxResponse({"models": []}))
    service = ServiceHealthService(vector_store=FakeVectorStore(raises=True))
    health = service.check_all()
    assert health.chromadb.status == "unreachable"
    assert health.chromadb.detail is None


def test_ollama_ok_when_model_present(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: FakeHttpxResponse({"models": [{"name": settings.OLLAMA_MODEL}]})
    )
    service = ServiceHealthService(vector_store=FakeVectorStore(count_value=0))
    health = service.check_all()
    assert health.ollama.status == "ok"
    assert health.ollama.detail == settings.OLLAMA_MODEL


def test_ollama_degraded_when_model_not_pulled(monkeypatch):
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: FakeHttpxResponse({"models": [{"name": "some-other-model"}]})
    )
    service = ServiceHealthService(vector_store=FakeVectorStore(count_value=0))
    health = service.check_all()
    assert health.ollama.status == "degraded"


def test_ollama_unreachable_on_transport_error(monkeypatch):
    def raise_transport_error(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", raise_transport_error)
    service = ServiceHealthService(vector_store=FakeVectorStore(count_value=0))
    health = service.check_all()
    assert health.ollama.status == "unreachable"
    assert health.ollama.detail is None


def test_gpu_reports_not_available_honestly_when_no_cuda(monkeypatch):
    """Real rule this test enforces: never fabricate a GPU number in a
    CPU-only environment -- a real "not available" status, not a made-up
    number, per this project's standing "never invent data" discipline."""
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeHttpxResponse({"models": []}))
    service = ServiceHealthService(vector_store=FakeVectorStore(count_value=0))
    health = service.check_all()
    assert health.gpu.status == "degraded"
    assert health.gpu.detail == "not available"


def test_gpu_reports_real_usage_when_cuda_available(monkeypatch):
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(
        torch.cuda, "mem_get_info", lambda: (10 * 1024**3, 16 * 1024**3)  # 10GB free of 16GB
    )
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeHttpxResponse({"models": []}))
    service = ServiceHealthService(vector_store=FakeVectorStore(count_value=0))
    health = service.check_all()
    assert health.gpu.status == "ok"
    assert health.gpu.detail == "6.0/16.0GB"
