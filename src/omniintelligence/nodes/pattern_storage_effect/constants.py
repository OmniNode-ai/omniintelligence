# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""State transition constants for pattern storage effect node.

This module provides the canonical state transition rules and validation
functions for pattern lifecycle management. These are governance constants
that define the allowed state transitions in the pattern storage system.

State Transition Rules:
    - CANDIDATE -> PROVISIONAL: Pattern passes initial verification
    - PROVISIONAL -> VALIDATED: Pattern meets all validation criteria
    - VALIDATED is terminal (no further transitions)

Design Decisions:
    - Valid transitions are hard-coded as governance rules (not configurable)
    - Single source of truth for all state transition validation
    - Used by both handlers and models for consistency

Reference:
    - OMN-1668: Pattern state transitions with audit trail

Usage:
    from omniintelligence.nodes.pattern_storage_effect.constants import (
        VALID_TRANSITIONS,
        is_valid_transition,
        get_valid_targets,
    )

    # Check if transition is valid
    if is_valid_transition(EnumPatternState.CANDIDATE, EnumPatternState.PROVISIONAL):
        # Proceed with promotion
        ...

    # Get valid targets for a state
    targets = get_valid_targets(EnumPatternState.CANDIDATE)
    # Returns: [EnumPatternState.PROVISIONAL]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from omniintelligence.nodes.pattern_storage_effect.models.model_pattern_state import (
    EnumPatternState,
)


# =============================================================================
# Validation Result Model
# =============================================================================


@dataclass(frozen=True, slots=True)
class TransitionValidationResult:
    """Result of a state transition validation (dry-run).

    This dataclass provides detailed information about whether a state
    transition is valid, including error details and valid alternatives
    when the transition is invalid.

    Attributes:
        is_valid: Whether the transition is allowed.
        from_state: The source state being validated.
        to_state: The target state being validated.
        error_message: Human-readable error message if invalid, None if valid.
        valid_targets: List of valid target states from the source state.

    Example:
        >>> result = validate_promotion_transition(
        ...     from_state=EnumPatternState.CANDIDATE,
        ...     to_state=EnumPatternState.VALIDATED,
        ... )
        >>> result.is_valid
        False
        >>> result.error_message
        'Invalid transition: candidate -> validated. Valid targets: provisional'
        >>> result.valid_targets
        [<EnumPatternState.PROVISIONAL: 'provisional'>]
    """

    is_valid: bool
    from_state: EnumPatternState
    to_state: EnumPatternState
    error_message: str | None
    valid_targets: list[EnumPatternState]

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


# =============================================================================
# Validation Functions
# =============================================================================


def is_valid_transition(
    from_state: EnumPatternState,
    to_state: EnumPatternState,
) -> bool:
    """Check if a state transition is valid.

    CANONICAL SOURCE OF TRUTH: This function (and VALID_TRANSITIONS constant)
    is the single authoritative source for state transition validation.
    All handlers and models MUST delegate to this function rather than
    implementing duplicate validation logic to prevent drift.

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


def validate_promotion_transition(
    from_state: EnumPatternState,
    to_state: EnumPatternState,
) -> TransitionValidationResult:
    """Validate a state transition without performing it (dry-run).

    This function provides a dry-run validation capability that allows callers
    to check whether a transition would be valid before attempting it. Unlike
    is_valid_transition() which returns a simple boolean, this function returns
    a rich result with detailed error information and valid alternatives.

    Use Cases:
        - Pre-flight validation in UI/API before submitting promotion request
        - Debugging why a transition was rejected
        - Building suggestion systems (e.g., "Did you mean PROVISIONAL?")

    Args:
        from_state: The current state of the pattern.
        to_state: The desired target state.

    Returns:
        TransitionValidationResult with:
            - is_valid: True if transition is allowed, False otherwise
            - from_state: Echo of the source state
            - to_state: Echo of the target state
            - error_message: Human-readable error if invalid, None if valid
            - valid_targets: List of valid target states from source

    Example:
        >>> result = validate_promotion_transition(
        ...     from_state=EnumPatternState.CANDIDATE,
        ...     to_state=EnumPatternState.PROVISIONAL,
        ... )
        >>> result.is_valid
        True
        >>> result.error_message is None
        True

        >>> result = validate_promotion_transition(
        ...     from_state=EnumPatternState.CANDIDATE,
        ...     to_state=EnumPatternState.VALIDATED,
        ... )
        >>> result.is_valid
        False
        >>> 'provisional' in result.error_message.lower()
        True
    """
    valid_targets = get_valid_targets(from_state)
    is_valid = to_state in valid_targets

    if is_valid:
        return TransitionValidationResult(
            is_valid=True,
            from_state=from_state,
            to_state=to_state,
            error_message=None,
            valid_targets=valid_targets,
        )

    # Build informative error message
    if not valid_targets:
        # Terminal state - no valid targets
        error_message = (
            f"Invalid transition: {from_state.value} -> {to_state.value}. "
            f"{from_state.value.upper()} is a terminal state with no valid transitions."
        )
    else:
        # Has valid targets, but requested target is not among them
        valid_str = ", ".join(s.value for s in valid_targets)
        error_message = (
            f"Invalid transition: {from_state.value} -> {to_state.value}. "
            f"Valid targets from {from_state.value}: {valid_str}"
        )

    return TransitionValidationResult(
        is_valid=False,
        from_state=from_state,
        to_state=to_state,
        error_message=error_message,
        valid_targets=valid_targets,
    )


__all__ = [
    "TransitionValidationResult",
    "VALID_TRANSITIONS",
    "get_valid_targets",
    "is_valid_transition",
    "validate_promotion_transition",
]
