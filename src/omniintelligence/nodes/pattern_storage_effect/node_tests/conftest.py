# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for pattern_storage_effect node tests.

Provides mock implementations of ProtocolPatternStore and
ProtocolPatternStateManager for unit testing governance invariants
without requiring a real database connection.

Reference:
    - OMN-1668: Pattern storage effect acceptance criteria
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

if TYPE_CHECKING:
    from psycopg import AsyncConnection

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
    PatternStorageGovernance,
)


# =============================================================================
# Mock Protocol Implementations
# =============================================================================


class MockPatternStore:
    """Mock implementation of ProtocolPatternStore for testing.

    Simulates a pattern database with in-memory storage. Supports
    all protocol methods for testing governance invariants and
    idempotency behavior.

    Attributes:
        patterns: In-memory storage of patterns.
        idempotency_map: Map of (pattern_id, signature) -> stored_id for idempotency.
    """

    def __init__(self) -> None:
        """Initialize the mock store with empty storage."""
        self.patterns: dict[UUID, dict[str, Any]] = {}
        self.idempotency_map: dict[tuple[UUID, str], UUID] = {}
        self._version_tracker: dict[tuple[str, str], int] = {}

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
        metadata: dict[str, Any] | None = None,
        conn: AsyncConnection,
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
        conn: AsyncConnection,
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
        conn: AsyncConnection,
    ) -> UUID | None:
        """Check if a pattern exists by idempotency key."""
        return self.idempotency_map.get((pattern_id, signature))

    async def set_previous_not_current(
        self,
        domain: str,
        signature: str,
        conn: AsyncConnection,
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
        conn: AsyncConnection,
    ) -> int | None:
        """Get the latest version number for a pattern lineage."""
        return self._version_tracker.get((domain, signature))

    async def get_stored_at(
        self,
        pattern_id: UUID,
        conn: AsyncConnection,
    ) -> datetime | None:
        """Get the original stored_at timestamp for a pattern.

        Used for idempotent returns to provide consistent timestamps.

        Args:
            pattern_id: The pattern to query.
            conn: Database connection (unused in mock).

        Returns:
            The original stored_at timestamp, or None if not found.
        """
        pattern = self.patterns.get(pattern_id)
        if pattern is not None:
            return pattern.get("stored_at")
        return None

    def reset(self) -> None:
        """Reset all storage for test isolation."""
        self.patterns.clear()
        self.idempotency_map.clear()
        self._version_tracker.clear()


class MockPatternStateManager:
    """Mock implementation of ProtocolPatternStateManager for testing.

    Simulates pattern state management with in-memory storage.
    Supports get/update state and transition recording.

    Attributes:
        states: Map of pattern_id to current state.
        transitions: List of recorded state transitions.
    """

    def __init__(self) -> None:
        """Initialize the mock state manager."""
        self.states: dict[UUID, EnumPatternState] = {}
        self.transitions: list[ModelStateTransition] = []

    async def get_current_state(
        self, pattern_id: UUID, conn: AsyncConnection
    ) -> EnumPatternState | None:
        """Get the current state of a pattern."""
        return self.states.get(pattern_id)

    async def update_state(
        self,
        pattern_id: UUID,
        new_state: EnumPatternState,
        conn: AsyncConnection,
    ) -> None:
        """Update the state of a pattern."""
        self.states[pattern_id] = new_state

    async def record_transition(
        self, transition: ModelStateTransition, conn: AsyncConnection
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


# =============================================================================
# Protocol Verification
# =============================================================================

# Verify mock implementations conform to protocols
assert isinstance(MockPatternStore(), ProtocolPatternStore)
assert isinstance(MockPatternStateManager(), ProtocolPatternStateManager)


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
    actor: str | None = "test_actor",
    source_run_id: str | None = "test_run_001",
    tags: list[str] | None = None,
    learning_context: str | None = "unit_test",
) -> ModelPatternStorageInput:
    """Create a valid ModelPatternStorageInput for testing.

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
        signature_hash = f"hash_{pattern_id.hex[:16]}"
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
            tags=tags or ["test"],
            learning_context=learning_context,
        ),
        learned_at=datetime.now(UTC),
    )


def create_low_confidence_input(
    confidence: float = 0.3,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create input dict with low confidence for validation bypass testing.

    Since ModelPatternStorageInput validates at model level, we create
    a dict that bypasses Pydantic validation for testing the handler's
    governance layer directly.

    Args:
        confidence: Low confidence value (< 0.5).
        **kwargs: Additional fields to override.

    Returns:
        Dict representation of input with low confidence.
    """
    pattern_id = kwargs.get("pattern_id", uuid4())
    signature_hash = kwargs.get("signature_hash", f"hash_{pattern_id.hex[:16]}")

    base = {
        "pattern_id": pattern_id,
        "signature": kwargs.get("signature", "def.*return.*None"),
        "signature_hash": signature_hash,
        "domain": kwargs.get("domain", "code_patterns"),
        "confidence": confidence,
        "version": kwargs.get("version", 1),
        "correlation_id": kwargs.get("correlation_id", uuid4()),
        "metadata": {
            "actor": kwargs.get("actor", "test_actor"),
            "source_run_id": kwargs.get("source_run_id", "test_run_001"),
            "tags": kwargs.get("tags", ["test"]),
            "learning_context": kwargs.get("learning_context", "unit_test"),
            "additional_attributes": {},
        },
        "learned_at": datetime.now(UTC).isoformat(),
    }
    return base


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
def minimum_confidence_input() -> ModelPatternStorageInput:
    """Provide input at exactly the minimum confidence threshold."""
    return create_valid_input(confidence=PatternStorageGovernance.MIN_CONFIDENCE)


@pytest.fixture
def high_confidence_input() -> ModelPatternStorageInput:
    """Provide input with high confidence score."""
    return create_valid_input(confidence=0.95)


@pytest.fixture
def sample_pattern_id() -> UUID:
    """Provide a sample pattern UUID for testing."""
    return uuid4()


@pytest.fixture
def correlation_id() -> UUID:
    """Provide a correlation ID for distributed tracing tests."""
    return uuid4()


@pytest.fixture
def mock_conn() -> MagicMock:
    """Provide a mock database connection for testing.

    Returns a MagicMock configured with common AsyncConnection methods.
    This enables testing handlers without a real database connection
    while maintaining realistic async behavior.

    The mock includes:
    - execute: AsyncMock for query execution
    - cursor: MagicMock for cursor operations

    Note: This is intentionally minimal - add methods as needed
    for specific test scenarios.
    """
    mock = MagicMock()
    mock.execute = AsyncMock()
    mock.cursor = MagicMock()
    mock.cursor.return_value.__aenter__ = AsyncMock()
    mock.cursor.return_value.__aexit__ = AsyncMock()
    return mock
