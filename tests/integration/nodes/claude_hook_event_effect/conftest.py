# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Fixtures for Claude Hook Event Effect integration tests.

This module provides pytest fixtures for testing the NodeClaudeHookEventEffect
node with an in-memory event bus. The fixtures enable testing of event routing
and processing without requiring external Kafka infrastructure.

Fixtures include:
    - In-memory event bus for message routing
    - Topic name constants following ONEX conventions
    - Sample Claude Code hook events for testing
    - Adapter to bridge ProtocolKafkaPublisher to EventBusInmemory
    - Mock intent classifier for controlled testing

Usage:
    @pytest.mark.integration
    async def test_user_prompt_event_routing(
        event_bus: EventBusInmemory,
        kafka_publisher_adapter: EventBusKafkaPublisherAdapter,
        sample_user_prompt_event: ModelClaudeCodeHookEvent,
    ) -> None:
        # Test event processing and routing...

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from omnibase_core.enums.hooks.claude_code import EnumClaudeCodeHookEventType
from omnibase_core.models.hooks.claude_code import (
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
)
from omnibase_infra.event_bus.event_bus_inmemory import EventBusInmemory

# =============================================================================
# Test Topic Constants
# =============================================================================

TEST_TOPIC_PREFIX: str = "test"
"""Environment prefix for test topics."""

TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1: str = "onex.cmd.omniintelligence.claude-hook-event.v1"
"""Topic suffix for Claude Code hook events (INPUT) in tests."""

TOPIC_SUFFIX_INTENT_CLASSIFIED_V1: str = "onex.evt.omniintelligence.intent-classified.v1"
"""Topic suffix for intent classification events (OUTPUT) in tests."""


# =============================================================================
# Adapter Classes
# =============================================================================


class EventBusKafkaPublisherAdapter:
    """Adapter to use EventBusInmemory as a ProtocolKafkaPublisher.

    This adapter bridges the interface gap between ProtocolKafkaPublisher
    (which the handler expects) and EventBusInmemory (which we use for testing).

    Protocol Bridging:
        ProtocolKafkaPublisher.publish(topic, key, value: dict) ->
        EventBusInmemory.publish(topic, key: bytes, value: bytes)

    The adapter serializes the dict value to JSON bytes for storage.

    Attributes:
        _event_bus: The underlying EventBusInmemory instance.

    Example:
        ```python
        event_bus = EventBusInmemory(environment="test", group="test-group")
        adapter = EventBusKafkaPublisherAdapter(event_bus)

        # Use adapter as ProtocolKafkaPublisher
        await adapter.publish(
            topic="test.events",
            key="session-123",
            value={"event_type": "IntentClassified", "data": {...}},
        )

        # Event is now in event_bus history
        history = await event_bus.get_event_history()
        ```
    """

    def __init__(self, event_bus: EventBusInmemory) -> None:
        """Initialize the adapter with an EventBusInmemory instance.

        Args:
            event_bus: The in-memory event bus to publish to.
        """
        self._event_bus = event_bus

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Publish event to EventBusInmemory using bytes API.

        Implements ProtocolKafkaPublisher interface by serializing the event
        to JSON bytes and delegating to EventBusInmemory.publish().

        Args:
            topic: Target Kafka topic name.
            key: Message key for partitioning.
            value: Event payload as a dictionary.
        """
        value_bytes = json.dumps(
            value, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        key_bytes = key.encode("utf-8") if key else None
        await self._event_bus.publish(topic=topic, key=key_bytes, value=value_bytes)


# =============================================================================
# Event Bus Fixtures
# =============================================================================


@pytest.fixture
async def event_bus() -> EventBusInmemory:
    """Create and start an in-memory event bus for testing.

    The event bus is configured with:
        - environment: "test" for test isolation
        - group: "test-group" for consumer group identification

    The fixture handles both start() and close() lifecycle.

    Returns:
        A started EventBusInmemory instance ready for use.
    """
    bus = EventBusInmemory(environment="test", group="test-group")
    await bus.start()
    yield bus
    await bus.close()


# =============================================================================
# Topic Fixtures
# =============================================================================


@pytest.fixture
def input_topic() -> str:
    """Return the input topic name for Claude hook events.

    Topic follows ONEX naming convention:
        {env}.onex.cmd.{domain}.{event-name}.{version}

    Returns:
        Full topic name for test environment.
    """
    return f"{TEST_TOPIC_PREFIX}.{TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1}"


@pytest.fixture
def output_topic() -> str:
    """Return the output topic name for classified intents.

    Topic follows ONEX naming convention:
        {env}.onex.evt.{domain}.{event-name}.{version}

    Returns:
        Full topic name for test environment.
    """
    return f"{TEST_TOPIC_PREFIX}.{TOPIC_SUFFIX_INTENT_CLASSIFIED_V1}"


# =============================================================================
# Sample Event Fixtures
# =============================================================================


@pytest.fixture
def sample_user_prompt_event() -> ModelClaudeCodeHookEvent:
    """Create a sample UserPromptSubmit event for testing.

    The event contains:
        - event_type: USER_PROMPT_SUBMIT
        - session_id: Unique test session identifier
        - payload: Contains a debug-focused prompt
        - timestamp: Current UTC time
        - correlation_id: Unique UUID for tracing

    Returns:
        A complete ModelClaudeCodeHookEvent ready for processing.
    """
    payload = ModelClaudeCodeHookEventPayload(
        prompt="Help me debug this Python function"
    )
    return ModelClaudeCodeHookEvent(
        event_type=EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT,
        session_id="test-session-123",
        correlation_id=uuid4(),
        timestamp_utc=datetime.now(UTC),
        payload=payload,
    )


@pytest.fixture
def sample_session_start_event() -> ModelClaudeCodeHookEvent:
    """Create a sample SessionStart event for testing.

    This is a no-op event type that should be acknowledged but not
    processed with intent classification.

    Returns:
        A SessionStart event for no-op handler testing.
    """
    payload = ModelClaudeCodeHookEventPayload(
        working_directory="/workspace/test-project"
    )
    return ModelClaudeCodeHookEvent(
        event_type=EnumClaudeCodeHookEventType.SESSION_START,
        session_id="test-session-123",
        correlation_id=uuid4(),
        timestamp_utc=datetime.now(UTC),
        payload=payload,
    )


@pytest.fixture
def sample_stop_event() -> ModelClaudeCodeHookEvent:
    """Create a sample Stop event for testing.

    This is a no-op event type that should be acknowledged but not
    processed with intent classification.

    Returns:
        A Stop event for no-op handler testing.
    """
    payload = ModelClaudeCodeHookEventPayload()
    return ModelClaudeCodeHookEvent(
        event_type=EnumClaudeCodeHookEventType.STOP,
        session_id="test-session-123",
        correlation_id=uuid4(),
        timestamp_utc=datetime.now(UTC),
        payload=payload,
    )


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_intent_classifier() -> MagicMock:
    """Create a mock intent classifier with controlled results.

    The mock returns a classification result with:
        - intent_category: "debugging"
        - confidence: 0.92
        - secondary_intents: []

    The mock's return values can be modified in individual tests:
        ```python
        mock_intent_classifier.compute.return_value.intent_category = "code_review"
        mock_intent_classifier.compute.return_value.confidence = 0.85
        ```

    Returns:
        A MagicMock implementing ProtocolIntentClassifier.
    """
    mock_classifier = MagicMock()

    # Create a mock output with expected attributes
    mock_output = MagicMock()
    mock_output.intent_category = "debugging"
    mock_output.confidence = 0.92
    mock_output.secondary_intents = []

    mock_classifier.compute = AsyncMock(return_value=mock_output)

    return mock_classifier


@pytest.fixture
def mock_failing_intent_classifier() -> MagicMock:
    """Create a mock intent classifier that raises an exception.

    Useful for testing error handling in the handler.

    Returns:
        A MagicMock that raises RuntimeError on compute().
    """
    mock_classifier = MagicMock()
    mock_classifier.compute = AsyncMock(
        side_effect=RuntimeError("Intent classification failed")
    )
    return mock_classifier


# =============================================================================
# Adapter Fixtures
# =============================================================================


@pytest.fixture
def kafka_publisher_adapter(
    event_bus: EventBusInmemory,
) -> EventBusKafkaPublisherAdapter:
    """Create a Kafka publisher adapter backed by the in-memory event bus.

    This fixture bridges ProtocolKafkaPublisher to EventBusInmemory,
    allowing handlers to publish events that appear in the event bus
    history for test assertions.

    Args:
        event_bus: The in-memory event bus fixture.

    Returns:
        An adapter implementing ProtocolKafkaPublisher.
    """
    return EventBusKafkaPublisherAdapter(event_bus)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TEST_TOPIC_PREFIX",
    "EventBusKafkaPublisherAdapter",
    "event_bus",
    "input_topic",
    "kafka_publisher_adapter",
    "mock_failing_intent_classifier",
    "mock_intent_classifier",
    "output_topic",
    "sample_session_start_event",
    "sample_stop_event",
    "sample_user_prompt_event",
]
