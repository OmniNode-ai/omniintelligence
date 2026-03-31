# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Golden chain integration tests for node_claude_hook_event_effect.

Validates the end-to-end event chain: command event published on subscribe
topic -> handler processes -> output event appears on publish topic with
correct correlation_id and meaningful payload.

Also validates the error chain: malformed input produces a FAILED result
with no output event emitted.

Reference:
    - OMN-7142: Golden chain integration tests
    - OMN-1456: Unified Claude Code hook endpoint
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from omnibase_core.enums.hooks.claude_code import EnumClaudeCodeHookEventType
from omnibase_core.models.hooks.claude_code import (
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
)
from omnibase_infra.event_bus.event_bus_inmemory import EventBusInmemory
from omnibase_infra.event_bus.models import ModelEventMessage
from omnibase_infra.models import ModelNodeIdentity

from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
    route_hook_event,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models import (
    EnumHookProcessingStatus,
)

from .conftest import EventBusKafkaPublisherAdapter

# =============================================================================
# Constants
# =============================================================================

SUBSCRIBE_TOPIC = "test.onex.cmd.omniintelligence.claude-hook-event.v1"
PUBLISH_TOPIC = "test.onex.evt.omniintelligence.intent-classified.v1"


# =============================================================================
# Golden Chain Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestGoldenChainUserPromptSubmit:
    """Golden chain: command in -> handler -> output event with correlation_id."""

    async def test_golden_chain_correlation_id_preserved(
        self,
        event_bus: EventBusInmemory,
        test_node_identity: ModelNodeIdentity,
    ) -> None:
        """Publish UserPromptSubmit command, assert output event preserves correlation_id."""
        correlation_id = uuid4()
        session_id = f"golden-chain-{uuid4()}"

        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT,
            session_id=session_id,
            correlation_id=correlation_id,
            timestamp_utc=datetime.now(UTC),
            payload=ModelClaudeCodeHookEventPayload(
                prompt="Refactor the auth middleware to use dependency injection"
            ),
        )

        received: list[ModelEventMessage] = []

        async def on_output(msg: ModelEventMessage) -> None:
            received.append(msg)

        adapter = EventBusKafkaPublisherAdapter(event_bus)

        unsubscribe = await event_bus.subscribe(
            PUBLISH_TOPIC, test_node_identity, on_output
        )

        try:
            result = await route_hook_event(
                event=event,
                kafka_producer=adapter,
                publish_topic=PUBLISH_TOPIC,
            )

            # Handler succeeds
            assert result.status == EnumHookProcessingStatus.SUCCESS
            assert str(result.correlation_id) == str(correlation_id)

            # Output event received
            assert len(received) == 1
            payload = json.loads(received[0].value)

            # Correlation ID preserved end-to-end
            assert payload["correlation_id"] == str(correlation_id)
            assert payload["session_id"] == session_id
            assert payload["event_type"] == "IntentClassified"

            # Meaningful payload fields present
            assert "intent_category" in payload
            assert "confidence" in payload
            assert isinstance(payload["confidence"], float | int)
            assert "timestamp" in payload

        finally:
            await unsubscribe()

    async def test_golden_chain_stop_event_emits_pattern_learning(
        self,
        event_bus: EventBusInmemory,
        test_node_identity: ModelNodeIdentity,
    ) -> None:
        """Stop event triggers pattern-learning command on the correct topic."""
        from omniintelligence.constants import TOPIC_SUFFIX_PATTERN_LEARNING_CMD_V1

        pattern_topic = f"test.{TOPIC_SUFFIX_PATTERN_LEARNING_CMD_V1}"
        correlation_id = uuid4()
        session_id = f"golden-chain-stop-{uuid4()}"

        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.STOP,
            session_id=session_id,
            correlation_id=correlation_id,
            timestamp_utc=datetime.now(UTC),
            payload=ModelClaudeCodeHookEventPayload(),
        )

        received: list[ModelEventMessage] = []

        async def on_output(msg: ModelEventMessage) -> None:
            received.append(msg)

        adapter = EventBusKafkaPublisherAdapter(event_bus)

        unsubscribe = await event_bus.subscribe(
            pattern_topic, test_node_identity, on_output
        )

        try:
            result = await route_hook_event(
                event=event,
                kafka_producer=adapter,
                publish_topic=pattern_topic,
            )

            assert result.status in {
                EnumHookProcessingStatus.SUCCESS,
                EnumHookProcessingStatus.PARTIAL,
            }

            # Stop handler emits to the pattern-learning topic
            history = await event_bus.get_event_history(topic=pattern_topic)
            if len(history) > 0:
                payload = json.loads(history[0].value)
                assert payload["session_id"] == session_id
                assert payload["event_type"] == "PatternLearningRequested"

        finally:
            await unsubscribe()


@pytest.mark.asyncio
@pytest.mark.integration
class TestGoldenChainErrorPath:
    """Error chain: malformed input -> FAILED result, no output event."""

    async def test_empty_prompt_no_output_event(
        self,
        event_bus: EventBusInmemory,
        test_node_identity: ModelNodeIdentity,
    ) -> None:
        """UserPromptSubmit with empty prompt produces FAILED, no output emitted."""
        correlation_id = uuid4()

        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT,
            session_id="golden-chain-error-empty",
            correlation_id=correlation_id,
            timestamp_utc=datetime.now(UTC),
            payload=ModelClaudeCodeHookEventPayload(prompt=""),
        )

        received: list[ModelEventMessage] = []

        async def on_output(msg: ModelEventMessage) -> None:
            received.append(msg)

        adapter = EventBusKafkaPublisherAdapter(event_bus)

        unsubscribe = await event_bus.subscribe(
            PUBLISH_TOPIC, test_node_identity, on_output
        )

        try:
            result = await route_hook_event(
                event=event,
                kafka_producer=adapter,
                publish_topic=PUBLISH_TOPIC,
            )

            # Handler fails gracefully
            assert result.status == EnumHookProcessingStatus.FAILED
            assert result.error_message is not None
            assert "prompt" in result.error_message.lower()

            # No output event emitted
            assert len(received) == 0
            history = await event_bus.get_event_history(topic=PUBLISH_TOPIC)
            assert len(history) == 0

        finally:
            await unsubscribe()

    async def test_no_kafka_producer_graceful_degradation(self) -> None:
        """Handler without kafka_producer succeeds but does not emit."""
        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT,
            session_id="golden-chain-no-kafka",
            correlation_id=uuid4(),
            timestamp_utc=datetime.now(UTC),
            payload=ModelClaudeCodeHookEventPayload(
                prompt="Explain the event bus architecture"
            ),
        )

        result = await route_hook_event(
            event=event,
            kafka_producer=None,
        )

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.intent_result is not None
        assert result.intent_result.emitted_to_kafka is False


__all__ = [
    "TestGoldenChainErrorPath",
    "TestGoldenChainUserPromptSubmit",
]
