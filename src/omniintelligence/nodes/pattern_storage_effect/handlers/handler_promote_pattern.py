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
    )
    from omniintelligence.nodes.pattern_storage_effect.constants import (
        VALID_TRANSITIONS,
        is_valid_transition,
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

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, Protocol, runtime_checkable
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from psycopg import AsyncConnection

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.pattern_storage_effect.constants import (
    VALID_TRANSITIONS,
    is_valid_transition,
)
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

DEFAULT_ACTOR: Final[str] = "system"
"""Default actor for state transitions when not specified."""


# =============================================================================
# Pure Validation (Database-Free)
# =============================================================================


@dataclass(frozen=True, slots=True)
class PromotionValidationResult:
    """Result of validating a promotion transition without database access.

    This is a pure validation result useful for:
    - CI validation without database setup
    - State machine documentation and testing
    - Pre-flight checks before database operations
    - Debugging state machine logic

    Attributes:
        is_valid: True if the transition is allowed by governance rules.
        from_state: The source state for the transition.
        to_state: The requested target state.
        error_message: Human-readable error message (None if valid).
        valid_targets: List of valid target states from from_state (None if valid).

    Example:
        >>> result = validate_promotion_transition(
        ...     EnumPatternState.CANDIDATE,
        ...     EnumPatternState.PROVISIONAL,
        ... )
        >>> result.is_valid
        True
        >>> result.error_message is None
        True

        >>> result = validate_promotion_transition(
        ...     EnumPatternState.CANDIDATE,
        ...     EnumPatternState.VALIDATED,
        ... )
        >>> result.is_valid
        False
        >>> result.valid_targets
        [<EnumPatternState.PROVISIONAL: 'provisional'>]
    """

    is_valid: bool
    from_state: EnumPatternState
    to_state: EnumPatternState
    error_message: str | None = None
    valid_targets: list[EnumPatternState] | None = None


def validate_promotion_transition(
    from_state: EnumPatternState,
    to_state: EnumPatternState,
) -> PromotionValidationResult:
    """Validate a promotion transition without database access.

    This is a pure validation function useful for:
    - CI validation without database setup
    - State machine documentation and testing
    - Pre-flight checks before database operations
    - Debugging state machine logic

    The function reuses the canonical is_valid_transition() logic from constants.py
    to ensure consistent validation across all code paths.

    Args:
        from_state: Current state of the pattern.
        to_state: Target state for promotion.

    Returns:
        PromotionValidationResult with validation outcome.
        - If valid: is_valid=True, error_message=None, valid_targets=None
        - If invalid: is_valid=False, error_message describes the issue,
          valid_targets lists allowed transitions from from_state

    Example:
        >>> # Valid transition
        >>> result = validate_promotion_transition(
        ...     EnumPatternState.CANDIDATE,
        ...     EnumPatternState.PROVISIONAL,
        ... )
        >>> assert result.is_valid
        >>> assert result.error_message is None

        >>> # Invalid transition (skipping PROVISIONAL)
        >>> result = validate_promotion_transition(
        ...     EnumPatternState.CANDIDATE,
        ...     EnumPatternState.VALIDATED,
        ... )
        >>> assert not result.is_valid
        >>> assert EnumPatternState.PROVISIONAL in result.valid_targets

        >>> # Invalid transition (from terminal state)
        >>> result = validate_promotion_transition(
        ...     EnumPatternState.VALIDATED,
        ...     EnumPatternState.CANDIDATE,
        ... )
        >>> assert not result.is_valid
        >>> assert result.valid_targets == []  # Terminal state has no valid targets
    """
    # Delegate to canonical validation logic in constants.py
    if is_valid_transition(from_state, to_state):
        return PromotionValidationResult(
            is_valid=True,
            from_state=from_state,
            to_state=to_state,
            error_message=None,
            valid_targets=None,
        )

    # Invalid transition - build helpful error message
    valid_targets = VALID_TRANSITIONS.get(from_state, [])
    valid_str = (
        ", ".join(s.value for s in valid_targets) if valid_targets else "none (terminal state)"
    )
    error_message = (
        f"Invalid transition: {from_state.value} -> {to_state.value}. "
        f"Valid targets from {from_state.value}: {valid_str}"
    )

    return PromotionValidationResult(
        is_valid=False,
        from_state=from_state,
        to_state=to_state,
        error_message=error_message,
        valid_targets=list(valid_targets),
    )


# Metrics Snapshot Design Decision:
# ---------------------------------
# The metrics_snapshot parameter in handle_promote_pattern can be None.
# This is intentional and has specific semantics:
#
#   - None = "metrics were not captured at promotion time"
#             (e.g., manual promotion, legacy data, or unavailable metrics)
#
#   - Empty ModelPatternMetricsSnapshot (all zeros) = "metrics were captured
#             and they are all zero" (semantically different from "not captured")
#
# Audit Trail Implications:
#   When metrics_snapshot=None appears in audit records, it clearly indicates
#   that no metrics justification was provided for the promotion. This is
#   acceptable for certain workflows (e.g., administrative promotions) but
#   should be reviewed during audits. Callers who have metrics available
#   should always provide them for better traceability.
#
# See: handle_promote_pattern docstring for usage guidance.


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

    def __repr__(self) -> str:
        """Return a detailed representation for debugging."""
        return (
            f"{self.__class__.__name__}("
            f"pattern_id={self.pattern_id!r}, "
            f"from_state={self.from_state!r}, "
            f"to_state={self.to_state!r})"
        )


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

    def __repr__(self) -> str:
        """Return a detailed representation for debugging."""
        return f"{self.__class__.__name__}(pattern_id={self.pattern_id!r})"


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

    Transaction Control:
        All methods require a `conn` parameter for transaction control. The caller
        (e.g., infra wiring) owns the transaction spanning idempotency checks and
        pattern state operations. This ensures atomic operations.

    Usage:
        class PostgresPatternStateManager:
            async def get_current_state(
                self, pattern_id: UUID, conn: AsyncConnection
            ) -> EnumPatternState | None:
                # Query database for current state
                ...

            async def update_state(
                self,
                pattern_id: UUID,
                new_state: EnumPatternState,
                conn: AsyncConnection,
            ) -> None:
                # Update pattern state in database
                ...

            async def record_transition(
                self, transition: ModelStateTransition, conn: AsyncConnection
            ) -> None:
                # Insert transition record into audit table
                ...

        state_manager = PostgresPatternStateManager(connection)
        assert isinstance(state_manager, ProtocolPatternStateManager)
    """

    async def get_current_state(
        self,
        pattern_id: UUID,
        conn: AsyncConnection,
    ) -> EnumPatternState | None:
        """Get the current state of a pattern.

        Args:
            pattern_id: The pattern to query.
            conn: Database connection for transaction control.

        Returns:
            The current state of the pattern, or None if not found.
        """
        ...

    async def update_state(
        self,
        pattern_id: UUID,
        new_state: EnumPatternState,
        conn: AsyncConnection,
    ) -> None:
        """Update the state of a pattern.

        Args:
            pattern_id: The pattern to update.
            new_state: The new state to set.
            conn: Database connection for transaction control.

        Raises:
            PatternNotFoundError: If the pattern does not exist.
        """
        ...

    async def record_transition(
        self,
        transition: ModelStateTransition,
        conn: AsyncConnection,
    ) -> None:
        """Record a state transition in the audit table.

        Args:
            transition: The transition record to insert.
            conn: Database connection for transaction control.

        Raises:
            Exception: If the insert fails (e.g., duplicate event_id).
        """
        ...


# =============================================================================
# Main Handler
# =============================================================================


async def handle_promote_pattern(
    pattern_id: UUID,
    to_state: EnumPatternState,
    reason: str,
    metrics_snapshot: ModelPatternMetricsSnapshot | None = None,
    *,
    state_manager: ProtocolPatternStateManager,
    conn: AsyncConnection,
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
        state_manager: State manager for database operations.
            If not provided, only validation is performed (dry-run mode).
        actor: Identifier of the entity triggering the promotion.
            Defaults to "system".
        correlation_id: Optional correlation ID for distributed tracing.
        domain: Optional domain of the pattern (for audit context).
        signature_hash: Optional signature hash (for audit context).
        metadata: Optional additional context for the audit record.
        conn: Database connection for transaction control. All operations use
            this connection for atomic idempotency + state update.

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
        ...     conn=conn,
        ...     actor="verification_workflow",
        ... )
        >>> event.from_state
        <EnumPatternState.CANDIDATE: 'candidate'>
        >>> event.to_state
        <EnumPatternState.PROVISIONAL: 'provisional'>
    """
    promoted_at = datetime.now(UTC)
    event_id = uuid4()

    # Step 1: Get current state
    from_state = await state_manager.get_current_state(pattern_id, conn=conn)
    if from_state is None:
        raise PatternNotFoundError(pattern_id)

    # Step 2: Validate transition
    if not is_valid_transition(from_state, to_state):
        raise PatternStateTransitionError(
            pattern_id=pattern_id,
            from_state=from_state,
            to_state=to_state,
        )

    # Step 3 & 4: Update state and record transition (if state_manager provided)
    # -------------------------------------------------------------------------
    # ATOMICITY REQUIREMENT (CRITICAL):
    #
    # The following two operations MUST be executed within a single database
    # transaction by the ProtocolPatternStateManager implementation:
    #
    #   1. update_state() - updates the pattern's state in the patterns table
    #   2. record_transition() - inserts audit record in pattern_state_transitions
    #
    # INVARIANT AT RISK:
    #   All state transitions MUST have a corresponding audit trail record
    #   (Governance compliance requirement)
    #
    # FAILURE SCENARIO WITHOUT ATOMICITY:
    #   If update_state() succeeds but record_transition() fails:
    #   - Pattern state is changed to the new state
    #   - No audit trail record exists for this transition
    #   - RESULT: State change without audit trail (governance violation)
    #   - IMPACT: Compliance audits cannot verify transition history;
    #             debugging state issues becomes impossible
    #
    # The handler cannot enforce transaction boundaries at the protocol level.
    # Implementations of ProtocolPatternStateManager are REQUIRED to wrap these
    # operations in a database transaction. See ProtocolPatternStateManager docstring.
    #
    # TODO(OMN-1668): Consider adding a combined atomic_promote() method to the
    # protocol that accepts both state and transition data, making atomicity
    # explicit at the API level.
    # -------------------------------------------------------------------------

    # Step 3: Update state in database
    await state_manager.update_state(pattern_id, to_state, conn=conn)

    # Step 4: Record transition in audit table
    # WARNING: This MUST succeed if update_state succeeded, otherwise
    # the state change will not have an audit trail. See atomicity note above.
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
    await state_manager.record_transition(transition, conn=conn)

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
    "ModelStateTransition",
    "PatternNotFoundError",
    "PatternStateTransitionError",
    "PromotionValidationResult",
    "ProtocolPatternStateManager",
    "handle_promote_pattern",
    "validate_promotion_transition",
]
