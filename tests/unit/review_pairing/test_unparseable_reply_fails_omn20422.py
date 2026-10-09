# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""An unparseable reviewer reply is a failed vote, never a clean one (OMN-20422).

Before this change ``async_parse_raw`` turned a reply that did not parse as JSON
into ``success=True`` with zero findings, so the second voter of the Hostile
Reviewer quorum counted as a clean review and the gate passed on one real
review (omnibase_infra#4757). An unparseable reply is retried once with the same
prompt; a second one marks the model failed, so the quorum reads DEGRADED.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from omniintelligence.review_pairing.adapters import adapter_ai_reviewer
from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    try_parse_review_response,
)

_GARBAGE = "I could not produce JSON, sorry. Here are some thoughts instead."
_VALID = json.dumps(
    [
        {
            "category": "architecture",
            "severity": "major",
            "title": "Missing retry",
            "description": "No retry on transient failure.",
            "evidence": "line 3",
            "proposed_fix": "add retry",
            "location": "plan.md",
        }
    ]
)


@pytest.mark.unit
class TestTryParseReviewResponse:
    @pytest.mark.parametrize(
        "raw", [_GARBAGE, "", "   ", '"just a string"', "42", "[not json]"]
    )
    def test_unparseable_returns_none(self, raw: str) -> None:
        assert try_parse_review_response(raw) is None

    def test_empty_array_is_a_parsed_clean_review(self) -> None:
        assert try_parse_review_response("[]") == []

    def test_valid_array_parses(self) -> None:
        assert len(try_parse_review_response(_VALID) or []) == 1


@pytest.mark.unit
class TestAsyncParseRawUnparseableReply:
    @pytest.mark.asyncio
    async def test_garbage_twice_marks_model_failed(self) -> None:
        call = AsyncMock(side_effect=[_GARBAGE, _GARBAGE + " again"])
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                "# Plan", model="qwen3-review"
            )

        assert call.await_count == 2
        assert result.success is False
        assert result.findings == []
        assert result.parse_failed is True
        assert result.raw_reply_length == len(_GARBAGE + " again")
        assert result.error is not None
        assert "unparseable" in result.error
        # The length is recorded, the reply text is not.
        assert "sorry" not in result.error
        assert _GARBAGE not in result.model_dump_json()

    @pytest.mark.asyncio
    async def test_retry_uses_the_same_prompt(self) -> None:
        call = AsyncMock(side_effect=[_GARBAGE, _GARBAGE])
        with patch.object(adapter_ai_reviewer, "call_model", call):
            await adapter_ai_reviewer.async_parse_raw("# Plan", model="qwen3-review")

        assert call.await_args_list[0] == call.await_args_list[1]

    @pytest.mark.asyncio
    async def test_reply_fixed_on_retry_succeeds(self) -> None:
        call = AsyncMock(side_effect=[_GARBAGE, _VALID])
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                "# Plan", model="qwen3-review"
            )

        assert call.await_count == 2
        assert result.success is True
        assert result.result_count == 1
        assert result.parse_failed is False
        assert result.raw_reply_length is None

    @pytest.mark.asyncio
    async def test_valid_reply_is_not_retried(self) -> None:
        call = AsyncMock(return_value=_VALID)
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                "# Plan", model="qwen3-review"
            )

        assert call.await_count == 1
        assert result.success is True
        assert result.result_count == 1
        assert result.parse_failed is False

    @pytest.mark.asyncio
    async def test_clean_empty_array_is_a_success_without_retry(self) -> None:
        call = AsyncMock(return_value="[]")
        with patch.object(adapter_ai_reviewer, "call_model", call):
            result = await adapter_ai_reviewer.async_parse_raw(
                "# Plan", model="qwen3-review"
            )

        assert call.await_count == 1
        assert result.success is True
        assert result.result_count == 0
        assert result.parse_failed is False


@pytest.mark.unit
class TestQuorumReadsDegradedOnUnparseableSecondVoter:
    """The #4757 shape: one voter reviews, the other replies with garbage."""

    @pytest.mark.asyncio
    async def test_garbage_second_voter_degrades_the_quorum(self) -> None:
        from omniintelligence.review_pairing.cli_review import run_review
        from omniintelligence.review_pairing.models_external_review import (
            EnumQuorumVerdict,
            ModelReviewQuorumPolicy,
        )
        from omniintelligence.review_pairing.quorum import evaluate_quorum

        async def _reply(
            system_prompt: str, user_prompt: str, model_key: str = ""
        ) -> str:
            return "[]" if model_key == "qwen3-review" else _GARBAGE

        with patch.object(adapter_ai_reviewer, "call_model", side_effect=_reply):
            multi = await run_review("# Plan", ["qwen3-review", "local-studio-planner"])

        assert multi.models_succeeded == ["qwen3-review"]
        assert multi.models_failed == ["local-studio-planner"]
        summary = evaluate_quorum(multi, ModelReviewQuorumPolicy())
        assert summary.verdict is EnumQuorumVerdict.DEGRADED_QUORUM

    @pytest.mark.asyncio
    async def test_two_clean_voters_still_pass(self) -> None:
        """Positive control: the same path with two parseable replies passes."""
        from omniintelligence.review_pairing.cli_review import run_review
        from omniintelligence.review_pairing.models_external_review import (
            EnumQuorumVerdict,
            ModelReviewQuorumPolicy,
        )
        from omniintelligence.review_pairing.quorum import evaluate_quorum

        with patch.object(
            adapter_ai_reviewer,
            "call_model",
            new_callable=AsyncMock,
            return_value="[]",
        ):
            multi = await run_review("# Plan", ["qwen3-review", "local-studio-planner"])

        assert multi.models_failed == []
        summary = evaluate_quorum(multi, ModelReviewQuorumPolicy())
        assert summary.verdict is not EnumQuorumVerdict.DEGRADED_QUORUM
