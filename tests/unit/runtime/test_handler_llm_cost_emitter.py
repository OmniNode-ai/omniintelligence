# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for handler_llm_cost_emitter.

Verifies:
    1. Payload shape matches omnidash projectLlmCostEvent expectations
    2. Fail-open when producer is None (no exception)
    3. Fail-open when producer.publish raises (no exception)

Reference: OMN-6801 Task 3
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from omniintelligence.runtime.handler_llm_cost_emitter import (
    LLM_COST_TOPIC,
    emit_llm_cost_event,
)


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmitLlmCostEvent:
    """Tests for emit_llm_cost_event."""

    async def test_payload_shape_matches_omnidash_consumer(self) -> None:
        """Verify payload contains all fields expected by projectLlmCostEvent."""
        captured: list[dict[str, Any]] = []

        async def capture_publish(
            *, topic: str, key: str, value: dict[str, object]
        ) -> None:
            captured.append({"topic": topic, "key": key, "value": value})

        mock_producer = AsyncMock()
        mock_producer.publish = AsyncMock(side_effect=capture_publish)

        correlation_id = uuid4()
        result = await emit_llm_cost_event(
            producer=mock_producer,
            topic=LLM_COST_TOPIC,
            model_id="qwen3-14b",
            prompt_tokens=500,
            completion_tokens=200,
            total_tokens=700,
            estimated_cost_usd=0.0035,
            session_id="test-session-123",
            correlation_id=correlation_id,
            endpoint_url="http://test:8001",
            request_type="completion",
            latency_ms=150,
            repo_name="omniintelligence",
            machine_id="devbox-201",
        )

        assert result is True
        assert len(captured) == 1

        event = captured[0]
        assert event["topic"] == LLM_COST_TOPIC
        assert event["key"] == str(correlation_id)

        payload = event["value"]
        assert payload["model_id"] == "qwen3-14b"
        assert payload["prompt_tokens"] == 500
        assert payload["completion_tokens"] == 200
        assert payload["total_tokens"] == 700
        assert payload["estimated_cost_usd"] == 0.0035
        assert payload["session_id"] == "test-session-123"
        assert payload["correlation_id"] == str(correlation_id)
        assert "timestamp_iso" in payload
        assert payload["endpoint_url"] == "http://test:8001"
        assert payload["request_type"] == "completion"
        assert payload["latency_ms"] == 150
        assert payload["repo_name"] == "omniintelligence"
        assert payload["machine_id"] == "devbox-201"
        # Omnidash also checks these aliased fields
        assert payload["input_tokens"] == 500
        assert payload["output_tokens"] == 200
        assert payload["cost_usd"] == 0.0035

    async def test_producer_none_returns_false_no_exception(self) -> None:
        """When producer is None, returns False without raising."""
        result = await emit_llm_cost_event(
            producer=None,
            topic=LLM_COST_TOPIC,
            model_id="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.001,
            session_id="test-session",
            correlation_id=uuid4(),
        )
        assert result is False

    async def test_publish_failure_returns_false_no_exception(self) -> None:
        """When producer.publish raises, returns False without propagating."""
        mock_producer = AsyncMock()
        mock_producer.publish = AsyncMock(
            side_effect=ConnectionError("Kafka unavailable")
        )

        result = await emit_llm_cost_event(
            producer=mock_producer,
            topic=LLM_COST_TOPIC,
            model_id="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.001,
            session_id="test-session",
            correlation_id=uuid4(),
        )
        assert result is False
