"""
Unit tests for the request OllamaClient actually sends.

These exist because of a QA report -- "uploading the exact same image yields
different outcomes across attempts" -- whose cause was reproduced at this
layer: with temperature=0.0 and Ollama's default (random) seed, five identical
requests to llama3:8b returned TWO distinct reports, diverging inside the
IMPRESSION section. Temperature 0 picks the highest-probability token; it does
not pin the sampler's starting state.

The fix is one key in an options dict, which is exactly the kind of thing that
gets dropped by a later refactor without anyone noticing -- the system would
still work, just stop being reproducible, silently. So the options payload is
asserted directly rather than trusted.

No network: httpx.post is monkeypatched, because the assertion is about what
this adapter SENDS, not about what Ollama answers.
"""
from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.infrastructure.ollama_client import OllamaClient
from app.services.exceptions import LLMTransportError


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def captured(monkeypatch):
    """Capture the JSON body of the single outbound request."""
    box: dict = {}

    def fake_post(url, json=None, timeout=None):
        box["url"] = url
        box["json"] = json
        box["timeout"] = timeout
        return _FakeResponse({"response": "drafted text"})

    monkeypatch.setattr(httpx, "post", fake_post)
    return box


def test_request_pins_both_temperature_and_seed(captured):
    """Both, not either. Temperature alone was measured to be insufficient."""
    result = OllamaClient().complete("a prompt")

    assert result == "drafted text"
    options = captured["json"]["options"]
    assert options["temperature"] == settings.LLM_TEMPERATURE
    assert options["seed"] == settings.LLM_SEED, (
        "seed missing from the Ollama options -- generation is no longer "
        "reproducible; see DEFAULT_LLM_SEED in app/core/config.py"
    )


def test_seed_and_temperature_come_from_settings_not_hardcoded(captured):
    """Same config-is-the-only-source-of-truth rule every other adapter follows:
    a caller overriding them must actually change the outbound request."""
    OllamaClient(temperature=0.7, seed=1234).complete("a prompt")

    assert captured["json"]["options"] == {"temperature": 0.7, "seed": 1234}


def test_request_sends_keep_alive(captured):
    """Holds the model resident between requests. A cold model was measured to
    produce different wording than a warm one even with the seed pinned, so
    dropping this reintroduces the reported symptom on any idle gap."""
    OllamaClient().complete("a prompt")

    assert captured["json"]["keep_alive"] == settings.OLLAMA_KEEP_ALIVE


def test_identical_prompts_produce_identical_request_bodies(captured):
    """The reproducibility property stated as a property: same input in, same
    request out. A future change that folded a timestamp, uuid or counter into
    the payload would break generation reproducibility and fail here."""
    client = OllamaClient()

    client.complete("the same prompt")
    first = captured["json"]
    client.complete("the same prompt")
    second = captured["json"]

    assert first == second


def test_transport_failure_is_still_wrapped(monkeypatch):
    """Guards the seed change against altering the existing error contract."""

    def fake_post(url, json=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(LLMTransportError):
        OllamaClient().complete("a prompt")
