# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern state promotion handler for pattern storage effect node.

This module provides the handler for pattern state transitions with a complete
audit trail. Patterns progress through states: CANDIDATE -> PROVISIONAL -> VALIDATED.

State Transition Rules:
    - CANDIDATE -> PROVISIONAL: Pattern passes initial verification
    - PROVISIONAL -> VALIDATED: Pattern meets all validation criteria
    - VALIDATED is terminal (no further transitions)

Audit Trail:
    - All transitions are recorded in the pattern_state_transitions DB table
    - Each transition emits a ModelPatternPromotedEvent for Kafka broadcast
    - Event ID provides idempotency key for deduplication

Design Decisions:
    - Protocol-based state manager for testability (dependency injection)
    - Valid transitions are hard-coded as governance rules (not configurable)
    - Metrics snapshot captures justification for promotion decisions
    - Actor field tracks who/what triggered the promotion

Reference:
    - OMN-1668: Pattern state transitions with audit trail

Usage:
    from omniintelligence.nodes.pattern_storage_effect.handlers.handler_promote_pattern import (
        handle_promote_pattern,
        is_valid_transition,
        VALID_TRANSITIONS,
    )

    # Promote a pattern
    event = await handle_promote_pattern(
        pattern_id=pattern_id,
        to_state=EnumPatternState.PROVISIONAL,
        reason="Pattern met verification criteria",
        metrics_snapshot=metrics,
        state_manager=state_manager,
        actor="verification_workflow",
    )
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final, Protocol, runtime_checkable
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.pattern_storage_effect.models.model_pattern_state import (
    EnumPatternState,
)
from omniintelligence.nodes.pattern_storage_effect.models.model_pattern_storage_output import (
    ModelPatternMetricsSnapshot,
    ModelPatternPromotedEvent,
)

# =============================================================================
# Constants
# =============================================================================

VALID_TRANSITIONS: Final[dict[EnumPatternState, list[EnumPatternState]]] = {
    EnumPatternState.CANDIDATE: [EnumPatternState.PROVISIONAL],
    EnumPatternState.PROVISIONAL: [EnumPatternState.VALIDATED],
    EnumPatternState.VALIDATED: [],  # Terminal state - no further transitions
}
"""Valid state transitions for pattern lifecycle.

This is a governance constant - not configurable to ensure consistent state
management across all pattern storage operations.

Transitions:
    CANDIDATE -> PROVISIONAL: Pattern passes initial verification
    PROVISIONAL -> VALIDATED: Pattern meets all validation criteria
    VALIDATED -> (none): Terminal state, pattern is production-ready
"""

DEFAULT_ACTOR: Final[str] = "system"
"""Default actor for state transitions when not specified."""


# =============================================================================
# Exceptions
# =============================================================================


class PatternStateTransitionError(Exception):
    """Raised when a pattern state transition is invalid.

    Error code: PATSTORE_001 - Invalid state transition (non-recoverable).

    This exception indicates an attempt to perform an invalid state transition
    (e.g., CANDIDATE -> VALIDATED, or VALIDATED -> any state).
    This is a non-recoverable error - the transition violates governance rules.

    Attributes:
        pattern_id: The pattern that failed to transition.
        from_state: The current state of the pattern.
        to_state: The requested target state.
        message: Human-readable error description.

    Example:
        >>> raise PatternStateTransitionError(
        ...     pattern_id=uuid4(),
        ...     from_state=EnumPatternState.CANDIDATE,
        ...     to_state=EnumPatternState.VALIDATED,
        ... )
    """

    def __init__(
        self,
        pattern_id: UUID,
        from_state: EnumPatternState | None,
        to_state: EnumPatternState,
        message: str | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            pattern_id: The pattern that failed to transition.
            from_state: The current state of the pattern (None if not found).
            to_state: The requested target state.
            message: Optional custom error message.
        """
        self.pattern_id = pattern_id
        self.from_state = from_state
        self.to_state = to_state

        if message is None:
            if from_state is None:
                message = f"Pattern {pattern_id} not found - cannot transition to {to_state.value}"
            else:
                valid_targets = VALID_TRANSITIONS.get(from_state, [])
                valid_str = (
                    ", ".join(s.value for s in valid_targets) if valid_targets else "none (terminal)"
                )
                message = (
                    f"Invalid transition for pattern {pattern_id}: "
                    f"{from_state.value} -> {to_state.value}. "
                    f"Valid targets from {from_state.value}: {valid_str}"
                )

        super().__init__(message)


class PatternNotFoundError(Exception):
    """Raised when a pattern is not found for state transition.

    Error code: PATSTORE_002 - Pattern not found (non-recoverable).

    This exception indicates an attempt to transition a pattern that does not
    exist in the state manager.

    Attributes:
        pattern_id: The pattern that was not found.

    Example:
        >>> raise PatternNotFoundError(pattern_id=uuid4())
    """

    def __init__(self, pattern_id: UUID) -> None:
        """Initialize the exception.

        Args:
            pattern_id: The pattern that was not found.
        """
        self.pattern_id = pattern_id
        super().__init__(f"Pattern {pattern_id} not found")


# =============================================================================
# Models
# =============================================================================


class ModelStateTransition(BaseModel):
    """Audit record for a pattern state transition.

    This model represents a single state transition event recorded in the
    pattern_state_transitions database table for audit trail purposes.

    Attributes:
        id: Unique identifier for this transition record.
        pattern_id: The pattern that was transitioned.
        domain: Domain of the pattern (for lineage context).
        signature_hash: Signature hash of the pattern (for lineage context).
        from_state: Previous state before transition (None for initial state).
        to_state: New state after transition.
        reason: Human-readable reason for the transition.
        actor: Identifier of the entity that triggered the transition.
        event_id: Idempotency key for deduplication.
        metadata: Additional context as key-value pairs.
        created_at: Timestamp when the transition was recorded (UTC).

    Example:
        >>> transition = ModelStateTransition(
        ...     pattern_id=uuid4(),
        ...     domain="code_patterns",
        ...     signature_hash="abc123",
        ...     from_state=EnumPatternState.CANDIDATE,
        ...     to_state=EnumPatternState.PROVISIONAL,
        ...     reason="Pattern met verification criteria",
        ...     actor="verification_workflow",
        ...     event_id=uuid4(),
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this transition record",
    )
    pattern_id: UUID = Field(
        ...,
        description="The pattern that was transitioned",
    )
    domain: str | None = Field(
        default=None,
        description="Domain of the pattern (for lineage context)",
    )
    signature_hash: str | None = Field(
        default=None,
        description="Signature hash of the pattern (for lineage context)",
    )
    from_state: EnumPatternState | None = Field(
        ...,
        description="Previous state before transition (None for initial state)",
    )
    to_state: EnumPatternState = Field(
        ...,
        description="New state after transition",
    )
    reason: str = Field(
        ...,
        min_length=1,
        description="Human-readable reason for the transition",
    )
    actor: str = Field(
        default=DEFAULT_ACTOR,
        min_length=1,
        description="Identifier of the entity that triggered the transition",
    )
    event_id: UUID = Field(
        default_factory=uuid4,
        description="Idempotency key for deduplication",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context as key-value pairs",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the transition was recorded (UTC)",
    )


# =============================================================================
# Protocols
# =============================================================================


@runtime_checkable
class ProtocolPatternStateManager(Protocol):
    """Protocol for pattern state management operations.

    This protocol defines the interface for managing pattern states in
    a storage backend (database). Implementations must provide methods
    for reading current state, updating state, and recording transitions.

    The protocol is runtime-checkable for isinstance() validation.

    IMPORTANT: Implementations MUST ensure that update_state() and record_transition()
    are executed atomically (within a single database transaction). If record_transition
    fails after update_state succeeds, the pattern state would be updated without an
    audit trail, violating governance compliance requirements.

    Usage:
        class PostgresPatternStateManager:
            async def get_current_state(self, pattern_id: UUID) -> EnumPatternState | None:
                # Query database for current state
                ...

            async def update_state(self, pattern_id: UUID, new_state: EnumPatternState) -> None:
                # Update pattern state in database
                ...

            async def record_transition(self, transition: ModelStateTransition) -> None:
                # Insert transition record into audit table
                ...

        state_manager = PostgresPatternStateManager(connection)
        assert isinstance(state_manager, ProtocolPatternStateManager)
    """

    async def get_current_state(self, pattern_id: UUID) -> EnumPatternState | None:
        """Get the current state of a pattern.

        Args:
            pattern_id: The pattern to query.

        Returns:
            The current state of the pattern, or None if not found.
        """
        ...

    async def update_state(
        self,
        pattern_id: UUID,
        new_state: EnumPatternState,
    ) -> None:
        """Update the state of a pattern.

        Args:
            pattern_id: The pattern to update.
            new_state: The new state to set.

        Raises:
            PatternNotFoundError: If the pattern does not exist.
        """
        ...

    async def record_transition(self, transition: ModelStateTransition) -> None:
        """Record a state transition in the audit table.

        Args:
            transition: The transition record to insert.

        Raises:
            Exception: If the insert fails (e.g., duplicate event_id).
        """
        ...


# =============================================================================
# Validation Functions
# =============================================================================


def is_valid_transition(
    from_state: EnumPatternState,
    to_state: EnumPatternState,
) -> bool:
    """Check if a state transition is valid.

    Valid transitions are defined by the VALID_TRANSITIONS constant:
        - CANDIDATE -> PROVISIONAL
        - PROVISIONAL -> VALIDATED
        - VALIDATED -> (none, terminal state)

    Args:
        from_state: The current state.
        to_state: The requested target state.

    Returns:
        True if the transition is valid, False otherwise.

    Example:
        >>> is_valid_transition(EnumPatternState.CANDIDATE, EnumPatternState.PROVISIONAL)
        True
        >>> is_valid_transition(EnumPatternState.CANDIDATE, EnumPatternState.VALIDATED)
        False
        >>> is_valid_transition(EnumPatternState.VALIDATED, EnumPatternState.CANDIDATE)
        False
    """
    valid_targets = VALID_TRANSITIONS.get(from_state, [])
    return to_state in valid_targets


def get_valid_targets(from_state: EnumPatternState) -> list[EnumPatternState]:
    """Get the valid target states for a given state.

    Args:
        from_state: The current state.

    Returns:
        List of valid target states (empty for terminal states).

    Example:
        >>> get_valid_targets(EnumPatternState.CANDIDATE)
        [<EnumPatternState.PROVISIONAL: 'provisional'>]
        >>> get_valid_targets(EnumPatternState.VALIDATED)
        []
    """
    return list(VALID_TRANSITIONS.get(from_state, []))


# =============================================================================
# Main Handler
# =============================================================================


async def handle_promote_pattern(
    pattern_id: UUID,
    to_state: EnumPatternState,
    reason: str,
    metrics_snapshot: ModelPatternMetricsSnapshot | None = None,
    *,
    state_manager: ProtocolPatternStateManager | None = None,
    actor: str = DEFAULT_ACTOR,
    correlation_id: UUID | None = None,
    domain: str | None = None,
    signature_hash: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ModelPatternPromotedEvent:
    """Handle pattern state promotion with audit trail.

    This function orchestrates the pattern promotion workflow:
    1. Get current state from state manager
    2. Validate the transition is allowed
    3. Update state in database
    4. Record transition in audit table
    5. Return event for Kafka broadcast

    Args:
        pattern_id: The pattern to promote.
        to_state: The target state for the promotion.
        reason: Human-readable reason for the promotion.
        metrics_snapshot: Optional metrics snapshot at promotion time.
            If not provided, the event will have metrics_snapshot=None,
            clearly indicating "no metrics captured" in the audit trail.
        state_manager: Optional state manager for database operations.
            If not provided, only validation is performed (dry-run mode).
        actor: Identifier of the entity triggering the promotion.
            Defaults to "system".
        correlation_id: Optional correlation ID for distributed tracing.
        domain: Optional domain of the pattern (for audit context).
        signature_hash: Optional signature hash (for audit context).
        metadata: Optional additional context for the audit record.

    Returns:
        ModelPatternPromotedEvent ready for Kafka broadcast.

    Raises:
        PatternNotFoundError: If the pattern does not exist in state manager.
        PatternStateTransitionError: If the transition is invalid.

    Example:
        >>> event = await handle_promote_pattern(
        ...     pattern_id=pattern_id,
        ...     to_state=EnumPatternState.PROVISIONAL,
        ...     reason="Pattern met verification criteria",
        ...     metrics_snapshot=ModelPatternMetricsSnapshot(
        ...         confidence=0.85,
        ...         match_count=10,
        ...         success_rate=0.9,
        ...     ),
        ...     state_manager=state_manager,
        ...     actor="verification_workflow",
        ... )
        >>> event.from_state
        <EnumPatternState.CANDIDATE: 'candidate'>
        >>> event.to_state
        <EnumPatternState.PROVISIONAL: 'provisional'>

    Note:
        If state_manager is None, the function performs validation only
        (dry-run mode). This is useful for testing validation logic without
        a database connection.
    """
    promoted_at = datetime.now(UTC)
    event_id = uuid4()

    # Step 1: Get current state
    from_state: EnumPatternState | None = None
    if state_manager is not None:
        from_state = await state_manager.get_current_state(pattern_id)
        if from_state is None:
            raise PatternNotFoundError(pattern_id)
    else:
        # Dry-run mode: infer from_state based on to_state
        # This allows validation testing without a state manager
        if to_state == EnumPatternState.PROVISIONAL:
            from_state = EnumPatternState.CANDIDATE
        elif to_state == EnumPatternState.VALIDATED:
            from_state = EnumPatternState.PROVISIONAL
        else:
            # to_state is CANDIDATE - this is only valid as initial state
            # which is not a promotion, so we reject it
            raise PatternStateTransitionError(
                pattern_id=pattern_id,
                from_state=None,
                to_state=to_state,
                message=f"Cannot promote to {to_state.value} - this is an initial state, not a promotion target",
            )

    # Step 2: Validate transition
    if not is_valid_transition(from_state, to_state):
        raise PatternStateTransitionError(
            pattern_id=pattern_id,
            from_state=from_state,
            to_state=to_state,
        )

    # Step 3 & 4: Update state and record transition (if state_manager provided)
    if state_manager is not None:
        # Update state in database
        await state_manager.update_state(pattern_id, to_state)

        # Record transition in audit table
        transition = ModelStateTransition(
            pattern_id=pattern_id,
            domain=domain,
            signature_hash=signature_hash,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            actor=actor,
            event_id=event_id,
            metadata=metadata or {},
            created_at=promoted_at,
        )
        await state_manager.record_transition(transition)

    # Step 5: Return event for Kafka broadcast
    # Pass metrics_snapshot as-is (None indicates "no metrics captured")
    return ModelPatternPromotedEvent(
        pattern_id=pattern_id,
        from_state=from_state,
        to_state=to_state,
        reason=reason,
        metrics_snapshot=metrics_snapshot,
        promoted_at=promoted_at,
        correlation_id=correlation_id,
        actor=actor,
    )


__all__ = [
    "DEFAULT_ACTOR",
    "VALID_TRANSITIONS",
    "ModelStateTransition",
    "PatternNotFoundError",
    "PatternStateTransitionError",
    "ProtocolPatternStateManager",
    "get_valid_targets",
    "handle_promote_pattern",
    "is_valid_transition",
]
