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
    from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_promote_pattern import (
        handle_promote_pattern,
    )
    from omniintelligence.nodes.node_pattern_storage_effect.constants import (
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

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from psycopg import AsyncConnection

from omniintelligence.nodes.node_pattern_storage_effect.constants import (
    VALID_TRANSITIONS,
    is_valid_transition,
)
from omniintelligence.nodes.node_pattern_storage_effect.handlers.model_state_transition import (
    DEFAULT_ACTOR,
    ModelStateTransition,
)
from omniintelligence.nodes.node_pattern_storage_effect.handlers.protocol_pattern_state_manager import (
    ProtocolPatternStateManager,
)
from omniintelligence.nodes.node_pattern_storage_effect.models.model_pattern_metrics_snapshot import (
    ModelPatternMetricsSnapshot,
)
from omniintelligence.nodes.node_pattern_storage_effect.models.model_pattern_promoted_event import (
    ModelPatternPromotedEvent,
)
from omniintelligence.nodes.node_pattern_storage_effect.models.model_pattern_state import (
    EnumPatternState,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Pure Validation (Database-Free) - CONSOLIDATED
# =============================================================================
#
# The canonical validate_promotion_transition() function and TransitionValidationResult
# are defined in constants.py as the single source of truth.
#
# For backwards compatibility, we re-export them here and provide an alias
# for PromotionValidationResult (deprecated, use TransitionValidationResult).
#
# Reference: OMN-1668 consolidation task
# =============================================================================

from omniintelligence.nodes.node_pattern_storage_effect.constants import (
    TransitionValidationResult,
    validate_promotion_transition,
)

# Backwards compatibility alias (deprecated)
# Use TransitionValidationResult from constants.py instead
PromotionValidationResult = TransitionValidationResult
"""Deprecated alias for TransitionValidationResult.

This alias is provided for backwards compatibility. New code should use
TransitionValidationResult from constants.py directly.
"""

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
                    ", ".join(s.value for s in valid_targets)
                    if valid_targets
                    else "none (terminal)"
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
# Result Type
# =============================================================================

# Error codes for structured error results
ERROR_CODE_PATTERN_NOT_FOUND: Final[str] = "PATTERN_NOT_FOUND"
"""Error code when a pattern does not exist in the state manager."""

ERROR_CODE_INVALID_TRANSITION: Final[str] = "INVALID_TRANSITION"
"""Error code when a state transition violates governance rules."""


@dataclass(frozen=True)
class PromotePatternResult:
    """Result of a pattern promotion operation.

    Follows the structured error pattern used by StorePatternResult.
    Handlers must return structured errors instead of raising domain exceptions.

    Attributes:
        success: Whether the promotion succeeded.
        event: The promotion event if successful.
        error_code: Machine-readable error code if failed.
            Standard codes:
            - "PATTERN_NOT_FOUND": Pattern does not exist
            - "INVALID_TRANSITION": State transition not allowed
        error_message: Human-readable error message if failed.
        pattern_id: The pattern ID that was operated on (always set).
        from_state: The state the pattern was in (None if not found).
        to_state: The requested target state.
    """

    success: bool
    event: ModelPatternPromotedEvent | None = None
    error_code: str | None = None
    error_message: str | None = None
    pattern_id: UUID | None = None
    from_state: EnumPatternState | None = None
    to_state: EnumPatternState | None = None


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
    metadata: dict[str, object] | None = None,
) -> PromotePatternResult:
    """Handle pattern state promotion with audit trail.

    This function orchestrates the pattern promotion workflow:
    1. Get current state from state manager
    2. Validate the transition is allowed
    3. Update state in database
    4. Record transition in audit table
    5. Return result with event for Kafka broadcast

    Returns structured errors instead of raising domain exceptions,
    following the handler error pattern documented in CLAUDE.md.

    Args:
        pattern_id: The pattern to promote.
        to_state: The target state for the promotion.
        reason: Human-readable reason for the promotion.
        metrics_snapshot: Optional metrics snapshot at promotion time.
            If not provided, the event will have metrics_snapshot=None,
            clearly indicating "no metrics captured" in the audit trail.
        state_manager: State manager for database operations (required).
            Must be provided to perform actual state transitions.
        actor: Identifier of the entity triggering the promotion.
            Defaults to "system".
        correlation_id: Optional correlation ID for distributed tracing.
        domain: Optional domain of the pattern (for audit context).
        signature_hash: Optional signature hash (for audit context).
        metadata: Optional additional context for the audit record.
        conn: Database connection for transaction control. All operations use
            this connection for atomic idempotency + state update.

    Returns:
        PromotePatternResult with success=True and event on success,
        or success=False with error_code and error_message on failure.

    Example:
        >>> result = await handle_promote_pattern(
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
        >>> result.success
        True
        >>> result.event.from_state
        <EnumPatternState.CANDIDATE: 'candidate'>
        >>> result.event.to_state
        <EnumPatternState.PROVISIONAL: 'provisional'>
    """
    promoted_at = datetime.now(UTC)
    event_id = uuid4()

    # Step 1: Get current state
    from_state = await state_manager.get_current_state(pattern_id, conn=conn)
    if from_state is None:
        error_msg = f"Pattern {pattern_id} not found"
        logger.warning(
            "Promote pattern failed: pattern not found",
            extra={"pattern_id": str(pattern_id)},
        )
        return PromotePatternResult(
            success=False,
            error_code=ERROR_CODE_PATTERN_NOT_FOUND,
            error_message=error_msg,
            pattern_id=pattern_id,
            from_state=None,
            to_state=to_state,
        )

    # Step 2: Validate transition
    if not is_valid_transition(from_state, to_state):
        valid_targets = VALID_TRANSITIONS.get(from_state, [])
        valid_str = (
            ", ".join(s.value for s in valid_targets)
            if valid_targets
            else "none (terminal)"
        )
        error_msg = (
            f"Invalid transition for pattern {pattern_id}: "
            f"{from_state.value} -> {to_state.value}. "
            f"Valid targets from {from_state.value}: {valid_str}"
        )
        logger.warning(
            "Promote pattern failed: invalid transition",
            extra={
                "pattern_id": str(pattern_id),
                "from_state": from_state.value,
                "to_state": to_state.value,
                "valid_targets": valid_str,
            },
        )
        return PromotePatternResult(
            success=False,
            error_code=ERROR_CODE_INVALID_TRANSITION,
            error_message=error_msg,
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

    # Step 5: Return result with event for Kafka broadcast
    # Pass metrics_snapshot as-is (None indicates "no metrics captured")
    event = ModelPatternPromotedEvent(
        pattern_id=pattern_id,
        from_state=from_state,
        to_state=to_state,
        reason=reason,
        metrics_snapshot=metrics_snapshot,
        promoted_at=promoted_at,
        correlation_id=correlation_id,
        actor=actor,
    )
    return PromotePatternResult(
        success=True,
        event=event,
        pattern_id=pattern_id,
        from_state=from_state,
        to_state=to_state,
    )


__all__ = [
    "DEFAULT_ACTOR",
    "ERROR_CODE_INVALID_TRANSITION",
    "ERROR_CODE_PATTERN_NOT_FOUND",
    "ModelStateTransition",
    "PatternNotFoundError",
    "PatternStateTransitionError",
    "PromotePatternResult",
    # Backwards compatibility alias (deprecated, use TransitionValidationResult)
    "PromotionValidationResult",
    "ProtocolPatternStateManager",
    # Re-exported from constants.py (canonical source)
    "TransitionValidationResult",
    "handle_promote_pattern",
    "validate_promotion_transition",
]
