# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The retry of an unparseable reviewer reply runs with a larger token budget.

A review reply that reaches the 4096-token cap stops mid-JSON and does not
parse. The retry used to resend the request with the same cap, so a diff whose
review runs long failed twice and the required voter did not vote: on
omnibase_infra#4928 the correctness voter replied 16303 and 16907 characters,
about 4096 tokens of review JSON, and the gate read degraded_quorum. Replayed
on the same lab endpoint, the same prompt with a 2048-token cap stopped with
finish_reason=length and did not parse.

The first call is unchanged. Only the retry asks for the larger budget, so a
reply that ran out of tokens can finish; the per-call timeout is unchanged.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from omniintelligence.review_pairing.adapters import adapter_ai_reviewer

_FINDING = {
    "category": "correctness",
    "severity": "major",
    "title": "Off by one",
    "description": "The loop skips the last item.",
    "evidence": "line 3",
    "proposed_fix": "use <=",
    "location": "a.py",
}
_VALID = json.dumps([_FINDING])
# A review array cut off mid-object, the shape a reply has at the token cap.
_TRUNCATED = json.dumps([_FINDING, _FINDING])[:-40]


@pytest.mark.unit
class TestRetryTokenBudget:
    def test_a_truncated_review_does_not_parse(self) -> None:
        assert adapter_ai_reviewer.try_parse_review_response(_TRUNCATED) is None

    def test_the_retry_budget_is_larger_than_the_first(self) -> None:
        assert (
            adapter_ai_reviewer._RETRY_MAX_TOKENS
            > adapter_ai_reviewer._DEFAULT_MAX_TOKENS
        )

    @pytest.mark.asyncio
    async def test_retry_asks_for_the_larger_budget(self) -> None:
        call = AsyncMock(side_effect=[_TRUNCATED, _VALID])
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                "# Plan", model="qwen3-review"
            )

        assert result.success is True
        assert result.result_count == 1
        first, retry = call.await_args_list
        assert "max_tokens" not in first.kwargs
        assert retry.kwargs["max_tokens"] == adapter_ai_reviewer._RETRY_MAX_TOKENS
        # Same system prompt, model and review request on both calls; the retry
        # adds the JSON-only instruction (OMN-20717) and the larger budget.
        assert first.args[0] == retry.args[0]
        assert retry.args[1].startswith(first.args[1])
        assert first.kwargs["model_key"] == retry.kwargs["model_key"]

    @pytest.mark.asyncio
    async def test_truncated_twice_still_fails_the_vote(self) -> None:
        call = AsyncMock(side_effect=[_TRUNCATED, _TRUNCATED])
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                "# Plan", model="qwen3-review"
            )

        assert call.await_count == 2
        assert result.success is False
        assert result.parse_failed is True

    @pytest.mark.asyncio
    async def test_call_model_sends_the_budget_it_is_given(self) -> None:
        env = dict.fromkeys(("LOCAL_LLM_SHARED_SECRET",), "x")
        env["LLM_QWEN3_REVIEW_URL"] = "http://x:1"
        with patch.dict("os.environ", env, clear=False):
            with (
                patch(
                    "omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible.HandlerLlmOpenaiCompatible"
                ) as handler_cls,
                patch(
                    "omniintelligence.review_pairing.adapters.adapter_ai_reviewer.resolve_served_model_id",
                    return_value="served-model-id",
                ),
            ):
                handler_inst = AsyncMock()
                handler_inst.handle.return_value = AsyncMock(generated_text="[]")
                handler_cls.return_value = handler_inst
                await adapter_ai_reviewer.call_model(
                    "sys", "usr", model_key="qwen3-review"
                )
                default_request = handler_inst.handle.call_args[0][0]
                await adapter_ai_reviewer.call_model(
                    "sys",
                    "usr",
                    model_key="qwen3-review",
                    max_tokens=adapter_ai_reviewer._RETRY_MAX_TOKENS,
                )
                retry_request = handler_inst.handle.call_args[0][0]

        assert default_request.max_tokens == adapter_ai_reviewer._DEFAULT_MAX_TOKENS
        assert retry_request.max_tokens == adapter_ai_reviewer._RETRY_MAX_TOKENS
