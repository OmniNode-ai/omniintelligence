# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Integration tests for Claude Hook Event Effect event bus routing.

Tests the full event flow: publish event -> handler processes -> output event published.
Uses EventBusInmemory for testing without Kafka infrastructure.

Reference:
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
    ProtocolKafkaPublisher,
    route_hook_event,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models import (
    EnumHookProcessingStatus,
)

from .conftest import TOPIC_SUFFIX_INTENT_CLASSIFIED_V1

# =============================================================================
# Test Classes
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestEventBusPublishSubscribe:
    """Tests for basic EventBusInmemory pub/sub functionality."""

    async def test_publish_subscribe_roundtrip(
        self,
        event_bus: EventBusInmemory,
        test_node_identity: ModelNodeIdentity,
    ) -> None:
        """Test basic EventBusInmemory pub/sub works.

        Verifies:
        - Event bus can be started
        - Subscriber receives published messages
        - Event history captures the message
        """
        received_messages: list[ModelEventMessage] = []
        test_topic = "test.roundtrip.topic"

        async def message_handler(msg: ModelEventMessage) -> None:
            received_messages.append(msg)

        # Start the event bus
        await event_bus.start()

        try:
            # Subscribe to the test topic
            unsubscribe = await event_bus.subscribe(
                test_topic,
                test_node_identity,
                message_handler,
            )

            # Publish a test message
            test_payload = {"test_key": "test_value", "number": 42}
            test_value = json.dumps(test_payload).encode("utf-8")
            test_key = b"test-key"

            await event_bus.publish(test_topic, test_key, test_value)

            # Verify subscriber received the message
            assert len(received_messages) == 1
            assert received_messages[0].topic == test_topic
            assert received_messages[0].value == test_value
            assert received_messages[0].key == test_key

            # Verify event history
            history = await event_bus.get_event_history(topic=test_topic)
            assert len(history) == 1
            assert history[0].topic == test_topic

            # Cleanup
            await unsubscribe()

        finally:
            await event_bus.close()


@pytest.mark.asyncio
@pytest.mark.integration
class TestUserPromptSubmitFullFlow:
    """Tests for the full UserPromptSubmit event processing flow."""

    async def test_user_prompt_submit_full_flow(
        self,
        event_bus: EventBusInmemory,
        output_topic: str,
        sample_user_prompt_event: ModelClaudeCodeHookEvent,
        kafka_publisher_adapter: ProtocolKafkaPublisher,
        test_node_identity: ModelNodeIdentity,
    ) -> None:
        """Test full flow: publish -> process -> output event.

        Verifies:
        - Handler processes UserPromptSubmit successfully
        - Output event is published to correct topic
        - Output event contains expected fields
        """
        received_outputs: list[ModelEventMessage] = []

        async def output_handler(msg: ModelEventMessage) -> None:
            received_outputs.append(msg)

        await event_bus.start()

        try:
            # Subscribe to output topic
            unsubscribe = await event_bus.subscribe(
                output_topic,
                test_node_identity,
                output_handler,
            )

            # Process event through handler
            result = await route_hook_event(
                event=sample_user_prompt_event,
                kafka_producer=kafka_publisher_adapter,
                topic_env_prefix="test",
                publish_topic_suffix=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
            )

            # Verify handler succeeded
            assert result.status == EnumHookProcessingStatus.SUCCESS
            assert result.intent_result is not None
            assert result.intent_result.emitted_to_kafka is True

            # Verify output event was published
            assert len(received_outputs) == 1
            output_event = json.loads(received_outputs[0].value)
            assert output_event["event_type"] == "IntentClassified"
            assert output_event["session_id"] == sample_user_prompt_event.session_id

            # Cleanup
            await unsubscribe()

        finally:
            await event_bus.close()

    async def test_output_event_published_on_classification(
        self,
        event_bus: EventBusInmemory,
        output_topic: str,
        sample_user_prompt_event: ModelClaudeCodeHookEvent,
        kafka_publisher_adapter: ProtocolKafkaPublisher,
        test_node_identity: ModelNodeIdentity,
    ) -> None:
        """Test intent-classified event has correct structure.

        Verifies output event contains:
        - event_type
        - session_id
        - correlation_id
        - intent_category
        - confidence
        - timestamp
        """
        received_outputs: list[ModelEventMessage] = []

        async def output_handler(msg: ModelEventMessage) -> None:
            received_outputs.append(msg)

        await event_bus.start()

        try:
            unsubscribe = await event_bus.subscribe(
                output_topic,
                test_node_identity,
                output_handler,
            )

            # Process the event
            result = await route_hook_event(
                event=sample_user_prompt_event,
                kafka_producer=kafka_publisher_adapter,
                topic_env_prefix="test",
                publish_topic_suffix=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
            )

            assert result.status == EnumHookProcessingStatus.SUCCESS
            assert len(received_outputs) == 1

            # Parse and verify output event structure
            output_event = json.loads(received_outputs[0].value)

            # Required fields
            assert "event_type" in output_event
            assert output_event["event_type"] == "IntentClassified"

            assert "session_id" in output_event
            assert output_event["session_id"] == sample_user_prompt_event.session_id

            assert "correlation_id" in output_event
            assert output_event["correlation_id"] == str(
                sample_user_prompt_event.correlation_id
            )

            assert "intent_category" in output_event
            # Without classifier, defaults to "unknown"
            assert output_event["intent_category"] == "unknown"

            assert "confidence" in output_event
            # Without classifier, defaults to 0.0
            assert output_event["confidence"] == 0.0

            assert "timestamp" in output_event
            # Timestamp should be ISO format
            assert isinstance(output_event["timestamp"], str)

            await unsubscribe()

        finally:
            await event_bus.close()


@pytest.mark.asyncio
@pytest.mark.integration
class TestNoOpEventTypes:
    """Tests for event types that don't produce output events."""

    async def test_session_start_no_output_event(
        self,
        event_bus: EventBusInmemory,
        output_topic: str,
        sample_session_start_event: ModelClaudeCodeHookEvent,
        kafka_publisher_adapter: ProtocolKafkaPublisher,
        test_node_identity: ModelNodeIdentity,
    ) -> None:
        """Test SessionStart event doesn't publish output event.

        Verifies:
        - Handler returns SUCCESS
        - intent_result is None
        - No output events published
        """
        received_outputs: list[ModelEventMessage] = []

        async def output_handler(msg: ModelEventMessage) -> None:
            received_outputs.append(msg)

        await event_bus.start()

        try:
            unsubscribe = await event_bus.subscribe(
                output_topic,
                test_node_identity,
                output_handler,
            )

            # Process SessionStart event
            result = await route_hook_event(
                event=sample_session_start_event,
                kafka_producer=kafka_publisher_adapter,
                topic_env_prefix="test",
                publish_topic_suffix=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
            )

            # Verify handler returned success without intent
            assert result.status == EnumHookProcessingStatus.SUCCESS
            assert result.intent_result is None

            # Verify no output events published
            assert len(received_outputs) == 0

            # Verify event history for output topic is empty
            history = await event_bus.get_event_history(topic=output_topic)
            assert len(history) == 0

            await unsubscribe()

        finally:
            await event_bus.close()


@pytest.mark.asyncio
@pytest.mark.integration
class TestAllEventTypesHandled:
    """Tests for handling all Claude Code hook event types."""

    async def test_all_event_types_handled(
        self,
        event_bus: EventBusInmemory,
        kafka_publisher_adapter: ProtocolKafkaPublisher,
    ) -> None:
        """Test all 12 enum values route successfully.

        Verifies:
        - All event types return SUCCESS or PARTIAL (not FAILED)
        - UserPromptSubmit has intent_result
        - Other event types have None intent_result
        """
        await event_bus.start()

        try:
            for event_type in EnumClaudeCodeHookEventType:
                # Create a sample event for this type
                # UserPromptSubmit needs a prompt in payload
                if event_type == EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT:
                    payload = ModelClaudeCodeHookEventPayload(
                        prompt="Test prompt for classification"
                    )
                else:
                    payload = ModelClaudeCodeHookEventPayload()

                event = ModelClaudeCodeHookEvent(
                    event_type=event_type,
                    session_id=f"test-session-{event_type.value}",
                    correlation_id=uuid4(),
                    timestamp_utc=datetime.now(UTC),
                    payload=payload,
                )

                # Process the event
                result = await route_hook_event(
                    event=event,
                    kafka_producer=kafka_publisher_adapter,
                    topic_env_prefix="test",
                    publish_topic_suffix=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
                )

                # Verify all return SUCCESS or PARTIAL (not FAILED)
                assert result.status in {
                    EnumHookProcessingStatus.SUCCESS,
                    EnumHookProcessingStatus.PARTIAL,
                }, f"Event type {event_type.value} returned status {result.status}"

                # Verify correct intent_result behavior
                if event_type == EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT:
                    assert result.intent_result is not None, (
                        "UserPromptSubmit should have intent_result"
                    )
                    assert result.intent_result.emitted_to_kafka is True
                else:
                    assert result.intent_result is None, (
                        f"Event type {event_type.value} should have None intent_result"
                    )

        finally:
            await event_bus.close()


@pytest.mark.asyncio
@pytest.mark.integration
class TestEventHistoryDebugging:
    """Tests for event history debugging utilities."""

    async def test_event_history_captures_flow(
        self,
        event_bus: EventBusInmemory,
        output_topic: str,
        sample_user_prompt_event: ModelClaudeCodeHookEvent,
        kafka_publisher_adapter: ProtocolKafkaPublisher,
        test_node_identity: ModelNodeIdentity,
    ) -> None:
        """Test event history captures published events for debugging.

        Verifies:
        - get_event_history returns published events
        - Events can be filtered by topic
        - Event history is useful for debugging
        """
        await event_bus.start()

        try:
            # Subscribe (even if we don't use the handler, we test history separately)
            unsubscribe = await event_bus.subscribe(
                output_topic,
                test_node_identity,
                lambda _: None,  # No-op handler
            )

            # Process an event
            result = await route_hook_event(
                event=sample_user_prompt_event,
                kafka_producer=kafka_publisher_adapter,
                topic_env_prefix="test",
                publish_topic_suffix=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
            )

            assert result.status == EnumHookProcessingStatus.SUCCESS

            # Use get_event_history to verify event was published
            history = await event_bus.get_event_history(topic=output_topic)

            assert len(history) == 1
            assert history[0].topic == output_topic

            # Verify event content via history
            event_content = json.loads(history[0].value)
            assert event_content["event_type"] == "IntentClassified"
            assert event_content["session_id"] == sample_user_prompt_event.session_id

            await unsubscribe()

        finally:
            await event_bus.close()

    async def test_clear_event_history_isolates_tests(
        self,
        event_bus: EventBusInmemory,
        output_topic: str,
        sample_user_prompt_event: ModelClaudeCodeHookEvent,
        kafka_publisher_adapter: ProtocolKafkaPublisher,
    ) -> None:
        """Test clear_event_history isolates tests from each other.

        Verifies:
        - clear_event_history empties the history
        - New events can be tracked after clearing
        """
        await event_bus.start()

        try:
            # Process an event
            await route_hook_event(
                event=sample_user_prompt_event,
                kafka_producer=kafka_publisher_adapter,
                topic_env_prefix="test",
                publish_topic_suffix=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
            )

            # Verify history has the event
            history_before = await event_bus.get_event_history(topic=output_topic)
            assert len(history_before) == 1

            # Clear the history
            await event_bus.clear_event_history()

            # Verify history is empty
            history_after = await event_bus.get_event_history(topic=output_topic)
            assert len(history_after) == 0

            # Process another event
            await route_hook_event(
                event=sample_user_prompt_event,
                kafka_producer=kafka_publisher_adapter,
                topic_env_prefix="test",
                publish_topic_suffix=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
            )

            # Verify only the new event is in history
            history_new = await event_bus.get_event_history(topic=output_topic)
            assert len(history_new) == 1

        finally:
            await event_bus.close()


@pytest.mark.asyncio
@pytest.mark.integration
class TestEdgeCases:
    """Tests for edge cases and error scenarios."""

    async def test_empty_prompt_fails_gracefully(
        self,
        event_bus: EventBusInmemory,
        output_topic: str,
        kafka_publisher_adapter: ProtocolKafkaPublisher,
        test_node_identity: ModelNodeIdentity,
    ) -> None:
        """Test UserPromptSubmit with empty prompt returns FAILED.

        Verifies:
        - Handler returns FAILED status
        - No output event is published
        - Error message is informative
        """
        received_outputs: list[ModelEventMessage] = []

        async def output_handler(msg: ModelEventMessage) -> None:
            received_outputs.append(msg)

        # Create event with empty prompt
        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT,
            session_id="test-session-empty-prompt",
            correlation_id=uuid4(),
            timestamp_utc=datetime.now(UTC),
            payload=ModelClaudeCodeHookEventPayload(prompt=""),
        )

        await event_bus.start()

        try:
            unsubscribe = await event_bus.subscribe(
                output_topic,
                test_node_identity,
                output_handler,
            )

            result = await route_hook_event(
                event=event,
                kafka_producer=kafka_publisher_adapter,
                topic_env_prefix="test",
                publish_topic_suffix=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
            )

            # Verify handler failed gracefully
            assert result.status == EnumHookProcessingStatus.FAILED
            assert result.intent_result is None
            assert result.error_message is not None
            assert "prompt" in result.error_message.lower()

            # Verify no output event published
            assert len(received_outputs) == 0

            await unsubscribe()

        finally:
            await event_bus.close()

    async def test_no_kafka_producer_returns_success_without_emission(
        self,
        sample_user_prompt_event: ModelClaudeCodeHookEvent,
    ) -> None:
        """Test handler works without Kafka producer.

        Verifies:
        - Handler returns SUCCESS
        - intent_result indicates not emitted to Kafka
        """
        result = await route_hook_event(
            event=sample_user_prompt_event,
            kafka_producer=None,
            topic_env_prefix="test",
        )

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.intent_result is not None
        assert result.intent_result.emitted_to_kafka is False
        assert result.intent_result.intent_category == "unknown"
        assert result.intent_result.confidence == 0.0


__all__ = [
    "TestAllEventTypesHandled",
    "TestEdgeCases",
    "TestEventBusPublishSubscribe",
    "TestEventHistoryDebugging",
    "TestNoOpEventTypes",
    "TestUserPromptSubmitFullFlow",
]
