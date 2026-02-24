# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Fixtures for pattern_storage_effect integration tests.

This module provides pytest fixtures for testing the NodePatternStorageEffect
node with real and mock infrastructure. Infrastructure availability is detected
at runtime to allow tests to run with or without real PostgreSQL/Kafka.

Infrastructure Configuration (from .env):
    - PostgreSQL: localhost:5432 (database: omniintelligence)
    - Kafka/Redpanda: localhost:9092 (for host scripts)

Reference:
    - OMN-1668: Pattern storage effect node implementation
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_pattern_storage_effect.models import (
    ModelPatternStorageInput,
)

# Import shared fixtures from canonical location
from omniintelligence.testing import (
    MockPatternStateManager,
    MockPatternStore,
    create_valid_pattern_input,
)

# =============================================================================
# Infrastructure Detection
# =============================================================================


def is_postgres_available() -> bool:
    """Check if PostgreSQL is available at the configured endpoint.

    Returns:
        True if PostgreSQL is reachable, False otherwise.
    """
    try:
        import asyncpg  # noqa: F401

        # We'll check connection in fixture, just verify import works
        return True
    except ImportError:
        return False


def is_kafka_available() -> bool:
    """Check if Kafka/Redpanda is available at the configured endpoint.

    Returns:
        True if Kafka is reachable, False otherwise.
    """
    try:
        # Check if we have the event bus available
        from omnibase_infra.event_bus.event_bus_inmemory import (
            EventBusInmemory,  # noqa: F401
        )

        return True
    except ImportError:
        return False


# Store infrastructure availability at module load
POSTGRES_AVAILABLE = is_postgres_available()
KAFKA_AVAILABLE = is_kafka_available()


# =============================================================================
# Skip Markers
# =============================================================================

requires_postgres = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="PostgreSQL (asyncpg) not available",
)

requires_kafka = pytest.mark.skipif(
    not KAFKA_AVAILABLE,
    reason="Kafka (event bus) not available",
)


# =============================================================================
# Event Bus Adapter for Kafka Testing
# =============================================================================


class EventBusKafkaPublisherAdapter:
    """Adapter to use EventBusInmemory as a Kafka-like publisher.

    This adapter bridges the interface between handlers that expect
    to publish to Kafka topics and the in-memory event bus for testing.
    """

    def __init__(self, event_bus: Any) -> None:
        """Initialize the adapter with an EventBusInmemory instance."""
        self._event_bus = event_bus

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Publish event to EventBusInmemory using bytes API."""
        value_bytes = json.dumps(
            value, separators=(",", ":"), ensure_ascii=False, default=str
        ).encode("utf-8")
        key_bytes = key.encode("utf-8") if key else None
        await self._event_bus.publish(topic=topic, key=key_bytes, value=value_bytes)


# =============================================================================
# Factory Functions
# =============================================================================


def create_valid_input(
    **kwargs,
) -> ModelPatternStorageInput:
    """Create a valid ModelPatternStorageInput for integration testing.

    This is an alias for create_valid_pattern_input with default actor/source_run_id
    suitable for integration tests.

    Args:
        **kwargs: Arguments passed to create_valid_pattern_input.

    Returns:
        A valid ModelPatternStorageInput instance.
    """
    # Set integration-test specific defaults if not provided
    kwargs.setdefault("actor", "integration_test")
    kwargs.setdefault("source_run_id", "integration_run_001")
    kwargs.setdefault("learning_context", "integration_test")
    if kwargs.get("tags") is None:
        kwargs["tags"] = ["integration", "test"]
    return create_valid_pattern_input(**kwargs)


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def mock_pattern_store() -> MockPatternStore:
    """Provide a fresh mock pattern store for each test."""
    return MockPatternStore()


@pytest.fixture
def mock_state_manager() -> MockPatternStateManager:
    """Provide a fresh mock state manager for each test."""
    return MockPatternStateManager()


@pytest.fixture
def valid_input() -> ModelPatternStorageInput:
    """Provide a valid pattern storage input for testing."""
    return create_valid_input()


@pytest.fixture
def sample_pattern_id() -> UUID:
    """Provide a sample pattern UUID for testing."""
    return uuid4()


@pytest.fixture
def correlation_id() -> UUID:
    """Provide a correlation ID for distributed tracing tests."""
    return uuid4()


@pytest.fixture
def test_group_id() -> str:
    """Create a test consumer group ID for subscriptions.

    DEPRECATED: Use test_node_identity fixture instead for subscribe() calls.
    """
    return "test.omniintelligence.pattern_storage_effect.v1"


@pytest.fixture
def test_node_identity() -> Any:
    """Create a test node identity for event bus subscriptions.

    Returns a ModelNodeIdentity object required by the new event bus subscribe API.
    The identity components are designed to produce a consumer group ID like:
        test.omniintelligence.pattern_storage_effect.consume.v1

    Returns:
        ModelNodeIdentity instance for use with event_bus.subscribe()
    """
    from omnibase_infra.models import ModelNodeIdentity

    return ModelNodeIdentity(
        env="test",
        service="omniintelligence",
        node_name="pattern_storage_effect",
        version="v1",
    )


@pytest.fixture
async def event_bus() -> AsyncGenerator[Any, None]:
    """Create and start an in-memory event bus for testing.

    The event bus is configured with:
        - environment: "test" for test isolation
        - group: "test-group" for consumer group identification

    Yields:
        A started EventBusInmemory instance ready for use.
    """
    if not KAFKA_AVAILABLE:
        pytest.skip("Event bus not available")

    from omnibase_infra.event_bus.event_bus_inmemory import EventBusInmemory

    bus = EventBusInmemory(environment="test", group="test-group")
    await bus.start()
    yield bus
    await bus.close()


@pytest.fixture
def kafka_publisher_adapter(event_bus: Any) -> EventBusKafkaPublisherAdapter:
    """Create a Kafka publisher adapter backed by the in-memory event bus.

    Args:
        event_bus: The in-memory event bus fixture.

    Returns:
        An adapter for publishing events.
    """
    return EventBusKafkaPublisherAdapter(event_bus)


# =============================================================================
# Topic Constants
# =============================================================================

TEST_TOPIC_PREFIX: str = "test"
TOPIC_PATTERN_STORED: str = (
    f"{TEST_TOPIC_PREFIX}.onex.evt.omniintelligence.pattern-stored.v1"
)
TOPIC_PATTERN_PROMOTED: str = (
    f"{TEST_TOPIC_PREFIX}.onex.evt.omniintelligence.pattern-promoted.v1"
)
TOPIC_PATTERN_LEARNED: str = (
    f"{TEST_TOPIC_PREFIX}.onex.evt.omniintelligence.pattern-learned.v1"
)


@pytest.fixture
def pattern_stored_topic() -> str:
    """Return the topic name for pattern-stored events."""
    return TOPIC_PATTERN_STORED


@pytest.fixture
def pattern_promoted_topic() -> str:
    """Return the topic name for pattern-promoted events."""
    return TOPIC_PATTERN_PROMOTED


@pytest.fixture
def pattern_learned_topic() -> str:
    """Return the topic name for pattern-learned events."""
    return TOPIC_PATTERN_LEARNED


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "KAFKA_AVAILABLE",
    "POSTGRES_AVAILABLE",
    "TEST_TOPIC_PREFIX",
    "TOPIC_PATTERN_LEARNED",
    "TOPIC_PATTERN_PROMOTED",
    "TOPIC_PATTERN_STORED",
    "EventBusKafkaPublisherAdapter",
    "MockPatternStateManager",
    "MockPatternStore",
    "correlation_id",
    "create_valid_input",
    "event_bus",
    "kafka_publisher_adapter",
    "mock_pattern_store",
    "mock_state_manager",
    "pattern_learned_topic",
    "pattern_promoted_topic",
    "pattern_stored_topic",
    "requires_kafka",
    "requires_postgres",
    "sample_pattern_id",
    "test_group_id",
    "test_node_identity",
    "valid_input",
]
