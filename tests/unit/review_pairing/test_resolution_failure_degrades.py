# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""An unresolvable endpoint must DEGRADE the reviewer, never hard-fail it.

OMN-18623 follow-up. Runtime model-id resolution (`model_id_source: served`)
introduced a new way for a review leg to fail: the endpoint answers the TCP
probe but cannot be resolved to exactly one served model. The reviewer's
outage behaviour is load-bearing for the whole fleet -- the Hostile Review Gate
is a required check in several repos -- so "it degrades" must be a pinned
property and not an inference from reading the call stack.

TWO DISTINCT PATHS, BOTH PINNED HERE
-------------------------------------
1. ENDPOINT DOWN (the pre-existing outage shape). ``select_models_with_fallback``
   TCP-probes local endpoints and drops the unreachable ones BEFORE any call is
   made, handing the review to the cloud reviewer / API fallback. Resolution
   never runs. This test file proves the OMN-18623 change did not perturb that
   path, because the change lives inside ``call_model`` and selection happens
   strictly before it.

2. ENDPOINT UP BUT UNRESOLVABLE (new with OMN-18623). The port is open, so the
   probe passes and the model is selected, but ``/v1/models`` is unreadable,
   unparseable, empty, or lists several models. The resolver refuses rather
   than guessing -- and that refusal must surface as an ordinary PER-MODEL
   failure that leaves the rest of the roster reviewing, exactly like the
   HTTP 404 it replaces.

The failure mode being excluded is a resolver exception escaping
``async_parse_raw`` and taking down the whole review, which would convert a
one-model problem into a fleet-wide gate outage -- strictly worse than the
defect OMN-18623 fixed.
"""

from __future__ import annotations

import pytest

from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.served_model_resolver import (
    ServedModelResolutionError,
)


@pytest.mark.asyncio
async def test_unresolvable_endpoint_returns_a_failed_result_not_an_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A resolution refusal degrades this one model; it does not raise."""

    def boom(*args: object, **kwargs: object) -> str:
        raise ServedModelResolutionError(
            "could not read the served model id from http://x:1/v1/models"
        )

    monkeypatch.setattr(
        adapter_ai_reviewer, "resolve_served_model_id", boom, raising=True
    )
    monkeypatch.setenv("LLM_QWEN3_REVIEW_URL", "http://x:1")
    monkeypatch.setenv("LOCAL_LLM_SHARED_SECRET", "x")  # pragma: allowlist secret

    result = await adapter_ai_reviewer.async_parse_raw(
        "some plan content", model="qwen3-review"
    )

    assert result.success is False, (
        "a resolution refusal must surface as a failed per-model result, not "
        "propagate out of async_parse_raw and abort the whole review."
    )
    assert result.model == "qwen3-review"
    assert not result.findings, (
        "a degraded leg must contribute no findings, so it cannot be mistaken "
        "for a clean review that simply found nothing."
    )
    assert result.error is not None
    assert "served model id" in result.error, (
        f"the failure must name its cause so the next lane is not left with a "
        f"generic error; got {result.error!r}"
    )


@pytest.mark.asyncio
async def test_one_unresolvable_model_leaves_the_roster_reviewing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The blast radius of a refusal is one model, not the run.

    This is the property that makes fail-closed resolution safe: the roster's
    quorum logic sees an ordinary per-model failure and the remaining models
    still produce a verdict.
    """
    calls: list[str] = []

    def selective(base_url: str, **kwargs: object) -> str:
        calls.append(base_url)
        raise ServedModelResolutionError("unresolvable")

    monkeypatch.setattr(
        adapter_ai_reviewer, "resolve_served_model_id", selective, raising=True
    )
    monkeypatch.setenv("LOCAL_LLM_SHARED_SECRET", "x")  # pragma: allowlist secret

    first = await adapter_ai_reviewer.async_parse_raw("plan", model="qwen3-review")
    second = await adapter_ai_reviewer.async_parse_raw("plan", model="qwen3-review-b")

    assert first.success is False
    assert second.success is False
    assert len(calls) == 2, (
        "each model must be attempted independently -- one refusal must not "
        "short-circuit the roster."
    )


def test_an_unreachable_endpoint_is_dropped_before_resolution_ever_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pre-existing outage path is untouched: probe first, fall back, no resolve.

    OMN-18623 changed what happens INSIDE call_model. Selection happens strictly
    before it, so a down endpoint still degrades to the API fallback with no
    resolution attempted. If this ever inverts, an outage would start producing
    resolution errors instead of a clean cloud-fallback review.
    """
    resolved: list[str] = []

    def tripwire(base_url: str, **kwargs: object) -> str:
        resolved.append(base_url)
        return "should-never-be-called"

    monkeypatch.setattr(
        adapter_ai_reviewer, "resolve_served_model_id", tripwire, raising=True
    )
    # Every local endpoint is down.
    monkeypatch.setattr(
        adapter_ai_reviewer, "_probe_tcp", lambda _host, _port: False, raising=True
    )

    to_run, skipped = adapter_ai_reviewer.select_models_with_fallback(
        ["qwen3-review", "qwen3-review-b"]
    )

    assert sorted(skipped) == ["qwen3-review", "qwen3-review-b"]
    assert to_run == list(adapter_ai_reviewer._API_FALLBACK_KEYS), (
        f"an all-local outage must degrade to the API fallback; got {to_run}"
    )
    assert resolved == [], (
        "selection must not resolve model ids -- an unreachable endpoint is "
        "dropped before call_model, so no /v1/models request should be made."
    )


def test_a_reachable_endpoint_is_still_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Positive control for the test above.

    Without it, a selection function that returned the fallback unconditionally
    would satisfy the outage assertion while being completely broken.
    """
    monkeypatch.setattr(
        adapter_ai_reviewer, "_probe_tcp", lambda _host, _port: True, raising=True
    )
    to_run, skipped = adapter_ai_reviewer.select_models_with_fallback(
        ["qwen3-review", "qwen3-review-b"]
    )
    assert to_run == ["qwen3-review", "qwen3-review-b"]
    assert skipped == []


def test_a_non_local_reviewer_is_unaffected_by_a_local_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cloud reviewer carries the gate when every local leg is down.

    glm-review is deliberately NOT in local_model_keys, so it passes through
    selection untouched. That independence is what makes "degrade, never
    hard-fail" true in practice rather than only in principle.
    """
    monkeypatch.setattr(
        adapter_ai_reviewer, "_probe_tcp", lambda _host, _port: False, raising=True
    )
    to_run, skipped = adapter_ai_reviewer.select_models_with_fallback(
        ["qwen3-review", "glm-review"]
    )
    assert "glm-review" in to_run
    assert skipped == ["qwen3-review"]
