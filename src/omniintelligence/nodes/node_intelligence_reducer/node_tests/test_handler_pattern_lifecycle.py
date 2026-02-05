# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for pattern lifecycle FSM handler.

Tests the handler that validates pattern lifecycle transitions against the
contract.yaml FSM rules. This handler is a pure function that:
    1. Validates from_status against valid states
    2. Validates trigger against valid triggers
    3. Looks up transition in VALID_TRANSITIONS table
    4. Checks guard conditions (e.g., admin for manual_reenable)
    5. Returns structured success with ModelPayloadUpdatePatternStatus intent
    6. Returns structured error for invalid transitions (never raises)

Test organization:
1. Valid Transitions - All 6 valid FSM transitions (PROVISIONAL is LEGACY - inbound blocked)
2. Invalid State Tests - Unknown from_status values
3. Invalid Trigger Tests - Unknown trigger values
4. Invalid Transition Tests - Valid state/trigger with no transition
5. State Mismatch Tests - Transition exists but to_status doesn't match
6. Guard Condition Tests - admin requirement for manual_reenable
7. Intent Verification - Correct population of intent fields
8. Helper Function Tests - validate_transition, get_fsm_transition_table
9. Case Sensitivity Tests - Lowercase normalization

Reference:
    - OMN-1805: Pattern lifecycle state machine implementation
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.models.domain import ModelGateSnapshot
from omniintelligence.nodes.node_intelligence_reducer.handlers.handler_pattern_lifecycle import (
    ERROR_GUARD_CONDITION_FAILED,
    ERROR_INVALID_TRANSITION,
    ERROR_INVALID_TRIGGER,
    ERROR_STATE_MISMATCH,
    GUARD_CONDITIONS,
    VALID_TRANSITIONS,
    VALID_TRIGGERS,
    PatternLifecycleTransitionResult,
    get_fsm_transition_table,
    get_guard_conditions,
    handle_pattern_lifecycle_transition,
    validate_transition,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_payload_update_pattern_status import (
    ModelPayloadUpdatePatternStatus,
)

# =============================================================================
# Test Class: Valid Transitions
# =============================================================================


@pytest.mark.unit
class TestValidTransitions:
    """Tests for all 6 valid FSM transitions.

    Note: candidate -> provisional was REMOVED because PROVISIONAL is LEGACY.
    The effect handler's PROVISIONAL guard blocks inbound transitions.
    New patterns use: candidate -> validated (via promote_direct).

    These tests verify the happy path where:
    - from_status is a valid state
    - trigger is a valid trigger
    - Transition exists in VALID_TRANSITIONS
    - to_status matches the expected target state
    - Guard conditions are satisfied
    """

    # NOTE: test_candidate_to_provisional_via_validation_passed REMOVED
    # PROVISIONAL is legacy - only outbound transitions allowed.
    # See handler_transition.py PROVISIONAL guard documentation.

    def test_provisional_to_validated_via_promote(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test transition: provisional -> validated (trigger: promote).

        This transition promotes a provisional pattern to validated status
        after meeting promotion gates.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="provisional",
            to_status="validated",
            trigger="promote",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.from_status == "provisional"
        assert result.to_status == "validated"
        assert result.trigger == "promote"

    def test_candidate_to_validated_via_promote_direct(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test transition: candidate -> validated (trigger: promote_direct).

        This transition allows skipping the provisional phase for patterns
        that meet all validation criteria immediately.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.from_status == "candidate"
        assert result.to_status == "validated"
        assert result.trigger == "promote_direct"

    def test_candidate_to_deprecated_via_deprecate(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test transition: candidate -> deprecated (trigger: deprecate).

        A candidate pattern can be deprecated if it fails validation or
        is no longer needed.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="deprecated",
            trigger="deprecate",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.from_status == "candidate"
        assert result.to_status == "deprecated"
        assert result.trigger == "deprecate"

    def test_provisional_to_deprecated_via_deprecate(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test transition: provisional -> deprecated (trigger: deprecate).

        A provisional pattern can be deprecated if it fails to meet
        promotion gates or is superseded.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="provisional",
            to_status="deprecated",
            trigger="deprecate",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.from_status == "provisional"
        assert result.to_status == "deprecated"
        assert result.trigger == "deprecate"

    def test_validated_to_deprecated_via_deprecate(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test transition: validated -> deprecated (trigger: deprecate).

        Even validated patterns can be deprecated when they become
        outdated or superseded by better patterns.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="validated",
            to_status="deprecated",
            trigger="deprecate",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.from_status == "validated"
        assert result.to_status == "deprecated"
        assert result.trigger == "deprecate"

    def test_deprecated_to_candidate_via_manual_reenable_with_admin(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test transition: deprecated -> candidate (trigger: manual_reenable).

        This transition requires actor_type='admin' as a guard condition.
        A deprecated pattern can be re-enabled for reconsideration.
        """
        # Arrange - With admin actor_type to satisfy guard condition
        input_data = make_reducer_input(
            from_status="deprecated",
            to_status="candidate",
            trigger="manual_reenable",
            actor_type="admin",  # Required by guard condition
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.from_status == "deprecated"
        assert result.to_status == "candidate"
        assert result.trigger == "manual_reenable"


# =============================================================================
# Test Class: Invalid State Tests
# =============================================================================


@pytest.mark.unit
class TestInvalidState:
    """Tests for invalid from_status values.

    With typed enums, invalid status strings are rejected at model creation
    time (Pydantic validation), not at handler execution time.
    These tests verify that validation correctly rejects invalid values.
    """

    def test_invalid_from_status_unknown_state(
        self,
        make_reducer_input,
    ) -> None:
        """Test rejection of unknown from_status value at model creation."""
        # Invalid status strings raise ValueError during enum conversion
        with pytest.raises(ValueError, match="unknown_state"):
            make_reducer_input(
                from_status="unknown_state",
                to_status="validated",
                trigger="promote",
            )

    def test_invalid_from_status_empty_string(
        self,
        make_reducer_input,
    ) -> None:
        """Test rejection of empty string from_status at model creation."""
        # Empty strings raise ValueError during enum conversion
        with pytest.raises(ValueError):
            make_reducer_input(
                from_status="",
                to_status="validated",
                trigger="promote",
            )

    def test_invalid_from_status_typo(
        self,
        make_reducer_input,
    ) -> None:
        """Test rejection of typo in from_status (e.g., 'candiate')."""
        # Typos raise ValueError during enum conversion
        with pytest.raises(ValueError, match="candiate"):
            make_reducer_input(
                from_status="candiate",  # Typo
                to_status="validated",
                trigger="promote_direct",
            )

    def test_valid_enum_values_accepted(
        self,
        make_reducer_input,
    ) -> None:
        """Test that all valid enum values are accepted."""
        # All valid enum values should be accepted
        for status in EnumPatternLifecycleStatus:
            # Should not raise
            input_data = make_reducer_input(
                from_status=status,
                to_status=EnumPatternLifecycleStatus.VALIDATED,
                trigger="promote",
            )
            assert input_data.payload.from_status == status


# =============================================================================
# Test Class: Invalid Trigger Tests
# =============================================================================


@pytest.mark.unit
class TestInvalidTrigger:
    """Tests for invalid trigger values.

    These tests verify that unknown triggers are rejected with
    ERROR_INVALID_TRIGGER and a descriptive error message.
    """

    def test_invalid_trigger_unknown(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test rejection of unknown trigger value."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="unknown_trigger",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.error_code == ERROR_INVALID_TRIGGER
        assert result.intent is None
        assert "unknown_trigger" in result.error_message
        assert "Valid triggers" in result.error_message

    def test_invalid_trigger_empty_string_rejected_at_model_level(self) -> None:
        """Test that empty string trigger is rejected at Pydantic model level.

        The ModelReducerInputPatternLifecycle has min_length=1 on the action field,
        so empty strings are rejected before reaching the handler. This is the
        correct behavior - validation happens at the schema boundary.
        """
        import pydantic

        from omniintelligence.nodes.node_intelligence_reducer.models.model_pattern_lifecycle_reducer_input import (
            ModelPatternLifecycleReducerInput,
        )
        from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input import (
            ModelReducerInputPatternLifecycle,
        )

        # Creating with empty trigger should raise ValidationError
        with pytest.raises(pydantic.ValidationError) as exc_info:
            ModelReducerInputPatternLifecycle(
                fsm_type="PATTERN_LIFECYCLE",
                entity_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                action="",  # Empty - rejected at model level
                payload=ModelPatternLifecycleReducerInput(
                    pattern_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    from_status="candidate",
                    to_status="validated",
                    trigger="",
                ),
                correlation_id="12345678-1234-5678-1234-567812345678",
                request_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            )

        # Assert: Validation error mentions string_too_short
        assert "string_too_short" in str(exc_info.value)

    def test_invalid_trigger_typo(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test rejection of typo in trigger (e.g., 'promte')."""
        # Arrange
        input_data = make_reducer_input(
            from_status="provisional",
            to_status="validated",
            trigger="promte",  # Typo
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.error_code == ERROR_INVALID_TRIGGER
        assert "promte" in result.error_message

    def test_error_message_lists_valid_triggers(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that error message includes list of valid triggers."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="invalid",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        # Verify all valid triggers are listed
        for trigger in VALID_TRIGGERS:
            assert trigger in result.error_message


# =============================================================================
# Test Class: Invalid Transition Tests
# =============================================================================


@pytest.mark.unit
class TestInvalidTransition:
    """Tests for invalid transition combinations.

    These tests verify that valid state + valid trigger combinations
    that don't exist in VALID_TRANSITIONS are rejected with
    ERROR_INVALID_TRANSITION.
    """

    def test_validated_with_promote_direct_no_transition(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test rejection: validated + promote_direct has no transition.

        Both 'validated' and 'promote_direct' are valid, but there's
        no transition from validated state with promote_direct trigger.
        (promote_direct is for candidate → validated only)
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="validated",
            to_status="validated",  # Would stay at validated if transition existed
            trigger="promote_direct",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.error_code == ERROR_INVALID_TRANSITION
        assert result.intent is None
        assert "validated" in result.error_message
        assert "promote_direct" in result.error_message

    def test_deprecated_with_promote_no_transition(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test rejection: deprecated + promote has no transition.

        Cannot promote directly from deprecated state.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="deprecated",
            to_status="validated",
            trigger="promote",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.error_code == ERROR_INVALID_TRANSITION

    def test_candidate_with_promote_no_transition(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test rejection: candidate + promote has no transition.

        Must use promote_direct to go candidate -> validated.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote",  # Should be promote_direct
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.error_code == ERROR_INVALID_TRANSITION

    def test_error_message_shows_available_triggers(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that error message shows available triggers from the state."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote",  # Invalid for candidate - should use promote_direct
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert "Available transitions from 'candidate'" in result.error_message
        # Should mention valid triggers: promote_direct, deprecate
        # NOTE: validation_passed REMOVED - PROVISIONAL is legacy
        assert "deprecate" in result.error_message
        assert "promote_direct" in result.error_message


# =============================================================================
# Test Class: State Mismatch Tests
# =============================================================================


@pytest.mark.unit
class TestStateMismatch:
    """Tests for state mismatch errors.

    These tests verify that when a valid transition exists, the
    provided to_status must match the expected target state.
    """

    def test_candidate_promote_direct_wrong_to_status(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test mismatch: candidate + promote_direct should go to validated.

        If caller provides to_status='deprecated' instead of 'validated',
        this is a state mismatch error.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="deprecated",  # Wrong! Should be 'validated'
            trigger="promote_direct",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.error_code == ERROR_STATE_MISMATCH
        assert result.intent is None
        assert "validated" in result.error_message  # Expected target
        assert "deprecated" in result.error_message  # Provided target

    def test_provisional_promote_wrong_to_status(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test mismatch: provisional + promote should go to validated.

        If caller provides to_status='deprecated', this is a state mismatch.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="provisional",
            to_status="deprecated",  # Wrong! Should be 'validated'
            trigger="promote",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.error_code == ERROR_STATE_MISMATCH
        assert "validated" in result.error_message  # Expected target
        assert "deprecated" in result.error_message  # Provided target

    def test_deprecated_manual_reenable_wrong_to_status(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test mismatch: deprecated + manual_reenable should go to candidate.

        Even with admin actor_type, wrong to_status causes mismatch error.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="deprecated",
            to_status="validated",  # Wrong! Should be 'candidate'
            trigger="manual_reenable",
            actor_type="admin",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.error_code == ERROR_STATE_MISMATCH
        assert "candidate" in result.error_message  # Expected target
        assert "validated" in result.error_message  # Provided target


# =============================================================================
# Test Class: Guard Condition Tests
# =============================================================================


@pytest.mark.unit
class TestGuardConditions:
    """Tests for guard condition enforcement.

    The PATTERN_LIFECYCLE FSM has one guard condition:
    - deprecated + manual_reenable requires actor_type='admin'
    """

    def test_manual_reenable_without_admin_fails(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test guard: manual_reenable without admin actor_type fails.

        The handler actor_type is not sufficient for this transition.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="deprecated",
            to_status="candidate",
            trigger="manual_reenable",
            actor_type="handler",  # Not admin
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.error_code == ERROR_GUARD_CONDITION_FAILED
        assert result.intent is None
        assert "admin" in result.error_message
        assert "handler" in result.error_message

    def test_manual_reenable_with_system_actor_fails(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test guard: manual_reenable with system actor_type fails.

        Even system actor cannot perform manual_reenable, only admin.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="deprecated",
            to_status="candidate",
            trigger="manual_reenable",
            actor_type="system",  # Not admin
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.error_code == ERROR_GUARD_CONDITION_FAILED
        assert "system" in result.error_message

    def test_manual_reenable_with_admin_succeeds(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test guard: manual_reenable with admin actor_type succeeds."""
        # Arrange
        input_data = make_reducer_input(
            from_status="deprecated",
            to_status="candidate",
            trigger="manual_reenable",
            actor_type="admin",  # Required
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.error_code is None

    def test_guard_condition_checked_after_transition_lookup(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that guard condition error has lower priority than transition errors.

        If both transition lookup fails AND guard would fail, we get
        INVALID_TRANSITION not GUARD_CONDITION_FAILED.
        """
        # Arrange - Invalid transition (validated + manual_reenable doesn't exist)
        input_data = make_reducer_input(
            from_status="validated",  # No manual_reenable from validated
            to_status="candidate",
            trigger="manual_reenable",
            actor_type="handler",  # Would fail guard if transition existed
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert - Should be INVALID_TRANSITION, not GUARD_CONDITION_FAILED
        assert result.success is False
        assert result.error_code == ERROR_INVALID_TRANSITION


# =============================================================================
# Test Class: Intent Verification
# =============================================================================


@pytest.mark.unit
class TestIntentVerification:
    """Tests for correct population of ModelPayloadUpdatePatternStatus intent.

    When a transition is valid, the handler returns an intent payload
    that must contain all required fields correctly populated.
    """

    def test_intent_type_is_correct(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that intent_type is 'postgres.update_pattern_status'."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.intent is not None
        assert result.intent.intent_type == "postgres.update_pattern_status"

    def test_request_id_flows_through(
        self,
        make_reducer_input,
        sample_request_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Test that request_id is preserved in intent."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
            request_id=sample_request_id,
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.intent.request_id == sample_request_id

    def test_correlation_id_flows_through(
        self,
        make_reducer_input,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Test that correlation_id is preserved in intent."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
            correlation_id=sample_correlation_id,
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.intent.correlation_id == sample_correlation_id

    def test_pattern_id_is_uuid(
        self,
        make_reducer_input,
        sample_pattern_id: str,
        sample_pattern_id_uuid: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Test that pattern_id is converted to UUID in intent."""
        # Arrange
        input_data = make_reducer_input(
            pattern_id=sample_pattern_id,  # String
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.intent.pattern_id == sample_pattern_id_uuid
        assert isinstance(result.intent.pattern_id, UUID)

    def test_status_fields_populated(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that from_status and to_status are populated in intent."""
        # Arrange
        input_data = make_reducer_input(
            from_status="provisional",
            to_status="validated",
            trigger="promote",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.intent.from_status == "provisional"
        assert result.intent.to_status == "validated"
        assert result.intent.trigger == "promote"

    def test_transition_at_populated(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that transition_at is populated in intent."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.intent.transition_at == sample_transition_at

    def test_transition_at_defaults_to_now(
        self,
        make_reducer_input,
    ) -> None:
        """Test that transition_at defaults to current time if not provided."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
        )

        # Act
        before = datetime.now(UTC)
        result = handle_pattern_lifecycle_transition(input_data)
        after = datetime.now(UTC)

        # Assert
        assert result.success is True
        assert before <= result.intent.transition_at <= after

    def test_actor_populated(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that actor field is populated in intent."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
            actor="promotion_scheduler",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.intent.actor == "promotion_scheduler"

    def test_reason_populated(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that reason field is populated in intent."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
            reason="Direct promotion - all criteria met",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.intent.reason == "Direct promotion - all criteria met"

    def test_gate_snapshot_populated(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that gate_snapshot field is populated in intent."""
        # Arrange
        gate_snapshot = ModelGateSnapshot(
            injection_count_rolling_20=15,
            success_rate_rolling_20=0.85,
            failure_streak=0,
            disabled=False,
        )
        input_data = make_reducer_input(
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            gate_snapshot=gate_snapshot,
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.intent.gate_snapshot == gate_snapshot

    def test_gate_snapshot_none_allowed(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that gate_snapshot can be None."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="deprecated",
            trigger="deprecate",
            gate_snapshot=None,
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.intent.gate_snapshot is None

    def test_intent_is_frozen(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that intent model is immutable (frozen)."""
        import pydantic

        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert isinstance(result.intent, ModelPayloadUpdatePatternStatus)
        # Frozen models raise ValidationError on mutation
        with pytest.raises(pydantic.ValidationError):
            result.intent.to_status = "deprecated"  # type: ignore[misc]


# =============================================================================
# Test Class: Helper Functions
# =============================================================================


@pytest.mark.unit
class TestHelperFunctions:
    """Tests for helper functions in the handler module."""

    def test_validate_transition_valid(self) -> None:
        """Test validate_transition returns True for valid transitions."""
        # Test all valid transitions
        for (from_status, trigger), expected_to in VALID_TRANSITIONS.items():
            is_valid, to_status = validate_transition(from_status, trigger)
            assert is_valid is True
            assert to_status == expected_to

    def test_validate_transition_invalid(self) -> None:
        """Test validate_transition returns False for invalid transitions."""
        # Invalid: validated + validation_passed
        is_valid, to_status = validate_transition("validated", "validation_passed")
        assert is_valid is False
        assert to_status is None

    def test_validate_transition_case_insensitive(self) -> None:
        """Test validate_transition normalizes case."""
        # Mixed case should still work
        is_valid, to_status = validate_transition("CANDIDATE", "PROMOTE_DIRECT")
        assert is_valid is True
        assert to_status == "validated"

    def test_get_fsm_transition_table_returns_copy(self) -> None:
        """Test get_fsm_transition_table returns a copy."""
        table = get_fsm_transition_table()
        assert table == VALID_TRANSITIONS
        # Verify it's a copy, not the original
        assert table is not VALID_TRANSITIONS

    def test_get_guard_conditions_returns_copy(self) -> None:
        """Test get_guard_conditions returns a copy."""
        conditions = get_guard_conditions()
        assert conditions == GUARD_CONDITIONS
        # Verify it's a copy, not the original
        assert conditions is not GUARD_CONDITIONS


# =============================================================================
# Test Class: Case Sensitivity
# =============================================================================


@pytest.mark.unit
class TestCaseSensitivity:
    """Tests for case normalization in handler.

    All from_status, to_status, and trigger values should be
    lowercased before processing.
    """

    def test_uppercase_from_status_normalized(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that uppercase from_status is normalized to lowercase."""
        # Arrange
        input_data = make_reducer_input(
            from_status="CANDIDATE",  # Uppercase
            to_status="validated",
            trigger="promote_direct",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.from_status == "candidate"  # Lowercased

    def test_uppercase_to_status_normalized(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that uppercase to_status is normalized to lowercase."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="VALIDATED",  # Uppercase
            trigger="promote_direct",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.to_status == "validated"  # Lowercased

    def test_uppercase_trigger_normalized(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that uppercase trigger is normalized to lowercase."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="PROMOTE_DIRECT",  # Uppercase
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.trigger == "promote_direct"  # Lowercased

    def test_mixed_case_all_fields(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test mixed case in all fields."""
        # Arrange
        input_data = make_reducer_input(
            from_status="CaNdIdAtE",
            to_status="VaLiDaTeD",
            trigger="PrOmOtE_DiReCt",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.from_status == "candidate"
        assert result.to_status == "validated"
        assert result.trigger == "promote_direct"


# =============================================================================
# Test Class: Result Model Verification
# =============================================================================


@pytest.mark.unit
class TestResultModel:
    """Tests for PatternLifecycleTransitionResult structure."""

    def test_result_is_frozen_dataclass(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that result is a frozen dataclass."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert isinstance(result, PatternLifecycleTransitionResult)
        # Frozen dataclasses raise FrozenInstanceError on mutation
        from dataclasses import FrozenInstanceError

        with pytest.raises(FrozenInstanceError):
            result.success = False  # type: ignore[misc]

    def test_success_result_has_none_error_fields(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that successful result has None for error fields."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.error_code is None
        assert result.error_message is None

    def test_error_result_has_none_intent(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that error result has None for intent field.

        Uses an invalid transition (wrong to_status) instead of invalid status
        since status is now validated at model creation time via enum types.
        """
        # Arrange - Use valid states but invalid transition (wrong to_status)
        # candidate + promote_direct should go to validated, not deprecated
        input_data = make_reducer_input(
            from_status=EnumPatternLifecycleStatus.CANDIDATE,
            to_status=EnumPatternLifecycleStatus.DEPRECATED,  # Wrong target
            trigger="promote_direct",
        )

        # Act
        result = handle_pattern_lifecycle_transition(
            input_data,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.intent is None
        assert result.error_code is not None
        assert result.error_message is not None

    def test_result_always_has_from_status_and_trigger(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that result always contains from_status and trigger.

        Tests both valid and invalid transitions (using wrong trigger).
        """
        # Arrange - Valid transition
        input_valid = make_reducer_input(
            from_status=EnumPatternLifecycleStatus.CANDIDATE,
            to_status=EnumPatternLifecycleStatus.VALIDATED,
            trigger="promote_direct",
        )

        # Arrange - Invalid transition (wrong trigger for validated state)
        input_invalid = make_reducer_input(
            from_status=EnumPatternLifecycleStatus.VALIDATED,
            to_status=EnumPatternLifecycleStatus.DEPRECATED,
            trigger="promote_direct",  # Wrong trigger, should be "deprecate"
        )

        # Act
        result_valid = handle_pattern_lifecycle_transition(
            input_valid,
            transition_at=sample_transition_at,
        )
        result_invalid = handle_pattern_lifecycle_transition(
            input_invalid,
            transition_at=sample_transition_at,
        )

        # Assert - Both have from_status and trigger
        assert result_valid.from_status == "candidate"
        assert result_valid.trigger == "promote_direct"
        assert result_invalid.from_status == "validated"
        assert result_invalid.trigger == "promote_direct"


# =============================================================================
# Test Class: Complete Transition Coverage
# =============================================================================


@pytest.mark.unit
class TestCompleteCoverage:
    """Tests to verify all transitions in VALID_TRANSITIONS are covered.

    This is a meta-test to ensure we have comprehensive coverage.
    """

    def test_all_valid_transitions_exercised(
        self,
        make_reducer_input,
        sample_transition_at: datetime,
    ) -> None:
        """Test that we can successfully execute all valid transitions.

        Iterates through VALID_TRANSITIONS and verifies each one works.
        """
        for (from_status, trigger), expected_to in VALID_TRANSITIONS.items():
            # Handle guard condition for manual_reenable
            actor_type = "admin" if trigger == "manual_reenable" else "handler"

            input_data = make_reducer_input(
                from_status=from_status,
                to_status=expected_to,
                trigger=trigger,
                actor_type=actor_type,
            )

            result = handle_pattern_lifecycle_transition(
                input_data,
                transition_at=sample_transition_at,
            )

            assert result.success is True, (
                f"Transition {from_status} + {trigger} -> {expected_to} failed: "
                f"{result.error_message}"
            )
            assert result.to_status == expected_to

    def test_transition_count_matches_expected(self) -> None:
        """Test that we have exactly 6 valid transitions.

        Note: candidate -> provisional REMOVED - PROVISIONAL is legacy.
        """
        assert len(VALID_TRANSITIONS) == 6

    def test_guard_condition_count_matches_expected(self) -> None:
        """Test that we have exactly 1 guard condition."""
        assert len(GUARD_CONDITIONS) == 1
        assert ("deprecated", "manual_reenable") in GUARD_CONDITIONS
