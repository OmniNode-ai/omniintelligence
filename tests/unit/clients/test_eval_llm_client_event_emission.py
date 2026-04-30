# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for EvalLLMClient telemetry event emission.

Tests:
    1. Emits ModelLLMCallCompletedEvent on successful call (mock publisher)
    2. No-op when publisher is None
    3. Publisher failure does not block LLM call result

Reference: OMN-5184 Task 2
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from omniintelligence.clients.eval_llm_client import EvalLLMClient
from omniintelligence.topics import IntentTopic


def _make_mock_response(
    *, prompt_tokens: int = 100, completion_tokens: int = 50
) -> dict[str, Any]:
    """Create a mock OpenAI-compatible response dict."""
    return {
        "choices": [
            {
                "message": {
                    "content": '{"metamorphic_stability_score": 0.9, "compliance_theater_risk": 0.1, "ambiguity_flags": [], "invented_requirements": [], "missing_acceptance_criteria": []}'
                }
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }


@pytest.mark.unit
class TestEvalLLMClientEventEmission:
    """Test telemetry event emission from EvalLLMClient."""

    @pytest.mark.asyncio
    async def test_emits_event_on_successful_call(self) -> None:
        """Publisher.publish called with ModelLLMCallCompletedEvent payload."""
        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock()

        client = EvalLLMClient(
            generator_url="http://test:8001",
            judge_url="http://test:8101",
            event_publisher=mock_publisher,
            correlation_id="corr-123",
            session_id="sess-456",
        )

        mock_response = _make_mock_response(prompt_tokens=200, completion_tokens=80)

        with patch.object(
            client,
            "_post_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            await client.connect()
            result = await client.judge_output(
                prompt="test prompt",
                output="test output",
                failure_indicators=["indicator1"],
            )

        assert result is not None
        mock_publisher.publish.assert_called_once()
        call_kwargs = mock_publisher.publish.call_args
        assert call_kwargs.kwargs["topic"] == IntentTopic.LLM_CALL_COMPLETED
        assert call_kwargs.kwargs["key"] == "corr-123"

        value = call_kwargs.kwargs["value"]
        assert value["input_tokens"] == 200
        assert value["output_tokens"] == 80
        assert value["total_tokens"] == 280
        assert value["request_type"] == "reasoning"
        assert value["endpoint_url"] == "http://test:8101"
        assert value["correlation_id"] == "corr-123"
        assert value["session_id"] == "sess-456"
        # Local models have $0.00 infra-cost rates; estimated provenance keeps
        # the row visible in Cost Trends.
        assert value["cost_usd"] == 0.0
        assert value["usage_source"] == "estimated"

    @pytest.mark.asyncio
    async def test_no_op_when_publisher_is_none(self) -> None:
        """No event emitted when event_publisher is None."""
        client = EvalLLMClient(
            generator_url="http://test:8001",
            judge_url="http://test:8101",
        )

        mock_response = _make_mock_response()

        with patch.object(
            client,
            "_post_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            await client.connect()
            result = await client.generate_scenarios(prompt_template="test")

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_publisher_failure_does_not_block_result(self) -> None:
        """LLM call result returned even if publisher.publish raises."""
        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock(side_effect=RuntimeError("Kafka down"))

        client = EvalLLMClient(
            generator_url="http://test:8001",
            judge_url="http://test:8101",
            event_publisher=mock_publisher,
            correlation_id="corr-999",
            session_id="sess-999",
        )

        mock_response = _make_mock_response()

        with patch.object(
            client,
            "_post_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            await client.connect()
            result = await client.judge_output(
                prompt="test",
                output="test output",
                failure_indicators=["x"],
            )

        # Result returned despite publisher failure
        assert "choices" in result
        mock_publisher.publish.assert_called_once()
