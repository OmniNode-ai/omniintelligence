# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Large reviews must return a complete, structured vote (OMN-20717).

large_free_text_reply.txt saves a live correctness-voter reply (15,779 chars
before the final newline), captured on 2026-10-16 while reviewing omnimarket#4002
through the production adapter.
It begins an array, falls into repeated analysis, and contains no complete JSON.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from omniintelligence.review_pairing.adapters import adapter_ai_reviewer as adapter

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]
PROSE = (
    Path(__file__)
    .with_name("fixtures")
    .joinpath("large_free_text_reply.txt")
    .read_text()
)
FINDING = {
    "category": "correctness",
    "severity": "major",
    "title": "Last row is lost",
    "description": "The loop omits the last row.",
    "evidence": "range(len(rows) - 1)",
    "proposed_fix": "Iterate over every row.",
    "location": "writer.py",
}


def file_diff(name: str, lines: int = 60) -> str:
    return (
        f"diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n"
        f"@@ -1 +1,{lines} @@\n-old\n"
        + "".join(f"+row_{i:04d} = process_record({i})\n" for i in range(lines))
    )


async def test_saved_long_prose_recovers_only_with_a_json_only_retry() -> None:
    assert 15_000 <= len(PROSE.encode()) <= 30_000
    assert adapter.try_parse_review_response(PROSE) is None

    async def endpoint(system: str, user: str, **kwargs: object) -> str:
        if kwargs.get("json_only") and "JSON ONLY" in system and '"required"' in system:
            return json.dumps([FINDING])
        return PROSE

    call = AsyncMock(side_effect=endpoint)
    with patch.object(adapter, "call_model", call):
        result = await adapter.async_parse_raw(file_diff("writer.py"), review_type="pr")
    assert result.success, result.error
    assert result.result_count == 1
    assert call.await_count == 2
    first, retry = call.await_args_list
    assert first.args[1] == retry.args[1]  # Original evidence is reviewed again.
    assert retry.kwargs["max_tokens"] > first.kwargs.get("max_tokens", 4096)


async def test_larger_diff_receives_more_output_tokens() -> None:
    config = adapter.MODEL_REGISTRY["qwen3-review"].model_copy(
        update={"context_window_tokens": 131072}
    )
    call = AsyncMock(return_value="[]")
    with (
        patch.dict(adapter.MODEL_REGISTRY, {"qwen3-review": config}),
        patch.object(adapter, "call_model", call),
    ):
        await adapter.async_parse_raw(file_diff("small.py", 1), review_type="pr")
        await adapter.async_parse_raw(file_diff("large.py", 800), review_type="pr")
    small, large = call.await_args_list
    assert large.kwargs["max_tokens"] > small.kwargs.get("max_tokens", 4096)


async def test_over_context_diff_reviews_every_file_and_merges_findings() -> None:
    diffs = [file_diff(f"part_{i}.py", 80) for i in range(14)]
    call = AsyncMock(return_value=json.dumps([FINDING]))
    with patch.object(adapter, "call_model", call):
        result = await adapter.async_parse_raw("".join(diffs), review_type="pr")
    assert result.success, result.error
    assert call.await_count > 1
    # Identical findings from adjacent batches are not repeated.
    assert result.result_count == 1
    users = [args.args[1] for args in call.await_args_list]
    for diff in diffs:
        assert sum(diff in user for user in users) == 1
    for args in call.await_args_list:
        system, user = args.args
        # Include the retry prompt and its reserved output in the context bound.
        retry_system = system + adapter._JSON_ONLY_RETRY
        retry_budget = min(16384, 2 * args.kwargs.get("max_tokens", 4096))
        assert len((retry_system + user).encode()) + retry_budget + 1024 <= 32768


async def test_one_failed_chunk_fails_the_entire_voter() -> None:
    call = AsyncMock(side_effect=[json.dumps([FINDING]), PROSE, PROSE])
    with patch.object(adapter, "call_model", call):
        result = await adapter.async_parse_raw(
            file_diff("one.py", 300) + file_diff("two.py", 300), review_type="pr"
        )
    assert not result.success
    assert result.parse_failed
    assert result.error and "chunk 2/" in result.error
    assert result.raw_reply_length == len(PROSE)


@pytest.mark.parametrize(
    "reply",
    [
        "{}",
        "[{}]",
        '["no review"]',
        "[null]",
        "I considered [] but have not finished the review.",
    ],
)
async def test_json_without_a_review_is_still_a_failed_vote(reply: str) -> None:
    call = AsyncMock(return_value=reply)
    with patch.object(adapter, "call_model", call):
        result = await adapter.async_parse_raw("a change")
    assert not result.success
    assert result.parse_failed
    assert call.await_count == 2


async def test_chunks_share_the_voters_existing_total_wall_clock_budget() -> None:
    async def slow_model(*args: object, **kwargs: object) -> str:
        await asyncio.sleep(0.05)
        return "[]"

    with (
        patch.object(adapter, "call_model", AsyncMock(side_effect=slow_model)),
        patch.object(
            adapter,
            "compute_sequential_worst_case",
            return_value=[SimpleNamespace(worst_case_seconds=0.001)],
            create=True,
        ),
    ):
        result = await adapter.async_parse_raw(file_diff("slow.py"), review_type="pr")
    assert not result.success
    assert result.error and "review budget exhausted" in result.error


async def test_a_single_oversized_file_keeps_every_changed_line_and_path() -> None:
    diff = file_diff("huge.py", 1800)
    call = AsyncMock(return_value="[]")
    with patch.object(adapter, "call_model", call):
        result = await adapter.async_parse_raw(diff, review_type="pr")
    assert result.success, result.error
    assert call.await_count > 1
    users = [args.args[1] for args in call.await_args_list]
    assert all("diff --git a/huge.py b/huge.py" in user for user in users)
    for line in diff.splitlines()[5:]:
        assert sum(line + "\n" in user for user in users) == 1


async def test_json_only_retry_disables_reasoning_and_keeps_supported_schema() -> None:
    from omniintelligence.review_pairing.models_external_review import (
        ModelEndpointConfig,
    )

    config = ModelEndpointConfig(
        env_var="TEST_REVIEW_URL",
        default_url="http://test.invalid:1",
        kind="code_review",
        timeout_seconds=120,
        api_model_id="test-model",
        enable_thinking=True,
        constrain_findings_schema=True,
        reasoning_effort="high",
    )
    handler = AsyncMock()
    handler.handle.return_value = AsyncMock(generated_text="[]")
    with (
        patch.dict(adapter.MODEL_REGISTRY, {"test-review": config}),
        patch(
            "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible",
            return_value=handler,
        ),
    ):
        await adapter.call_model(
            "system", "user", model_key="test-review", json_only=True
        )
    body = handler.handle.call_args.args[0].extra_body
    assert body["chat_template_kwargs"]["enable_thinking"] is False
    assert body["chat_template_kwargs"]["reasoning_effort"] == "low"
    assert body["response_format"] == adapter.FINDINGS_RESPONSE_FORMAT
