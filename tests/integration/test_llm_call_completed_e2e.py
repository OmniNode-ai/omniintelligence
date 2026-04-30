# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Integration tests for llm-call-completed event pipeline.

Verifies:
    1. Topic declared in bloom_eval_orchestrator contract
    2. EvalLLMClient emits event via in-memory publisher
    3. Event arrives on correct topic with expected payload shape

Reference: OMN-5184 Task 3
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from omniintelligence.clients.eval_llm_client import EvalLLMClient
from omniintelligence.runtime.contract_topics import _read_event_bus_topics
from omniintelligence.topics import IntentTopic


@pytest.mark.integration
class TestLLMCallCompletedTopicDeclaration:
    """Verify topic is declared in contract YAML."""

    def test_topic_in_bloom_eval_contract_publish_topics(self) -> None:
        """llm-call-completed.v1 declared in bloom eval publish_topics."""
        publish_topics = _read_event_bus_topics(
            "omniintelligence.nodes.node_bloom_eval_orchestrator",
            "publish_topics",
        )
        assert IntentTopic.LLM_CALL_COMPLETED in publish_topics

    def test_topic_enum_value_matches_contract(self) -> None:
        """IntentTopic enum value matches the string in contract YAML."""
        assert (
            IntentTopic.LLM_CALL_COMPLETED
            == "onex.evt.omniintelligence.llm-call-completed.v1"
        )


@pytest.mark.integration
class TestLLMCallCompletedEventFlow:
    """Verify event emission via in-memory publisher."""

    @pytest.mark.asyncio
    async def test_event_arrives_on_correct_topic(self) -> None:
        """EvalLLMClient emits event on llm-call-completed topic."""
        received_events: list[dict[str, Any]] = []

        async def capture_publish(
            *, topic: str, key: str, value: dict[str, object]
        ) -> None:
            received_events.append({"topic": topic, "key": key, "value": value})

        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock(side_effect=capture_publish)

        client = EvalLLMClient(
            generator_url="http://test:8001",
            judge_url="http://test:8101",
            event_publisher=mock_publisher,
            correlation_id="test-corr-id",
            session_id="test-sess-id",
        )

        mock_response: dict[str, Any] = {
            "choices": [
                {"message": {"content": "scenario 1"}},
                {"message": {"content": "scenario 2"}},
            ],
            "usage": {"prompt_tokens": 500, "completion_tokens": 200},
        }

        with patch.object(
            client,
            "_post_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            await client.connect()
            await client.generate_scenarios(
                prompt_template="test", n=2, model="qwen3-14b"
            )

        assert len(received_events) == 1
        event = received_events[0]
        assert event["topic"] == IntentTopic.LLM_CALL_COMPLETED
        assert event["key"] == "test-corr-id"

        payload = event["value"]
        assert payload["model_id"] == "qwen3-14b"
        assert payload["endpoint_url"] == "http://test:8001"
        assert payload["input_tokens"] == 500
        assert payload["output_tokens"] == 200
        assert payload["total_tokens"] == 700
        assert payload["request_type"] == "completion"
        assert payload["correlation_id"] == "test-corr-id"
        assert payload["session_id"] == "test-sess-id"
        assert payload["cost_usd"] == 0.0
        assert payload["usage_source"] == "estimated"
        assert payload.get("gpu_seconds") is None
        assert payload.get("gpu_type") is None
        assert payload.get("gpu_count") is None
        assert payload.get("compute_usage_source") is None
        assert "emitted_at" in payload
        assert payload["latency_ms"] >= 0
