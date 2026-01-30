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

from typing import Final

from omniintelligence.nodes.pattern_storage_effect.models.model_pattern_state import (
    EnumPatternState,
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


__all__ = [
    "VALID_TRANSITIONS",
    "get_valid_targets",
    "is_valid_transition",
]
