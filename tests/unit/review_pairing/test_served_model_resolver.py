# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for runtime served-model resolution (OMN-18623).

The resolver replaces a hardcoded model id with a read of the endpoint's own
``/v1/models``. That makes it the new single point of failure for every local
review leg, so every refusal path is pinned here: an endpoint that cannot be
resolved must RAISE with a legible reason rather than return a guess, because a
guess is precisely the failure mode the ticket removes.
"""

from __future__ import annotations

import io
import json
import urllib.error
from collections.abc import Iterator
from typing import Any

import pytest

from omniintelligence.review_pairing import served_model_resolver
from omniintelligence.review_pairing.served_model_resolver import (
    ServedModelResolutionError,
    clear_cache,
    resolve_served_model_id,
)


@pytest.fixture(autouse=True)
def _clean_cache() -> Iterator[None]:
    """Resolution is process-cached; isolate every test from its neighbours."""
    clear_cache()
    yield
    clear_cache()


class _FakeResponse(io.BytesIO):
    """Minimal stand-in for the urlopen context manager."""

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _payload(*ids: str) -> bytes:
    return json.dumps({"object": "list", "data": [{"id": i} for i in ids]}).encode()


def _patch_urlopen(monkeypatch: pytest.MonkeyPatch, result: Any) -> list[str]:
    """Patch urlopen; return the list that records each URL requested."""
    seen: list[str] = []

    def fake_urlopen(request: Any, timeout: float = 0.0) -> Any:
        seen.append(request.full_url)
        if isinstance(result, Exception):
            raise result
        return _FakeResponse(result)

    monkeypatch.setattr(served_model_resolver.urllib.request, "urlopen", fake_urlopen)
    return seen


def test_resolves_the_single_served_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """The happy path: one model on the port, that id is returned."""
    seen = _patch_urlopen(monkeypatch, _payload("Qwen3.8-27B"))
    assert resolve_served_model_id("http://host.invalid:8000") == "Qwen3.8-27B"
    assert seen == ["http://host.invalid:8000/v1/models"]


def test_probes_the_same_host_the_review_will_post_to(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The probe target is derived from the caller's base_url, never a constant.

    This is the property that makes the answer trustworthy rather than merely
    fresh: the id cannot be resolved from one endpoint and sent to another.
    """
    seen = _patch_urlopen(monkeypatch, _payload("some-model"))
    resolve_served_model_id("http://other.invalid:9001/")
    assert seen == ["http://other.invalid:9001/v1/models"]


def test_complete_chat_completions_url_resolves_its_sibling_models_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A registry entry may carry a COMPLETE chat-completions URL (cloud shape)."""
    seen = _patch_urlopen(monkeypatch, _payload("m"))
    resolve_served_model_id("https://api.invalid/api/coding/paas/v4/chat/completions")
    assert seen == ["https://api.invalid/api/coding/paas/v4/models"]


def test_unreachable_endpoint_raises_rather_than_guessing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_urlopen(monkeypatch, urllib.error.URLError("connection refused"))
    with pytest.raises(ServedModelResolutionError) as excinfo:
        resolve_served_model_id("http://host.invalid:8000")
    assert "could not read the served model id" in str(excinfo.value)
    assert "http://host.invalid:8000/v1/models" in str(excinfo.value)


def test_zero_models_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty inventory is not 'no opinion'; it is an unusable endpoint."""
    _patch_urlopen(monkeypatch, _payload())
    with pytest.raises(ServedModelResolutionError) as excinfo:
        resolve_served_model_id("http://host.invalid:8000")
    assert "serves 0 models" in str(excinfo.value)


def test_multiple_models_raises_and_says_what_to_do(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Several models breaks the one-model-per-port premise, so refuse.

    Silently taking the first would reintroduce a guess through a different
    door, and the order of that list is not a contract.
    """
    _patch_urlopen(monkeypatch, _payload("model-a", "model-b"))
    with pytest.raises(ServedModelResolutionError) as excinfo:
        resolve_served_model_id("http://host.invalid:8000")
    message = str(excinfo.value)
    assert "serves 2 models" in message
    assert "model_id_source: declared" in message


def test_non_json_response_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_urlopen(monkeypatch, b"<html>502 Bad Gateway</html>")
    with pytest.raises(ServedModelResolutionError) as excinfo:
        resolve_served_model_id("http://host.invalid:8000")
    assert "did not return JSON model metadata" in str(excinfo.value)


def test_json_without_a_data_list_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_urlopen(monkeypatch, json.dumps({"object": "list"}).encode())
    with pytest.raises(ServedModelResolutionError) as excinfo:
        resolve_served_model_id("http://host.invalid:8000")
    assert "no 'data' list" in str(excinfo.value)


def test_entries_without_a_usable_id_are_not_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed entry must not be mistaken for a served model."""
    raw = json.dumps({"data": [{"id": ""}, {"nope": 1}, {"id": "real-model"}]}).encode()
    _patch_urlopen(monkeypatch, raw)
    assert resolve_served_model_id("http://host.invalid:8000") == "real-model"


def test_empty_base_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ServedModelResolutionError):
        resolve_served_model_id("")


def test_result_is_cached_per_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """A roster calls one endpoint twice; it must cost one probe, not two."""
    seen = _patch_urlopen(monkeypatch, _payload("Qwen3.8-27B"))
    assert resolve_served_model_id("http://host.invalid:8000") == "Qwen3.8-27B"
    assert resolve_served_model_id("http://host.invalid:8000") == "Qwen3.8-27B"
    assert len(seen) == 1


def test_cache_can_be_bypassed(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_urlopen(monkeypatch, _payload("Qwen3.8-27B"))
    resolve_served_model_id("http://host.invalid:8000", use_cache=False)
    resolve_served_model_id("http://host.invalid:8000", use_cache=False)
    assert len(seen) == 2


def test_a_failure_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """A transient outage must not poison the rest of the process.

    Caching a failure would turn one flaky probe into a whole run's worth of
    dead review legs.
    """
    _patch_urlopen(monkeypatch, urllib.error.URLError("boom"))
    with pytest.raises(ServedModelResolutionError):
        resolve_served_model_id("http://host.invalid:8000")

    seen = _patch_urlopen(monkeypatch, _payload("Qwen3.8-27B"))
    assert resolve_served_model_id("http://host.invalid:8000") == "Qwen3.8-27B"
    assert len(seen) == 1


def test_adapter_sends_the_resolved_id_for_a_served_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End of the wire: the value the request carries is the resolved one.

    The registry no longer holds a model id, so a test that only checked the
    resolver would leave the actual substitution unproven. This pins the
    adapter helper that decides what goes in the ``model`` field.
    """
    from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
        MODEL_REGISTRY,
        _resolve_api_model_id,
    )

    _patch_urlopen(monkeypatch, _payload("whatever-is-served-today"))
    config = MODEL_REGISTRY["qwen3-review"]
    assert config.api_model_id == ""

    resolved = _resolve_api_model_id("qwen3-review", config, config.default_url)
    assert resolved == "whatever-is-served-today"


def test_adapter_sends_the_declared_id_for_a_declared_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A declared entry must not probe anything: the cloud path is unchanged."""
    from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
        MODEL_REGISTRY,
        _resolve_api_model_id,
    )

    seen = _patch_urlopen(monkeypatch, _payload("should-not-be-read"))
    config = MODEL_REGISTRY["glm-review"]
    resolved = _resolve_api_model_id("glm-review", config, config.default_url)
    assert resolved == "glm-5.3-flash"
    assert seen == [], "a declared entry must not probe /v1/models"
