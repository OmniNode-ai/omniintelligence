# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Shared mock implementations for pattern storage testing.

This module provides mock implementations of ProtocolPatternStore and
ProtocolPatternStateManager for use in both unit and integration tests.
These mocks simulate in-memory database operations for testing governance
invariants and idempotency behavior without requiring real infrastructure.

Usage:
    from omniintelligence.testing import (
        MockPatternStore,
        MockPatternStateManager,
        create_valid_pattern_input,
    )

Reference:
    - OMN-1668: Pattern storage effect acceptance criteria
    - OMN-1780: Pattern storage repository contract
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from omnibase_core.types.typed_dict_pattern_storage_metadata import (
    TypedDictPatternStorageMetadata,
)

if TYPE_CHECKING:
    pass

from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_promote_pattern import (
    ModelStateTransition,
    ProtocolPatternStateManager,
)
from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_store_pattern import (
    ProtocolPatternStore,
)
from omniintelligence.nodes.node_pattern_storage_effect.models import (
    EnumPatternState,
    ModelPatternStorageInput,
    ModelPatternStorageMetadata,
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
        patterns: In-memory storage of patterns keyed by pattern_id.
        idempotency_map: Map of (pattern_id, signature_hash) -> stored_id for idempotency.

    Example:
        >>> store = MockPatternStore()
        >>> await store.store_pattern(
        ...     pattern_id=uuid4(),
        ...     signature="def.*return.*None",
        ...     signature_hash="abc123",
        ...     domain="code_patterns",
        ...     version=1,
        ...     confidence=0.85,
        ...     state=EnumPatternState.CANDIDATE,
        ...     is_current=True,
        ...     stored_at=datetime.now(UTC),
        ...     conn=mock_conn,
        ... )
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
        """Store a pattern in the mock database.

        Args:
            pattern_id: Unique identifier for this pattern instance.
            signature: The pattern signature string.
            signature_hash: Hash of the signature for deduplication.
            domain: Domain where the pattern was learned.
            version: Version number of this pattern.
            confidence: Confidence score (0.0 to 1.0).
            quality_score: Quality score (0.0 to 1.0), defaults to 0.5.
            state: Initial lifecycle state of the pattern.
            is_current: Whether this is the current version.
            stored_at: Timestamp when stored.
            actor: Entity that stored the pattern.
            source_run_id: Run that produced the pattern.
            correlation_id: Correlation ID for tracing.
            metadata: Additional pattern metadata.
            conn: Database connection (unused in mock).

        Returns:
            UUID of the stored pattern.
        """
        self.patterns[pattern_id] = {
            "pattern_id": pattern_id,
            "signature": signature,
            "signature_hash": signature_hash,
            "domain": domain,
            "version": version,
            "confidence": confidence,
            "quality_score": quality_score,
            "state": state,
            "is_current": is_current,
            "stored_at": stored_at,
            "actor": actor,
            "source_run_id": source_run_id,
            "correlation_id": correlation_id,
            "metadata": metadata or {},
        }
        # Track idempotency key (using signature_hash for stability)
        self.idempotency_map[(pattern_id, signature_hash)] = pattern_id
        # Track version (using signature_hash for stability)
        lineage_key = (domain, signature_hash)
        self._version_tracker[lineage_key] = version
        return pattern_id

    async def check_exists(
        self,
        domain: str,
        signature_hash: str,
        version: int,
        conn: Any = None,
    ) -> bool:
        """Check if a pattern exists for the given lineage and version.

        Args:
            domain: Domain to search in.
            signature_hash: Pattern signature hash.
            version: Version number to check.
            conn: Database connection (unused in mock).

        Returns:
            True if pattern exists, False otherwise.
        """
        for pattern in self.patterns.values():
            if (
                pattern["domain"] == domain
                and pattern["signature_hash"] == signature_hash
                and pattern["version"] == version
            ):
                return True
        return False

    async def check_exists_by_id(
        self,
        pattern_id: UUID,
        signature_hash: str,
        conn: Any = None,
    ) -> UUID | None:
        """Check if a pattern exists by idempotency key.

        Args:
            pattern_id: Pattern ID to check.
            signature_hash: Pattern signature hash.
            conn: Database connection (unused in mock).

        Returns:
            The pattern UUID if found, None otherwise.
        """
        return self.idempotency_map.get((pattern_id, signature_hash))

    async def set_previous_not_current(
        self,
        domain: str,
        signature_hash: str,
        conn: Any = None,
    ) -> int:
        """Set is_current = false for all previous versions.

        Args:
            domain: Domain to update.
            signature_hash: Pattern signature hash.
            conn: Database connection (unused in mock).

        Returns:
            Number of patterns updated.
        """
        updated_count = 0
        for pattern in self.patterns.values():
            if (
                pattern["domain"] == domain
                and pattern["signature_hash"] == signature_hash
                and pattern["is_current"]
            ):
                pattern["is_current"] = False
                updated_count += 1
        return updated_count

    async def get_latest_version(
        self,
        domain: str,
        signature_hash: str,
        conn: Any = None,
    ) -> int | None:
        """Get the latest version number for a pattern lineage.

        Args:
            domain: Domain to query.
            signature_hash: Pattern signature hash.
            conn: Database connection (unused in mock).

        Returns:
            The latest version number, or None if no patterns exist.
        """
        return self._version_tracker.get((domain, signature_hash))

    async def get_stored_at(
        self,
        pattern_id: UUID,
        conn: Any = None,
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

        Args:
            pattern_id: Unique identifier for this pattern instance.
            signature: The pattern signature.
            signature_hash: Hash of the signature.
            domain: Domain where the pattern was learned.
            version: Version number (should be > 1 for existing lineage).
            confidence: Confidence score.
            quality_score: Quality score (0.0 to 1.0), defaults to 0.5.
            state: Initial state of the pattern.
            is_current: Ignored - always stored as TRUE.
            stored_at: Timestamp when stored.
            actor: Entity that stored the pattern.
            source_run_id: Run that produced the pattern.
            correlation_id: Correlation ID for tracing.
            metadata: Additional pattern metadata.
            conn: Database connection (unused in mock).

        Returns:
            UUID of the stored pattern.
        """
        # Track that atomic operation was used (for test verification)
        self._atomic_transitions_count += 1

        # Atomically: set previous not current + store new pattern
        # In a real implementation, this would be a single CTE SQL statement
        for pattern in self.patterns.values():
            if (
                pattern["domain"] == domain
                and pattern["signature_hash"] == signature_hash
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
        self.idempotency_map[(pattern_id, signature_hash)] = pattern_id
        # Track version
        lineage_key = (domain, signature_hash)
        self._version_tracker[lineage_key] = version
        return pattern_id

    def reset(self) -> None:
        """Reset all storage for test isolation."""
        self.patterns.clear()
        self.idempotency_map.clear()
        self._version_tracker.clear()
        self._atomic_transitions_count = 0


class MockPatternStateManager:
    """Mock implementation of ProtocolPatternStateManager for testing.

    Simulates pattern state management with in-memory storage.
    Supports get/update state and transition recording.

    Attributes:
        states: Map of pattern_id to current state.
        transitions: List of recorded state transitions.

    Example:
        >>> manager = MockPatternStateManager()
        >>> manager.set_state(pattern_id, EnumPatternState.CANDIDATE)
        >>> await manager.update_state(pattern_id, EnumPatternState.PROVISIONAL, conn)
    """

    def __init__(self) -> None:
        """Initialize the mock state manager."""
        self.states: dict[UUID, EnumPatternState] = {}
        self.transitions: list[ModelStateTransition] = []

    async def get_current_state(
        self,
        pattern_id: UUID,
        conn: Any = None,
    ) -> EnumPatternState | None:
        """Get the current state of a pattern.

        Args:
            pattern_id: The pattern to query.
            conn: Database connection (unused in mock).

        Returns:
            The current state, or None if pattern not found.
        """
        return self.states.get(pattern_id)

    async def update_state(
        self,
        pattern_id: UUID,
        new_state: EnumPatternState,
        conn: Any = None,
    ) -> None:
        """Update the state of a pattern.

        Args:
            pattern_id: The pattern to update.
            new_state: The new state to set.
            conn: Database connection (unused in mock).
        """
        self.states[pattern_id] = new_state

    async def record_transition(
        self,
        transition: ModelStateTransition,
        conn: Any = None,
    ) -> None:
        """Record a state transition in the audit table.

        Args:
            transition: The state transition to record.
            conn: Database connection (unused in mock).
        """
        self.transitions.append(transition)

    def set_state(self, pattern_id: UUID, state: EnumPatternState) -> None:
        """Helper to set initial state for testing.

        Args:
            pattern_id: The pattern to set state for.
            state: The state to set.
        """
        self.states[pattern_id] = state

    def reset(self) -> None:
        """Reset all state for test isolation."""
        self.states.clear()
        self.transitions.clear()


# =============================================================================
# Protocol Verification
# =============================================================================

# Verify mock implementations conform to protocols at import time
assert isinstance(MockPatternStore(), ProtocolPatternStore)
assert isinstance(MockPatternStateManager(), ProtocolPatternStateManager)


# =============================================================================
# Factory Functions
# =============================================================================


def create_valid_pattern_input(
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
    learning_context: str | None = "test",
) -> ModelPatternStorageInput:
    """Create a valid ModelPatternStorageInput for testing.

    This factory function provides sensible defaults for all required fields,
    making it easy to create valid test inputs with minimal specification.

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

    Example:
        >>> input_data = create_valid_pattern_input(confidence=0.9)
        >>> input_data.confidence
        0.9
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


def create_low_confidence_input_dict(
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
            "learning_context": kwargs.get("learning_context", "test"),
            "additional_attributes": {},
        },
        "learned_at": datetime.now(UTC).isoformat(),
    }
    return base


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "MockPatternStateManager",
    "MockPatternStore",
    "create_low_confidence_input_dict",
    "create_valid_pattern_input",
]
