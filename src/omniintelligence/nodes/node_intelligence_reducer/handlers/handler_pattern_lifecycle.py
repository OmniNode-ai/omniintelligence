# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for PATTERN_LIFECYCLE FSM transitions in the Intelligence Reducer.

This module implements pure FSM transition logic for pattern lifecycle states:
    CANDIDATE -> VALIDATED -> DEPRECATED

Note: PROVISIONAL is a LEGACY status - only outbound transitions allowed.
Legacy patterns in PROVISIONAL can transition to VALIDATED or DEPRECATED,
but new patterns cannot transition TO PROVISIONAL.

The handler:
    1. Validates the transition against contract.yaml FSM rules
    2. Checks guard conditions (e.g., admin required for manual_reenable)
    3. Returns structured success with ModelPayloadUpdatePatternStatus intent
    4. Returns structured error on invalid transitions (never raises)

FSM Transitions (from contract.yaml):
    - provisional -> validated (trigger: promote) [LEGACY: outbound only]
    - candidate -> validated (trigger: promote_direct)
    - candidate -> deprecated (trigger: deprecate)
    - provisional -> deprecated (trigger: deprecate) [LEGACY: outbound only]
    - validated -> deprecated (trigger: deprecate)
    - deprecated -> candidate (trigger: manual_reenable) REQUIRES actor_type='admin'

Design Principles:
    - Pure functions with no side effects
    - Return structured errors, never raise domain exceptions
    - Declarative FSM transitions from contract.yaml
    - Protocol-based for testability

Reference:
    - OMN-1805: Pattern lifecycle state machine implementation
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.nodes.node_intelligence_reducer.models.model_payload_update_pattern_status import (
    ModelPayloadUpdatePatternStatus,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input import (
    ModelReducerInputPatternLifecycle,
)


# =============================================================================
# FSM Transition Table
# =============================================================================
# Extracted from contract.yaml state_machine.transitions for PATTERN_LIFECYCLE
#
# Key: (from_state, trigger)
# Value: to_state
#
# This table is the SINGLE SOURCE OF TRUTH for valid transitions.
# Any changes must be reflected in contract.yaml.
#
# TODO(OMN-1887): Derive FSM transition tables from contract.yaml at runtime.
# The current hard-coded approach is acceptable for MVP and provides clear,
# auditable transition logic. In a future iteration, these tables should be
# dynamically loaded from contract.yaml to ensure single-source-of-truth
# consistency and eliminate manual synchronization between code and contract.
# See: node_intelligence_reducer/contract.yaml state_machine.transitions
# Ticket: https://linear.app/omninode/issue/OMN-1887

VALID_TRANSITIONS: Final[dict[tuple[str, str], str]] = {
    # NOTE: candidate -> provisional REMOVED - PROVISIONAL is LEGACY (outbound only)
    # provisional -> validated via promote (LEGACY: outbound only)
    ("provisional", "promote"): "validated",
    # candidate -> validated via promote_direct
    ("candidate", "promote_direct"): "validated",
    # candidate -> deprecated via deprecate
    ("candidate", "deprecate"): "deprecated",
    # provisional -> deprecated via deprecate (LEGACY: outbound only)
    ("provisional", "deprecate"): "deprecated",
    # validated -> deprecated via deprecate
    ("validated", "deprecate"): "deprecated",
    # deprecated -> candidate via manual_reenable (admin only)
    ("deprecated", "manual_reenable"): "candidate",
}

# =============================================================================
# Guard Conditions
# =============================================================================
# Certain transitions require specific guard conditions to be met.
# Key: (from_state, trigger)
# Value: (field, required_value, error_message)

GUARD_CONDITIONS: Final[dict[tuple[str, str], tuple[str, str, str]]] = {
    ("deprecated", "manual_reenable"): (
        "actor_type",
        "admin",
        "manual_reenable requires actor_type='admin'",
    ),
}

# Valid pattern lifecycle states
VALID_STATES: Final[frozenset[str]] = frozenset(
    {
        "candidate",
        "provisional",
        "validated",
        "deprecated",
    }
)

# Valid triggers for PATTERN_LIFECYCLE FSM
# NOTE: validation_passed REMOVED - had no valid transition after PROVISIONAL deprecation
VALID_TRIGGERS: Final[frozenset[str]] = frozenset(
    {
        "promote",
        "promote_direct",
        "deprecate",
        "manual_reenable",
    }
)


# =============================================================================
# Result Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class PatternLifecycleTransitionResult:
    """Result of a pattern lifecycle transition validation.

    This dataclass provides a structured result for the handler, containing
    either a success with the intent payload or an error with details.

    Attributes:
        success: Whether the transition is valid.
        intent: The ModelPayloadUpdatePatternStatus intent to emit (if success).
        error_code: Machine-readable error code (if error).
        error_message: Human-readable error message (if error).
        from_status: The source status.
        to_status: The target status (if valid).
        trigger: The trigger that was attempted.
    """

    success: bool
    intent: ModelPayloadUpdatePatternStatus | None
    error_code: str | None
    error_message: str | None
    from_status: str
    to_status: str | None
    trigger: str


# Error code constants
ERROR_INVALID_PATTERN_ID: Final[str] = "INVALID_PATTERN_ID"
ERROR_INVALID_FROM_STATE: Final[str] = "INVALID_FROM_STATE"
ERROR_INVALID_TRIGGER: Final[str] = "INVALID_TRIGGER"
ERROR_INVALID_TRANSITION: Final[str] = "INVALID_TRANSITION"
ERROR_GUARD_CONDITION_FAILED: Final[str] = "GUARD_CONDITION_FAILED"
ERROR_STATE_MISMATCH: Final[str] = "STATE_MISMATCH"


# =============================================================================
# Handler Functions
# =============================================================================


def handle_pattern_lifecycle_transition(
    input_data: ModelReducerInputPatternLifecycle,
    *,
    transition_at: datetime | None = None,
) -> PatternLifecycleTransitionResult:
    """Handle a pattern lifecycle FSM transition request.

    This is the main entry point for pattern lifecycle transitions. It:
    1. Validates the from_status against valid states
    2. Validates the trigger against valid triggers
    3. Looks up the transition in VALID_TRANSITIONS
    4. Checks guard conditions (e.g., admin for manual_reenable)
    5. Builds and returns ModelPayloadUpdatePatternStatus intent

    Error Handling:
        - Returns structured error on invalid state
        - Returns structured error on invalid trigger
        - Returns structured error on invalid transition
        - Returns structured error on guard condition failure
        - Never raises domain exceptions

    Args:
        input_data: The reducer input containing transition request details.
        transition_at: When to record as transition time. Defaults to now.

    Returns:
        PatternLifecycleTransitionResult with either:
        - success=True and intent payload for valid transitions
        - success=False and error details for invalid transitions
    """
    payload = input_data.payload
    from_status = payload.from_status.lower()
    to_status = payload.to_status.lower()
    trigger = payload.trigger.lower()
    actor_type = payload.actor_type
    transition_time = transition_at or datetime.now(UTC)

    # Step 0: Validate pattern_id is a valid UUID format
    try:
        UUID(payload.pattern_id)
    except (ValueError, AttributeError):
        return _create_error_result(
            error_code=ERROR_INVALID_PATTERN_ID,
            error_message=f"pattern_id is not a valid UUID: {payload.pattern_id}",
            from_status=from_status,
            to_status=to_status,
            trigger=trigger,
        )

    # Step 1: Validate from_status is a valid PATTERN_LIFECYCLE state
    if from_status not in VALID_STATES:
        return _create_error_result(
            error_code=ERROR_INVALID_FROM_STATE,
            error_message=f"Invalid from_status '{from_status}'. "
            f"Valid states: {sorted(VALID_STATES)}",
            from_status=from_status,
            to_status=to_status,
            trigger=trigger,
        )

    # Step 2: Validate trigger is a valid PATTERN_LIFECYCLE trigger
    if trigger not in VALID_TRIGGERS:
        return _create_error_result(
            error_code=ERROR_INVALID_TRIGGER,
            error_message=f"Invalid trigger '{trigger}'. "
            f"Valid triggers: {sorted(VALID_TRIGGERS)}",
            from_status=from_status,
            to_status=to_status,
            trigger=trigger,
        )

    # Step 3: Look up transition in the valid transitions table
    transition_key = (from_status, trigger)
    expected_to_status = VALID_TRANSITIONS.get(transition_key)

    if expected_to_status is None:
        return _create_error_result(
            error_code=ERROR_INVALID_TRANSITION,
            error_message=f"Invalid transition: '{from_status}' + '{trigger}' "
            "is not a valid PATTERN_LIFECYCLE transition. "
            f"Available transitions from '{from_status}': "
            f"{_get_available_triggers(from_status)}",
            from_status=from_status,
            to_status=to_status,
            trigger=trigger,
        )

    # Step 4: Verify to_status matches expected (sanity check)
    if to_status != expected_to_status:
        return _create_error_result(
            error_code=ERROR_STATE_MISMATCH,
            error_message=f"State mismatch: trigger '{trigger}' from '{from_status}' "
            f"should result in '{expected_to_status}', but to_status='{to_status}' "
            "was provided.",
            from_status=from_status,
            to_status=to_status,
            trigger=trigger,
        )

    # Step 5: Check guard conditions
    guard = GUARD_CONDITIONS.get(transition_key)
    if guard is not None:
        field_name, required_value, guard_error_message = guard
        actual_value = getattr(payload, field_name, None)

        if actual_value != required_value:
            return _create_error_result(
                error_code=ERROR_GUARD_CONDITION_FAILED,
                error_message=f"Guard condition failed: {guard_error_message}. "
                f"Got {field_name}='{actual_value}', expected '{required_value}'.",
                from_status=from_status,
                to_status=to_status,
                trigger=trigger,
            )

    # Step 6: Build the intent payload
    # Convert string statuses back to enum values for type safety
    intent = ModelPayloadUpdatePatternStatus(
        intent_type="postgres.update_pattern_status",
        request_id=input_data.request_id,
        correlation_id=input_data.correlation_id,
        pattern_id=UUID(payload.pattern_id),
        from_status=EnumPatternLifecycleStatus(from_status),
        to_status=EnumPatternLifecycleStatus(expected_to_status),
        trigger=trigger,
        actor=payload.actor,
        reason=payload.reason,
        gate_snapshot=payload.gate_snapshot,
        transition_at=transition_time,
    )

    return PatternLifecycleTransitionResult(
        success=True,
        intent=intent,
        error_code=None,
        error_message=None,
        from_status=from_status,
        to_status=expected_to_status,
        trigger=trigger,
    )


def _create_error_result(
    *,
    error_code: str,
    error_message: str,
    from_status: str,
    to_status: str | None,
    trigger: str,
) -> PatternLifecycleTransitionResult:
    """Create an error result with structured error information.

    Args:
        error_code: Machine-readable error code.
        error_message: Human-readable error message.
        from_status: The source status that was provided.
        to_status: The target status that was provided (may be invalid).
        trigger: The trigger that was attempted.

    Returns:
        PatternLifecycleTransitionResult with success=False.
    """
    return PatternLifecycleTransitionResult(
        success=False,
        intent=None,
        error_code=error_code,
        error_message=error_message,
        from_status=from_status,
        to_status=to_status,
        trigger=trigger,
    )


def _get_available_triggers(from_status: str) -> list[str]:
    """Get list of valid triggers from a given status.

    Args:
        from_status: The source status.

    Returns:
        List of valid triggers from that status.
    """
    return sorted(
        trigger
        for (state, trigger), _ in VALID_TRANSITIONS.items()
        if state == from_status
    )


def validate_transition(
    from_status: str,
    trigger: str,
) -> tuple[bool, str | None]:
    """Validate a transition without building an intent.

    This is a pure validation function useful for checking transitions
    without the full context of a reducer input.

    Args:
        from_status: The current status (will be lowercased).
        trigger: The transition trigger (will be lowercased).

    Returns:
        Tuple of (is_valid, expected_to_status or None).
    """
    key = (from_status.lower(), trigger.lower())
    to_status = VALID_TRANSITIONS.get(key)
    return (to_status is not None, to_status)


def get_fsm_transition_table() -> dict[tuple[str, str], str]:
    """Get a copy of the FSM transition table.

    Useful for introspection and testing.

    Returns:
        Copy of VALID_TRANSITIONS dictionary.
    """
    return dict(VALID_TRANSITIONS)


def get_guard_conditions() -> dict[tuple[str, str], tuple[str, str, str]]:
    """Get a copy of the guard conditions table.

    Useful for introspection and testing.

    Returns:
        Copy of GUARD_CONDITIONS dictionary.
    """
    return dict(GUARD_CONDITIONS)


__all__ = [
    "ERROR_GUARD_CONDITION_FAILED",
    "ERROR_INVALID_FROM_STATE",
    "ERROR_INVALID_PATTERN_ID",
    "ERROR_INVALID_TRANSITION",
    "ERROR_INVALID_TRIGGER",
    "ERROR_STATE_MISMATCH",
    "GUARD_CONDITIONS",
    "VALID_STATES",
    "VALID_TRANSITIONS",
    "VALID_TRIGGERS",
    "PatternLifecycleTransitionResult",
    "get_fsm_transition_table",
    "get_guard_conditions",
    "handle_pattern_lifecycle_transition",
    "validate_transition",
]
