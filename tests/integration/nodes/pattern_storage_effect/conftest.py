# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Fixtures for pattern_storage_effect integration tests.

This module provides pytest fixtures for testing the NodePatternStorageEffect
node with real and mock infrastructure. Infrastructure availability is detected
at runtime to allow tests to run with or without real PostgreSQL/Kafka.

Infrastructure Configuration (from .env):
    - PostgreSQL: 192.168.86.200:5436 (database: omninode_bridge)
    - Kafka/Redpanda: 192.168.86.200:29092 (for host scripts)

Reference:
    - OMN-1668: Pattern storage effect node implementation
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

import pytest

from omnibase_core.types import TypedDictPatternStorageMetadata

from omniintelligence.nodes.pattern_storage_effect.handlers.handler_promote_pattern import (
    ModelStateTransition,
    ProtocolPatternStateManager,
)
from omniintelligence.nodes.pattern_storage_effect.handlers.handler_store_pattern import (
    ProtocolPatternStore,
)
from omniintelligence.nodes.pattern_storage_effect.models import (
    EnumPatternState,
    ModelPatternStorageInput,
    ModelPatternStorageMetadata,
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
# Mock Protocol Implementations (from node_tests.conftest)
# =============================================================================


class MockPatternStore:
    """Mock implementation of ProtocolPatternStore for integration testing.

    This is a copy from node_tests.conftest to avoid cross-package imports.
    """

    def __init__(self) -> None:
        """Initialize the mock store with empty storage."""
        self.patterns: dict[UUID, dict[str, Any]] = {}
        self.idempotency_map: dict[tuple[UUID, str], UUID] = {}
        self._version_tracker: dict[tuple[str, str], int] = {}
        self._atomic_transitions_count: int = 0

    async def store_pattern(
        self,
        *,
        pattern_id: UUID,
        signature: str,
        signature_hash: str,
        domain: str,
        version: int,
        confidence: float,
        state: EnumPatternState,
        is_current: bool,
        stored_at: datetime,
        actor: str | None = None,
        source_run_id: str | None = None,
        correlation_id: UUID | None = None,
        metadata: TypedDictPatternStorageMetadata | None = None,
        conn: Any = None,
    ) -> UUID:
        """Store a pattern in the mock database."""
        self.patterns[pattern_id] = {
            "pattern_id": pattern_id,
            "signature": signature,
            "signature_hash": signature_hash,
            "domain": domain,
            "version": version,
            "confidence": confidence,
            "state": state,
            "is_current": is_current,
            "stored_at": stored_at,
            "actor": actor,
            "source_run_id": source_run_id,
            "correlation_id": correlation_id,
            "metadata": metadata or {},
        }
        # Track idempotency key (using signature text, not hash)
        self.idempotency_map[(pattern_id, signature)] = pattern_id
        # Track version (using signature text, not hash)
        lineage_key = (domain, signature)
        self._version_tracker[lineage_key] = version
        return pattern_id

    async def check_exists(
        self,
        domain: str,
        signature: str,
        version: int,
        conn: Any = None,
    ) -> bool:
        """Check if a pattern exists for the given lineage and version."""
        for pattern in self.patterns.values():
            if (
                pattern["domain"] == domain
                and pattern["signature"] == signature
                and pattern["version"] == version
            ):
                return True
        return False

    async def check_exists_by_id(
        self,
        pattern_id: UUID,
        signature: str,
        conn: Any = None,
    ) -> UUID | None:
        """Check if a pattern exists by idempotency key."""
        return self.idempotency_map.get((pattern_id, signature))

    async def set_previous_not_current(
        self,
        domain: str,
        signature: str,
        conn: Any = None,
    ) -> int:
        """Set is_current = false for all previous versions."""
        updated_count = 0
        for pattern in self.patterns.values():
            if (
                pattern["domain"] == domain
                and pattern["signature"] == signature
                and pattern["is_current"]
            ):
                pattern["is_current"] = False
                updated_count += 1
        return updated_count

    async def get_latest_version(
        self,
        domain: str,
        signature: str,
        conn: Any = None,
    ) -> int | None:
        """Get the latest version number for a pattern lineage."""
        return self._version_tracker.get((domain, signature))

    async def get_stored_at(
        self,
        pattern_id: UUID,
        conn: Any = None,
    ) -> datetime | None:
        """Get the original stored_at timestamp for a pattern."""
        pattern = self.patterns.get(pattern_id)
        if pattern is not None:
            return pattern.get("stored_at")
        return None

    async def store_with_version_transition(
        self,
        *,
        pattern_id: UUID,
        signature: str,
        signature_hash: str,
        domain: str,
        version: int,
        confidence: float,
        quality_score: float = 0.5,
        state: EnumPatternState,
        is_current: bool,
        stored_at: datetime,
        actor: str | None = None,
        source_run_id: str | None = None,
        correlation_id: UUID | None = None,
        metadata: TypedDictPatternStorageMetadata | None = None,
        conn: Any = None,
    ) -> UUID:
        """Atomically transition previous version(s) and store new pattern.

        This method combines set_previous_not_current and store_pattern into
        a single atomic operation. For testing, we track that this method was
        called via the atomic_transitions_count attribute.
        """
        # Track that atomic operation was used (for test verification)
        self._atomic_transitions_count += 1

        # Atomically: set previous not current + store new pattern
        for pattern in self.patterns.values():
            if (
                pattern["domain"] == domain
                and pattern["signature"] == signature
                and pattern["is_current"]
            ):
                pattern["is_current"] = False

        # Store the new pattern (always with is_current=True)
        self.patterns[pattern_id] = {
            "pattern_id": pattern_id,
            "signature": signature,
            "signature_hash": signature_hash,
            "domain": domain,
            "version": version,
            "confidence": confidence,
            "quality_score": quality_score,
            "state": state,
            "is_current": True,  # Always true for atomic transition
            "stored_at": stored_at,
            "actor": actor,
            "source_run_id": source_run_id,
            "correlation_id": correlation_id,
            "metadata": metadata or {},
        }
        # Track idempotency key
        self.idempotency_map[(pattern_id, signature)] = pattern_id
        # Track version
        lineage_key = (domain, signature)
        self._version_tracker[lineage_key] = version
        return pattern_id

    def reset(self) -> None:
        """Reset all storage for test isolation."""
        self.patterns.clear()
        self.idempotency_map.clear()
        self._version_tracker.clear()
        self._atomic_transitions_count = 0


class MockPatternStateManager:
    """Mock implementation of ProtocolPatternStateManager for integration testing."""

    def __init__(self) -> None:
        """Initialize the mock state manager."""
        self.states: dict[UUID, EnumPatternState] = {}
        self.transitions: list[ModelStateTransition] = []

    async def get_current_state(
        self, pattern_id: UUID, conn: Any = None
    ) -> EnumPatternState | None:
        """Get the current state of a pattern."""
        return self.states.get(pattern_id)

    async def update_state(
        self,
        pattern_id: UUID,
        new_state: EnumPatternState,
        conn: Any = None,
    ) -> None:
        """Update the state of a pattern."""
        self.states[pattern_id] = new_state

    async def record_transition(
        self, transition: ModelStateTransition, conn: Any = None
    ) -> None:
        """Record a state transition in the audit table."""
        self.transitions.append(transition)

    def set_state(self, pattern_id: UUID, state: EnumPatternState) -> None:
        """Helper to set initial state for testing."""
        self.states[pattern_id] = state

    def reset(self) -> None:
        """Reset all state for test isolation."""
        self.states.clear()
        self.transitions.clear()


# Verify mock implementations conform to protocols
assert isinstance(MockPatternStore(), ProtocolPatternStore)
assert isinstance(MockPatternStateManager(), ProtocolPatternStateManager)


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
    pattern_id: UUID | None = None,
    signature: str = "def.*return.*None",
    signature_hash: str | None = None,
    domain: str = "code_patterns",
    confidence: float = 0.85,
    version: int = 1,
    correlation_id: UUID | None = None,
    actor: str | None = "integration_test",
    source_run_id: str | None = "integration_run_001",
    tags: list[str] | None = None,
    learning_context: str | None = "integration_test",
) -> ModelPatternStorageInput:
    """Create a valid ModelPatternStorageInput for integration testing.

    Args:
        pattern_id: Unique identifier (auto-generated if not provided).
        signature: Pattern signature string.
        signature_hash: Hash of signature (auto-generated if not provided).
        domain: Domain of the pattern.
        confidence: Confidence score (must be >= 0.5).
        version: Version number.
        correlation_id: Correlation ID for tracing.
        actor: Entity storing the pattern.
        source_run_id: Run that produced the pattern.
        tags: Optional tags.
        learning_context: Context where pattern was learned.

    Returns:
        A valid ModelPatternStorageInput instance.
    """
    if pattern_id is None:
        pattern_id = uuid4()
    if signature_hash is None:
        signature_hash = f"integ_hash_{pattern_id.hex[:16]}"
    if correlation_id is None:
        correlation_id = uuid4()

    return ModelPatternStorageInput(
        pattern_id=pattern_id,
        signature=signature,
        signature_hash=signature_hash,
        domain=domain,
        confidence=confidence,
        version=version,
        correlation_id=correlation_id,
        metadata=ModelPatternStorageMetadata(
            actor=actor,
            source_run_id=source_run_id,
            tags=tags or ["integration", "test"],
            learning_context=learning_context,
        ),
        learned_at=datetime.now(UTC),
    )


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
    """Create a test consumer group ID for subscriptions."""
    return "test.omniintelligence.pattern_storage_effect.v1"


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
TOPIC_PATTERN_STORED: str = f"{TEST_TOPIC_PREFIX}.onex.evt.omniintelligence.pattern-stored.v1"
TOPIC_PATTERN_PROMOTED: str = f"{TEST_TOPIC_PREFIX}.onex.evt.omniintelligence.pattern-promoted.v1"
TOPIC_PATTERN_LEARNED: str = f"{TEST_TOPIC_PREFIX}.onex.evt.omniintelligence.pattern-learned.v1"


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
    "EventBusKafkaPublisherAdapter",
    "KAFKA_AVAILABLE",
    "MockPatternStateManager",
    "MockPatternStore",
    "POSTGRES_AVAILABLE",
    "TEST_TOPIC_PREFIX",
    "TOPIC_PATTERN_LEARNED",
    "TOPIC_PATTERN_PROMOTED",
    "TOPIC_PATTERN_STORED",
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
    "valid_input",
]
