# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""A chunked review's deadline scales with its chunk count (OMN-20910).

Measured 2026-10-18 on omnimarket's Hostile Reviewer: the correctness voter
(timeout 120 s, 3 retries) had one call's worst case, about 494 s, for the
WHOLE review, shared by every chunk. A chunk takes 43-75 s on that endpoint,
so a diff split into more than about 8-16 chunks always ran out of time
(omnimarket#4070: 65 chunks, budget exhausted after chunk 16) and the gate
degraded with no finding. A voter may now declare review_deadline_seconds:
a chunked review gets timeout_seconds per chunk, never less than one call's
worst case and never more than that ceiling. A review that still runs past
it is a timeout, and the gate fails closed as before.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from omniintelligence.nodes.node_review_receipt_substitute_compute.handlers.handler_review_receipt_substitute import (
    FAILURE_TIMED_OUT,
    substitutable_failure,
)
from omniintelligence.review_pairing.adapters import adapter_ai_reviewer as adapter
from omniintelligence.review_pairing.model_registry_loader import load_review_voters
from omniintelligence.review_pairing.models_external_review import (
    ModelEndpointConfig,
)
from omniintelligence.review_pairing.retry_budget import (
    assert_budget_within_ceiling,
    compute_sequential_worst_case,
)

pytestmark = [pytest.mark.unit]

_CHUNKS = 24


def _file_diff(name: str, lines: int = 200) -> str:
    return (
        f"diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n"
        f"@@ -1 +1,{lines} @@\n-old\n"
        + "".join(f"+row_{i:04d} = process_record({i})\n" for i in range(lines))
    )


def _many_chunk_diff() -> str:
    return "".join(_file_diff(f"part_{i:02d}.py") for i in range(_CHUNKS))


def _correctness_config(**overrides: object) -> ModelEndpointConfig:
    # The correctness voter's shape in the CI overlay: 120 s, default retries.
    fields: dict[str, object] = {
        "env_var": "",
        "default_url": "http://correctness.example:8000",
        "kind": "code_review",
        "timeout_seconds": 120.0,
        "api_model_id": "test-reviewer",
        "enable_thinking": False,
    }
    fields.update(overrides)
    return ModelEndpointConfig.model_validate(fields)


async def _review(config: ModelEndpointConfig, seconds_per_chunk: float) -> tuple:
    clock = [0.0]

    async def model(*args: object, **kwargs: object) -> str:
        clock[0] += seconds_per_chunk
        return "[]"

    call = AsyncMock(side_effect=model)
    with (
        patch.dict(adapter.MODEL_REGISTRY, {"correctness-test": config}),
        patch.object(adapter, "call_model", call),
        patch.object(adapter, "time", SimpleNamespace(monotonic=lambda: clock[0])),
    ):
        result = await adapter.async_parse_raw(
            _many_chunk_diff(), model="correctness-test", review_type="pr"
        )
    return result, call.await_count, clock[0]


def test_the_fixture_diff_is_reviewed_in_many_chunks() -> None:
    config = _correctness_config()
    budget = config.context_window_tokens - 2 * adapter._MAX_REVIEW_TOKENS - 8192
    assert len(adapter._review_chunks(_many_chunk_diff(), budget)) >= _CHUNKS


@pytest.mark.asyncio
async def test_a_many_chunk_review_finishes_within_its_chunk_scaled_deadline() -> None:
    """24 chunks at 60 s each: 1440 s, past one call's 494 s worst case."""
    result, calls, elapsed = await _review(
        _correctness_config(review_deadline_seconds=3000.0), 60.0
    )
    assert result.success, result.error
    assert calls == _CHUNKS
    assert elapsed == pytest.approx(_CHUNKS * 60.0)


@pytest.mark.asyncio
async def test_without_a_ceiling_the_deadline_is_one_calls_worst_case() -> None:
    """No review_deadline_seconds keeps the earlier budget: 494 s in all."""
    result, calls, elapsed = await _review(_correctness_config(), 60.0)
    assert not result.success
    assert result.error and "review budget exhausted" in result.error
    assert calls < 10
    assert elapsed < 494.0 + 60.0


@pytest.mark.asyncio
async def test_the_deadline_is_timeout_per_chunk_not_the_ceiling() -> None:
    """24 x 120 s = 2880 s, below the 3000 s ceiling: 130 s chunks run out."""
    result, calls, elapsed = await _review(
        _correctness_config(review_deadline_seconds=3000.0), 130.0
    )
    assert not result.success
    assert result.error and "review budget exhausted" in result.error
    assert calls < _CHUNKS
    assert elapsed < 2880.0 + 130.0


@pytest.mark.asyncio
async def test_the_ceiling_bounds_the_deadline_and_fails_closed_as_a_timeout() -> None:
    """A ceiling of 1000 s stops 24 x 60 s; the vote is a substitutable timeout."""
    result, calls, elapsed = await _review(
        _correctness_config(review_deadline_seconds=1000.0), 60.0
    )
    assert not result.success
    assert result.error and "review budget exhausted" in result.error
    assert substitutable_failure(result) == FAILURE_TIMED_OUT
    assert calls <= 17
    assert elapsed < 1000.0 + 60.0


def test_the_budget_check_counts_the_ceiling_for_any_chunk_count() -> None:
    config = _correctness_config(review_deadline_seconds=1800.0)
    [job] = compute_sequential_worst_case(["c"], configs={"c": config})
    assert job.worst_case_seconds == 1800.0
    assert job.review_deadline_seconds == 1800.0
    [one] = compute_sequential_worst_case(["c"], configs={"c": config}, chunk_count=1)
    assert one.worst_case_seconds == pytest.approx(494.0)
    [many] = compute_sequential_worst_case(
        ["c"], configs={"c": config}, chunk_count=_CHUNKS
    )
    assert many.worst_case_seconds == 1800.0
    [some] = compute_sequential_worst_case(["c"], configs={"c": config}, chunk_count=6)
    assert some.worst_case_seconds == 720.0


def test_the_budget_check_refuses_ceilings_past_the_job_timeout() -> None:
    configs = {
        "a": _correctness_config(review_deadline_seconds=1800.0),
        "b": _correctness_config(review_deadline_seconds=1200.0),
    }
    assert_budget_within_ceiling(
        ["a", "b"],
        job_timeout_seconds=3600.0,
        setup_overhead_seconds=300.0,
        configs=configs,
    )
    configs["b"] = _correctness_config(review_deadline_seconds=1800.0)
    with pytest.raises(AssertionError, match="Retry-budget invariant violated"):
        assert_budget_within_ceiling(
            ["a", "b"],
            job_timeout_seconds=3600.0,
            setup_overhead_seconds=300.0,
            configs=configs,
        )


def _overlay(tmp_path: Path, deadline: str) -> Path:
    path = tmp_path / "overlay.yaml"
    path.write_text(
        textwrap.dedent(
            f"""\
            schema_version: "review_voters_overlay.v1"
            voters:
              - voter_id: correctness
                endpoint_url: "http://correctness.example:8000/v1/chat/completions"
                required: true
                timeout_seconds: 120
                {deadline}
            """
        )
    )
    return path


def test_the_overlay_carries_the_ceiling_to_the_adapter(tmp_path: Path) -> None:
    roster = load_review_voters(_overlay(tmp_path, "review_deadline_seconds: 1800"))
    assert roster.ok, roster.error_message
    assert roster.endpoint_configs()["correctness"].review_deadline_seconds == 1800.0
    assert "review_deadline=1800s" in roster.voters[0].describe()


def test_the_overlay_refuses_a_ceiling_below_one_timeout(tmp_path: Path) -> None:
    roster = load_review_voters(_overlay(tmp_path, "review_deadline_seconds: 60"))
    assert not roster.ok
    assert "correctness" in (roster.error_message or "")
