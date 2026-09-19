"""
Phase 21 §4.1: evaluation_config.json must record the generation settings
ACTUALLY IN EFFECT.

This test exists because the thing it guards already failed once, silently.
`get_real_generation_settings()` hardcoded `"seed": "not set by this system"`,
which was true when written and became false at c39654a6 when LLM_SEED was
pinned to fix a measured reproducibility defect. Nothing caught it: a hardcoded
string cannot disagree with itself. The falsehood would have been written into a
Phase 21 config file and cited from there.

So the assertion is not "the function returns sensible values" -- it is "the
function agrees with Settings", which is the only property that can rot.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "ml" / "evaluation"))

from app.core.config import settings  # noqa: E402

run_generation_eval = pytest.importorskip(
    "run_generation_eval",
    reason="ml/evaluation harness not importable in this environment",
)


@pytest.fixture
def recorded(monkeypatch):
    """Ollama's /api/version is irrelevant here and must not make the test
    depend on a running inference server."""
    class _Boom:
        def __call__(self, *a, **k):
            raise run_generation_eval.requests.RequestException("offline")

    monkeypatch.setattr(run_generation_eval.requests, "get", _Boom())
    return run_generation_eval.get_real_generation_settings(settings.OLLAMA_BASE_URL)


@pytest.mark.parametrize(
    "key,expected_attr",
    [
        ("model", "OLLAMA_MODEL"),
        ("temperature", "LLM_TEMPERATURE"),
        ("seed", "LLM_SEED"),
        ("keep_alive", "OLLAMA_KEEP_ALIVE"),
        ("timeout_seconds", "OLLAMA_TIMEOUT_SECONDS"),
        ("content_retry_count", "LLM_CONTENT_RETRY_COUNT"),
        ("transport_retry_count", "LLM_TRANSPORT_RETRY_COUNT"),
    ],
)
def test_recorded_setting_matches_live_config(recorded, key, expected_attr):
    assert recorded[key] == getattr(settings, expected_attr), (
        f"evaluation_config.json would record {key}={recorded[key]!r} while "
        f"Settings.{expected_attr} is {getattr(settings, expected_attr)!r}. "
        "The harness has drifted from configuration."
    )


def test_pinned_parameters_are_not_reported_as_unset(recorded):
    """The specific regression that happened. seed and keep_alive ARE set."""
    for key in ("seed", "keep_alive"):
        assert "not set" not in str(recorded[key]), (
            f"{key} is pinned in config but the harness reports it as unset"
        )


def test_genuinely_unset_parameters_are_still_reported_as_unset(recorded):
    """The mirror image: do not let the fix overclaim. These three are not sent
    in ollama_client.py's request body and must not be presented as configured."""
    for key in ("top_p", "repeat_penalty", "max_tokens"):
        assert "not set" in str(recorded[key])


def test_unset_claims_match_the_adapter_payload():
    """Ground the 'not set' claims in the adapter's real outbound body rather
    than in a list someone maintains by hand."""
    source = (REPO_ROOT / "backend/app/infrastructure/ollama_client.py").read_text(encoding="utf-8")
    for absent in ("top_p", "repeat_penalty", "num_predict", "max_tokens"):
        assert f'"{absent}"' not in source, (
            f"{absent} now appears in the Ollama request body; "
            "get_real_generation_settings still reports it as unset"
        )
    for present in ("seed", "keep_alive", "temperature"):
        assert f'"{present}"' in source
