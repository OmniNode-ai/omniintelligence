# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Tests for handle_stop handler in Claude Hook Event Effect.

Validates that Stop events trigger pattern learning command emission
to onex.cmd.omniintelligence.pattern-learning.v1.

Related:
    - OMN-2210: Wire intelligence nodes into registration + pattern extraction
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
    ProtocolKafkaPublisher,
    handle_stop,
    route_hook_event,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models import (
    EnumClaudeCodeHookEventType,
    EnumHookProcessingStatus,
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
)


def _make_stop_event() -> ModelClaudeCodeHookEvent:
    """Create a Stop hook event for testing."""
    return ModelClaudeCodeHookEvent(
        event_type=EnumClaudeCodeHookEventType.STOP,
        session_id="test-session-123",
        correlation_id=uuid4(),
        timestamp_utc=datetime.now(UTC).isoformat(),
        payload=ModelClaudeCodeHookEventPayload(),
    )


def _make_mock_producer(**kwargs: object) -> AsyncMock:
    """Create a mock Kafka producer with protocol conformance verification."""
    mock_producer = AsyncMock()
    mock_producer.publish = AsyncMock(**kwargs)
    assert isinstance(mock_producer, ProtocolKafkaPublisher)
    return mock_producer


@pytest.mark.unit
class TestHandleStop:
    """Test handle_stop handler function."""

    @pytest.mark.asyncio
    async def test_returns_success_without_kafka(self) -> None:
        """Should return success even without Kafka producer."""
        event = _make_stop_event()
        result = await handle_stop(event=event, kafka_producer=None)

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.event_type == "Stop"
        assert result.session_id == "test-session-123"
        assert result.metadata is not None
        assert result.metadata["handler"] == "stop_trigger_pattern_learning"
        assert result.metadata["pattern_learning_emission"] == "no_producer"

    @pytest.mark.asyncio
    async def test_emits_pattern_learning_command(self) -> None:
        """Should emit pattern learning command to Kafka on Stop."""
        event = _make_stop_event()
        mock_producer = _make_mock_producer()

        result = await handle_stop(event=event, kafka_producer=mock_producer)

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.metadata is not None
        assert result.metadata["pattern_learning_emission"] == "success"
        assert (
            result.metadata["pattern_learning_topic"]
            == "onex.cmd.omniintelligence.pattern-learning.v1"
        )

        # Verify Kafka publish was called with correct topic
        mock_producer.publish.assert_awaited_once()
        call_kwargs = mock_producer.publish.call_args
        assert call_kwargs.kwargs["topic"] == "onex.cmd.omniintelligence.pattern-learning.v1"

    @pytest.mark.asyncio
    async def test_emitted_payload_structure(self) -> None:
        """Verify the emitted command payload has correct structure."""
        event = _make_stop_event()
        mock_producer = _make_mock_producer()

        await handle_stop(event=event, kafka_producer=mock_producer)

        # Get the value argument from the publish call (keyword args)
        call_args = mock_producer.publish.call_args
        payload = call_args.kwargs["value"]

        assert payload["event_type"] == "PatternLearningRequested"
        assert payload["session_id"] == "test-session-123"
        assert payload["trigger"] == "session_stop"
        assert payload["correlation_id"] == str(event.correlation_id)
        assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_handles_kafka_publish_failure(self) -> None:
        """Should return PARTIAL when Kafka producer was available but publish failed."""
        event = _make_stop_event()
        mock_producer = _make_mock_producer(
            side_effect=RuntimeError("Kafka unavailable"),
        )

        result = await handle_stop(event=event, kafka_producer=mock_producer)

        # Should return PARTIAL: Kafka was configured but emission failed
        assert result.status == EnumHookProcessingStatus.PARTIAL
        assert result.metadata is not None
        assert result.metadata["pattern_learning_emission"] == "failed"
        assert "Kafka unavailable" in result.metadata["pattern_learning_error"]

        # Verify DLQ routing was attempted: producer.publish should be called
        # twice -- once for the original topic (which fails) and once for the
        # DLQ topic (which also fails because the mock raises unconditionally).
        assert mock_producer.publish.await_count == 2
        dlq_call = mock_producer.publish.call_args_list[1]
        assert dlq_call.kwargs["topic"].endswith(".dlq")

        # DLQ publish also failed (same side_effect), so metadata reflects that
        assert result.metadata["pattern_learning_dlq"] == "failed"


@pytest.mark.unit
class TestRouteHookEventStop:
    """Test that route_hook_event correctly routes Stop events."""

    @pytest.mark.asyncio
    async def test_stop_event_routed_to_handle_stop(self) -> None:
        """Stop events should be routed to handle_stop, not handle_no_op."""
        event = _make_stop_event()
        mock_producer = _make_mock_producer()

        result = await route_hook_event(
            event=event,
            kafka_producer=mock_producer,
        )

        assert result.status == EnumHookProcessingStatus.SUCCESS
        # Verify it went through handle_stop (has pattern_learning metadata)
        assert result.metadata is not None
        assert result.metadata["handler"] == "stop_trigger_pattern_learning"
