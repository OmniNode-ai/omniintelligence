# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Claude voter truncation uses the JSON-only review retry (OMN-20910)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import httpx
import pytest

from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    ClaudeReplyIncompleteError,
)
from omniintelligence.review_pairing.models_external_review import ModelEndpointConfig

_CALL_ENV_NAME = "OMN20910_MAX_TOKENS_TEST_ENV"
_TRUNCATED_REPLY = '[{"title": "x"'


def _config() -> ModelEndpointConfig:
    return ModelEndpointConfig(
        provider="anthropic",
        env_var="OMN20910_MAX_TOKENS_TEST_URL",
        kind="api_fallback",
        default_url="https://review-api.example",
        api_model_id="claude-sonnet-5-5",
        api_key_env=_CALL_ENV_NAME,
        timeout_seconds=5.0,
        max_retries=0,
        context_window_tokens=200000,
    )


def _message(
    stop_reason: str,
    text: str = _TRUNCATED_REPLY,
    *,
    input_tokens: int = 100,
    output_tokens: int = 7,
) -> dict[str, object]:
    return {
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "stop_reason": stop_reason,
        "model": "claude-sonnet-5-5",
    }


@pytest.fixture
def api(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[list[dict[str, object]]], list[httpx.Request]]:
    original = httpx.AsyncClient
    monkeypatch.setenv(_CALL_ENV_NAME, "placeholder-value")

    def install(bodies: list[dict[str, object]]) -> list[httpx.Request]:
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=bodies[len(requests) - 1])

        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs),
        )
        return requests

    return install


@pytest.fixture
def registered(monkeypatch: pytest.MonkeyPatch) -> str:
    key = "omn20910-max-tokens"
    monkeypatch.setitem(adapter_ai_reviewer.MODEL_REGISTRY, key, _config())
    return key


@pytest.mark.unit
class TestClaudeVoterMaxTokensRetry:
    def test_truncated_reply_retries_with_twice_the_output_budget(
        self,
        api: Callable[[list[dict[str, object]]], list[httpx.Request]],
        registered: str,
    ) -> None:
        requests = api([_message("max_tokens"), _message("end_turn", "[]")])
        result = asyncio.run(
            adapter_ai_reviewer.async_parse_raw("diff", model=registered)
        )

        assert result.success, result.error
        assert len(requests) == 2
        first, second = [json.loads(request.content) for request in requests]
        assert second["max_tokens"] == 2 * first["max_tokens"]
        assert (
            second["system"] == first["system"] + adapter_ai_reviewer._JSON_ONLY_RETRY
        )

    @pytest.mark.parametrize("chunk_count", [1, 2])
    def test_truncated_retry_fails_with_usage_and_reply_lengths(
        self,
        api: Callable[[list[dict[str, object]]], list[httpx.Request]],
        registered: str,
        monkeypatch: pytest.MonkeyPatch,
        chunk_count: int,
    ) -> None:
        monkeypatch.setattr(
            adapter_ai_reviewer, "_review_chunks", lambda *_args: ["diff"] * chunk_count
        )
        retry_text = '[{"title": "longer truncated reply"'
        requests = api(
            [_message("end_turn", "[]")] * (chunk_count - 1)
            + [
                _message("max_tokens"),
                _message("max_tokens", retry_text, input_tokens=200, output_tokens=11),
            ]
        )
        result = asyncio.run(
            adapter_ai_reviewer.async_parse_raw("diff", model=registered)
        )

        assert not result.success
        assert result.error is not None
        assert "unparseable reply" in result.error
        assert f"{len(_TRUNCATED_REPLY)}, {len(retry_text)}" in result.error
        assert result.parse_failed
        assert result.raw_reply_length == len(retry_text)
        assert result.input_tokens == 100 * chunk_count + 200
        assert result.output_tokens == 7 * chunk_count + 11
        assert len(requests) == chunk_count + 1
        if chunk_count > 1:
            assert result.error.startswith("chunk 2/2:")

    def test_refusal_fails_without_retry_and_names_the_stop_reason(
        self,
        api: Callable[[list[dict[str, object]]], list[httpx.Request]],
        registered: str,
    ) -> None:
        requests = api([_message("refusal")])
        result = asyncio.run(
            adapter_ai_reviewer.async_parse_raw("diff", model=registered)
        )

        assert not result.success
        assert result.error is not None
        assert "stop_reason=refusal" in result.error
        assert len(requests) == 1

    def test_call_model_still_raises_for_truncation(
        self,
        api: Callable[[list[dict[str, object]]], list[httpx.Request]],
        registered: str,
    ) -> None:
        requests = api([_message("max_tokens")])
        with pytest.raises(ClaudeReplyIncompleteError) as raised:
            asyncio.run(adapter_ai_reviewer.call_model("sys", "user", registered))

        assert raised.value.stop_reason == "max_tokens"
        assert raised.value.reply_length == len(_TRUNCATED_REPLY)
        assert str(raised.value) == (
            "Unexpected or incomplete Claude API response (stop_reason=max_tokens)"
        )
        assert len(requests) == 1
