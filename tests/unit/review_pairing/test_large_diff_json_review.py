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

from omniintelligence.nodes.node_review_receipt_substitute_compute.handlers.handler_review_receipt_substitute import (
    FAILURE_TIMED_OUT,
    substitutable_failure,
)
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


async def test_an_exhausted_budget_is_a_substitutable_timeout() -> None:
    """A voter that runs out of its shared budget timed out (OMN-19998).

    Before chunking, a Studio call that ran past its timeout failed with the
    transport's timeout code, and the substitute-vote policy could replace it.
    The shared deadline must fail the same way, or a large review on a slow
    voter ends with no verdict and nothing may stand in for it.
    """

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
    assert substitutable_failure(result) == FAILURE_TIMED_OUT


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


async def test_slow_successful_primary_leaves_time_for_overflow_on_every_chunk() -> (
    None
):
    """A primary can answer each request yet starve the complete vote (OMN-19998)."""
    from omnibase_infra.enums import EnumInfraTransportType
    from omnibase_infra.errors import InfraTimeoutError, ModelTimeoutErrorContext

    from omniintelligence.review_pairing.models_external_review import (
        ModelEndpointConfig,
    )

    primary = "http://primary.example:8130"
    overflow = "http://overflow.example:8000"
    config = ModelEndpointConfig(
        env_var="TEST_SECURITY_REVIEW_URL",
        default_url=primary,
        kind="code_review",
        timeout_seconds=600.0,
        max_retries=0,
        api_model_id="test-reviewer",
        enable_thinking=False,
        overflow_urls=(overflow,),
    )
    clock = [0.0]
    calls = []

    class Handler:
        def __init__(self, transport: object) -> None:
            pass

        async def handle(self, request: object) -> SimpleNamespace:
            calls.append(request)
            duration = 450.0 if request.base_url == primary else 20.0
            clock[0] += min(duration, request.timeout_seconds)
            if duration > request.timeout_seconds:
                raise InfraTimeoutError(
                    "endpoint exceeded its request timeout",
                    context=ModelTimeoutErrorContext(
                        transport_type=EnumInfraTransportType.HTTP,
                        operation="llm_http_call",
                        timeout_seconds=request.timeout_seconds,
                    ),
                )
            return SimpleNamespace(generated_text="[]")

    diffs = [file_diff(f"part_{i}.py", 260) for i in range(4)]
    with (
        patch.dict(adapter.MODEL_REGISTRY, {"security-test": config}),
        patch.object(adapter, "time", SimpleNamespace(monotonic=lambda: clock[0])),
        patch(
            "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible",
            Handler,
        ),
    ):
        result = await adapter.async_parse_raw(
            "".join(diffs), model="security-test", review_type="pr"
        )

    assert result.success, result.error
    answered = [request for request in calls if request.base_url == overflow]
    assert len(answered) == 4
    for diff in diffs:
        assert sum(diff in request.messages[0]["content"] for request in answered) == 1
    assert clock[0] < 1200.0  # The original budget, not a larger timeout.
    assert adapter.SERVED_BASE_URLS["security-test"] == overflow
    adapter.SERVED_BASE_URLS.pop("security-test", None)


async def test_silent_endpoints_remain_a_timeout_with_a_subsecond_chunk_budget() -> (
    None
):
    """A small remaining share must time out, not fail request validation."""
    from omniintelligence.review_pairing.models_external_review import (
        ModelEndpointConfig,
    )

    config = ModelEndpointConfig(
        env_var="TEST_SECURITY_REVIEW_URL",
        default_url="http://primary.example:8130",
        kind="code_review",
        timeout_seconds=600.0,
        max_retries=0,
        api_model_id="test-reviewer",
        overflow_urls=("http://overflow.example:8000",),
    )
    cancelled = []

    class Handler:
        def __init__(self, transport: object) -> None:
            pass

        async def handle(self, request: object) -> None:
            try:
                await asyncio.Future()
            finally:
                cancelled.append(request.base_url)

    with (
        patch.dict(adapter.MODEL_REGISTRY, {"security-silent-test": config}),
        patch.object(
            adapter,
            "compute_sequential_worst_case",
            return_value=[SimpleNamespace(worst_case_seconds=0.8)],
        ),
        patch(
            "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible",
            Handler,
        ),
    ):
        result = await adapter.async_parse_raw(
            "".join(file_diff(f"part_{i}.py", 260) for i in range(4)),
            model="security-silent-test",
            review_type="pr",
        )

    assert not result.success
    assert substitutable_failure(result) == FAILURE_TIMED_OUT
    assert cancelled == [config.default_url, *config.overflow_urls]


async def test_chunk_overflow_through_the_production_http_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use real model discovery, signed HTTP requests and response parsing."""
    from aiohttp import web
    from omnibase_infra.adapters.llm.adapter_llm_provider_openai import (
        TransportHolderLlmHttp,
    )

    from omniintelligence.review_pairing.models_external_review import (
        ModelEndpointConfig,
    )

    monkeypatch.setenv("LOCAL_LLM_SHARED_SECRET", "synthetic-test-signing-key")
    monkeypatch.setenv("LLM_ENDPOINT_CIDR_ALLOWLIST", "127.0.0.1/32")
    monkeypatch.setattr(TransportHolderLlmHttp, "_LOCAL_LLM_CIDRS", None)
    calls: list[tuple[str, dict]] = []
    runners: list[web.AppRunner] = []

    async def start_endpoint(name: str, delay: float) -> str:
        async def models(request: web.Request) -> web.Response:
            return web.json_response({"data": [{"id": "test-reviewer"}]})

        async def review(request: web.Request) -> web.Response:
            assert request.headers.get("x-omn-node-signature")
            calls.append((name, await request.json()))
            await asyncio.sleep(delay)
            return web.json_response(
                {"choices": [{"message": {"content": "[]"}, "finish_reason": "stop"}]}
            )

        app = web.Application()
        app.router.add_get("/v1/models", models)
        app.router.add_post("/v1/chat/completions", review)
        runner = web.AppRunner(app)
        runners.append(runner)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", 0).start()
        return f"http://127.0.0.1:{runner.addresses[0][1]}"

    try:
        primary = await start_endpoint("primary", 1.4)
        overflow = await start_endpoint("overflow", 0.01)
        config = ModelEndpointConfig(
            env_var="TEST_HTTP_REVIEW_URL",
            default_url=primary,
            kind="code_review",
            timeout_seconds=2.0,
            max_retries=0,
            model_id_source="served",
            enable_thinking=False,
            overflow_urls=(overflow,),
            temperature=0.7,
            top_p=0.8,
            review_focus="Give extra scrutiny to security and contracts.",
        )
        monkeypatch.setitem(adapter.MODEL_REGISTRY, "security-http-test", config)
        diffs = [file_diff(f"part_{i}.py", 260) for i in range(4)]
        result = await asyncio.wait_for(
            adapter.async_parse_raw(
                "".join(diffs),
                model="security-http-test",
                review_type="pr",
                repository="example/review-target",
            ),
            timeout=6.0,
        )
        assert result.success, result.error
        answered = [body for name, body in calls if name == "overflow"]
        assert len(answered) == 4
        for diff in diffs:
            assert (
                sum(diff in body["messages"][-1]["content"] for body in answered) == 1
            )
        for body in answered:
            assert body["model"] == "test-reviewer"
            assert body["temperature"] == 0.7
            assert body["top_p"] == 0.8
            assert body["metadata"]["repository"] == "example/review-target"
            assert config.review_focus in body["messages"][0]["content"]
        assert adapter.SERVED_BASE_URLS["security-http-test"] == overflow
    finally:
        adapter.SERVED_BASE_URLS.pop("security-http-test", None)
        await asyncio.gather(*(runner.cleanup() for runner in runners))
