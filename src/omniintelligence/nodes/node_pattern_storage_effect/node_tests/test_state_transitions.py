# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for pattern state transitions.

Tests the state transition rules (FSM governance):
    - CANDIDATE -> PROVISIONAL: Valid (initial verification passed)
    - PROVISIONAL -> VALIDATED: Valid (full validation passed)
    - VALIDATED -> (none): Terminal state, no transitions allowed
    - CANDIDATE -> VALIDATED: INVALID (skips PROVISIONAL)
    - Any reverse transitions: INVALID

These transitions are hard-coded governance rules that cannot be bypassed.

Reference:
    - OMN-1668: Pattern storage effect acceptance criteria
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_pattern_storage_effect.constants import (
    VALID_TRANSITIONS,
    TransitionValidationResult,
    get_valid_targets,
    is_valid_transition,
    validate_promotion_transition,
)
from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_promote_pattern import (
    DEFAULT_ACTOR,
    PatternNotFoundError,
    PatternStateTransitionError,
    handle_promote_pattern,
)
from omniintelligence.nodes.node_pattern_storage_effect.models import (
    EnumPatternState,
    ModelPatternMetricsSnapshot,
)
from omniintelligence.nodes.node_pattern_storage_effect.node_tests.conftest import (
    MockPatternStateManager,
)


# =============================================================================
# State Transition Constants Verification
# =============================================================================


@pytest.mark.unit
class TestStateTransitionConstants:
    """Verify state transition constants are correctly defined."""

    def test_valid_transitions_from_candidate(self) -> None:
        """CANDIDATE should only transition to PROVISIONAL."""
        valid = VALID_TRANSITIONS[EnumPatternState.CANDIDATE]
        assert len(valid) == 1
        assert EnumPatternState.PROVISIONAL in valid

    def test_valid_transitions_from_provisional(self) -> None:
        """PROVISIONAL should only transition to VALIDATED."""
        valid = VALID_TRANSITIONS[EnumPatternState.PROVISIONAL]
        assert len(valid) == 1
        assert EnumPatternState.VALIDATED in valid

    def test_validated_is_terminal(self) -> None:
        """VALIDATED should be a terminal state (no valid transitions)."""
        valid = VALID_TRANSITIONS[EnumPatternState.VALIDATED]
        assert len(valid) == 0

    def test_all_states_have_transition_entry(self) -> None:
        """Every state should have an entry in VALID_TRANSITIONS."""
        for state in EnumPatternState:
            assert state in VALID_TRANSITIONS

    def test_default_actor_is_system(self) -> None:
        """DEFAULT_ACTOR should be 'system'."""
        assert DEFAULT_ACTOR == "system"


# =============================================================================
# is_valid_transition Function Tests
# =============================================================================


@pytest.mark.unit
class TestIsValidTransition:
    """Tests for the is_valid_transition helper function."""

    def test_candidate_to_provisional_valid(self) -> None:
        """CANDIDATE -> PROVISIONAL should be valid."""
        assert is_valid_transition(
            EnumPatternState.CANDIDATE,
            EnumPatternState.PROVISIONAL,
        )

    def test_provisional_to_validated_valid(self) -> None:
        """PROVISIONAL -> VALIDATED should be valid."""
        assert is_valid_transition(
            EnumPatternState.PROVISIONAL,
            EnumPatternState.VALIDATED,
        )

    def test_candidate_to_validated_invalid(self) -> None:
        """CANDIDATE -> VALIDATED should be invalid (skips PROVISIONAL)."""
        assert not is_valid_transition(
            EnumPatternState.CANDIDATE,
            EnumPatternState.VALIDATED,
        )

    def test_validated_to_any_invalid(self) -> None:
        """VALIDATED -> any state should be invalid (terminal)."""
        assert not is_valid_transition(
            EnumPatternState.VALIDATED,
            EnumPatternState.CANDIDATE,
        )
        assert not is_valid_transition(
            EnumPatternState.VALIDATED,
            EnumPatternState.PROVISIONAL,
        )

    def test_reverse_transitions_invalid(self) -> None:
        """Reverse transitions should all be invalid."""
        # PROVISIONAL -> CANDIDATE
        assert not is_valid_transition(
            EnumPatternState.PROVISIONAL,
            EnumPatternState.CANDIDATE,
        )
        # VALIDATED -> PROVISIONAL
        assert not is_valid_transition(
            EnumPatternState.VALIDATED,
            EnumPatternState.PROVISIONAL,
        )
        # VALIDATED -> CANDIDATE
        assert not is_valid_transition(
            EnumPatternState.VALIDATED,
            EnumPatternState.CANDIDATE,
        )

    def test_self_transition_invalid(self) -> None:
        """Self-transitions should be invalid."""
        for state in EnumPatternState:
            assert not is_valid_transition(state, state)


# =============================================================================
# get_valid_targets Function Tests
# =============================================================================


@pytest.mark.unit
class TestGetValidTargets:
    """Tests for the get_valid_targets helper function."""

    def test_candidate_targets(self) -> None:
        """CANDIDATE should have [PROVISIONAL] as valid targets."""
        targets = get_valid_targets(EnumPatternState.CANDIDATE)
        assert targets == [EnumPatternState.PROVISIONAL]

    def test_provisional_targets(self) -> None:
        """PROVISIONAL should have [VALIDATED] as valid targets."""
        targets = get_valid_targets(EnumPatternState.PROVISIONAL)
        assert targets == [EnumPatternState.VALIDATED]

    def test_validated_targets(self) -> None:
        """VALIDATED should have empty list (terminal)."""
        targets = get_valid_targets(EnumPatternState.VALIDATED)
        assert targets == []


# =============================================================================
# Valid State Transition Tests
# =============================================================================


@pytest.mark.unit
class TestValidStateTransitions:
    """Tests for valid state transitions via handle_promote_pattern."""

    @pytest.mark.asyncio
    async def test_candidate_to_provisional(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """Valid transition: CANDIDATE -> PROVISIONAL."""
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        event = await handle_promote_pattern(
            pattern_id=pattern_id,
            to_state=EnumPatternState.PROVISIONAL,
            reason="Pattern passed initial verification",
            state_manager=mock_state_manager,
            conn=mock_conn,
        )

        assert event.from_state == EnumPatternState.CANDIDATE
        assert event.to_state == EnumPatternState.PROVISIONAL
        assert event.pattern_id == pattern_id
        assert event.reason == "Pattern passed initial verification"

    @pytest.mark.asyncio
    async def test_provisional_to_validated(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """Valid transition: PROVISIONAL -> VALIDATED."""
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.PROVISIONAL)

        event = await handle_promote_pattern(
            pattern_id=pattern_id,
            to_state=EnumPatternState.VALIDATED,
            reason="Pattern met all validation criteria",
            state_manager=mock_state_manager,
            conn=mock_conn,
        )

        assert event.from_state == EnumPatternState.PROVISIONAL
        assert event.to_state == EnumPatternState.VALIDATED
        assert event.is_valid_transition()

    @pytest.mark.asyncio
    async def test_state_manager_updated(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """State manager should reflect new state after promotion."""
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        await handle_promote_pattern(
            pattern_id=pattern_id,
            to_state=EnumPatternState.PROVISIONAL,
            reason="Verification passed",
            state_manager=mock_state_manager,
            conn=mock_conn,
        )

        # State should be updated in the manager
        assert (
            await mock_state_manager.get_current_state(pattern_id, mock_conn)
            == EnumPatternState.PROVISIONAL
        )

    @pytest.mark.asyncio
    async def test_transition_recorded_in_audit(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """State transition should be recorded in audit trail."""
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        await handle_promote_pattern(
            pattern_id=pattern_id,
            to_state=EnumPatternState.PROVISIONAL,
            reason="Verification passed",
            state_manager=mock_state_manager,
            conn=mock_conn,
            actor="test_workflow",
        )

        # Check audit trail
        assert len(mock_state_manager.transitions) == 1
        transition = mock_state_manager.transitions[0]
        assert transition.pattern_id == pattern_id
        assert transition.from_state == EnumPatternState.CANDIDATE
        assert transition.to_state == EnumPatternState.PROVISIONAL
        assert transition.actor == "test_workflow"


# =============================================================================
# Invalid State Transition Tests
# =============================================================================


@pytest.mark.unit
class TestInvalidStateTransitions:
    """Tests for invalid state transitions that must be rejected."""

    @pytest.mark.asyncio
    async def test_candidate_to_validated_rejected(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """Invalid transition: CANDIDATE -> VALIDATED must be rejected."""
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        with pytest.raises(PatternStateTransitionError) as exc_info:
            await handle_promote_pattern(
                pattern_id=pattern_id,
                to_state=EnumPatternState.VALIDATED,  # Skips PROVISIONAL
                reason="Attempting invalid skip",
                state_manager=mock_state_manager,
                conn=mock_conn,
            )

        assert exc_info.value.pattern_id == pattern_id
        assert exc_info.value.from_state == EnumPatternState.CANDIDATE
        assert exc_info.value.to_state == EnumPatternState.VALIDATED

    @pytest.mark.asyncio
    async def test_validated_to_any_rejected(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """Invalid transition: VALIDATED -> any state must be rejected."""
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.VALIDATED)

        # Try VALIDATED -> CANDIDATE
        with pytest.raises(PatternStateTransitionError):
            await handle_promote_pattern(
                pattern_id=pattern_id,
                to_state=EnumPatternState.CANDIDATE,
                reason="Attempting to demote validated pattern",
                state_manager=mock_state_manager,
                conn=mock_conn,
            )

        # Try VALIDATED -> PROVISIONAL
        with pytest.raises(PatternStateTransitionError):
            await handle_promote_pattern(
                pattern_id=pattern_id,
                to_state=EnumPatternState.PROVISIONAL,
                reason="Attempting to demote validated pattern",
                state_manager=mock_state_manager,
                conn=mock_conn,
            )

    @pytest.mark.asyncio
    async def test_provisional_to_candidate_rejected(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """Invalid transition: PROVISIONAL -> CANDIDATE must be rejected."""
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.PROVISIONAL)

        with pytest.raises(PatternStateTransitionError):
            await handle_promote_pattern(
                pattern_id=pattern_id,
                to_state=EnumPatternState.CANDIDATE,  # Reverse transition
                reason="Attempting reverse transition",
                state_manager=mock_state_manager,
                conn=mock_conn,
            )

    @pytest.mark.asyncio
    async def test_error_message_contains_valid_targets(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """Error message should include valid target states."""
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        with pytest.raises(PatternStateTransitionError) as exc_info:
            await handle_promote_pattern(
                pattern_id=pattern_id,
                to_state=EnumPatternState.VALIDATED,
                reason="Invalid skip",
                state_manager=mock_state_manager,
                conn=mock_conn,
            )

        error_message = str(exc_info.value)
        # Should mention valid targets from CANDIDATE (which is PROVISIONAL)
        assert "provisional" in error_message.lower()


# =============================================================================
# Pattern Not Found Tests
# =============================================================================


@pytest.mark.unit
class TestPatternNotFound:
    """Tests for handling non-existent patterns."""

    @pytest.mark.asyncio
    async def test_not_found_raises_error(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """Promoting non-existent pattern should raise PatternNotFoundError."""
        non_existent_id = uuid4()
        # Don't set any state - pattern doesn't exist

        with pytest.raises(PatternNotFoundError) as exc_info:
            await handle_promote_pattern(
                pattern_id=non_existent_id,
                to_state=EnumPatternState.PROVISIONAL,
                reason="Attempting to promote non-existent pattern",
                state_manager=mock_state_manager,
                conn=mock_conn,
            )

        assert exc_info.value.pattern_id == non_existent_id

    @pytest.mark.asyncio
    async def test_not_found_error_message(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """PatternNotFoundError should have informative message."""
        non_existent_id = uuid4()

        with pytest.raises(PatternNotFoundError) as exc_info:
            await handle_promote_pattern(
                pattern_id=non_existent_id,
                to_state=EnumPatternState.PROVISIONAL,
                reason="Test",
                state_manager=mock_state_manager,
                conn=mock_conn,
            )

        assert str(non_existent_id) in str(exc_info.value)


# =============================================================================
# Metrics Snapshot Tests
# =============================================================================


@pytest.mark.unit
class TestMetricsSnapshot:
    """Tests for metrics snapshot in promotion events."""

    @pytest.mark.asyncio
    async def test_metrics_included_in_event(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """Metrics snapshot should be included in promotion event."""
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        metrics = ModelPatternMetricsSnapshot(
            confidence=0.85,
            match_count=10,
            success_rate=0.9,
            validation_count=5,
        )

        event = await handle_promote_pattern(
            pattern_id=pattern_id,
            to_state=EnumPatternState.PROVISIONAL,
            reason="Verification passed",
            metrics_snapshot=metrics,
            state_manager=mock_state_manager,
            conn=mock_conn,
        )

        # metrics_snapshot should be present when explicitly provided
        assert event.metrics_snapshot is not None
        assert event.metrics_snapshot.confidence == 0.85
        assert event.metrics_snapshot.match_count == 10
        assert event.metrics_snapshot.success_rate == 0.9
        assert event.metrics_snapshot.validation_count == 5

    @pytest.mark.asyncio
    async def test_default_metrics_when_not_provided(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """No metrics should be returned when none specified.

        When metrics_snapshot is not provided, it should be None rather than
        a default with misleading zero values. This clearly indicates
        'no metrics captured' in audit trails.
        """
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        event = await handle_promote_pattern(
            pattern_id=pattern_id,
            to_state=EnumPatternState.PROVISIONAL,
            reason="Verification passed",
            state_manager=mock_state_manager,
            conn=mock_conn,
            # No metrics_snapshot provided
        )

        # metrics_snapshot should be None when not provided
        # This is intentional to avoid misleading 0.0 confidence values
        assert event.metrics_snapshot is None


# =============================================================================
# Actor and Correlation ID Tests
# =============================================================================


@pytest.mark.unit
class TestActorAndCorrelation:
    """Tests for actor tracking and correlation ID propagation."""

    @pytest.mark.asyncio
    async def test_actor_recorded_in_event(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """Actor should be recorded in promotion event."""
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        event = await handle_promote_pattern(
            pattern_id=pattern_id,
            to_state=EnumPatternState.PROVISIONAL,
            reason="Test",
            state_manager=mock_state_manager,
            conn=mock_conn,
            actor="verification_workflow",
        )

        assert event.actor == "verification_workflow"

    @pytest.mark.asyncio
    async def test_default_actor_when_not_provided(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """Default actor should be used when not specified."""
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        event = await handle_promote_pattern(
            pattern_id=pattern_id,
            to_state=EnumPatternState.PROVISIONAL,
            reason="Test",
            state_manager=mock_state_manager,
            conn=mock_conn,
        )

        assert event.actor == DEFAULT_ACTOR

    @pytest.mark.asyncio
    async def test_correlation_id_propagated(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """Correlation ID should be propagated to event."""
        pattern_id = uuid4()
        correlation_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        event = await handle_promote_pattern(
            pattern_id=pattern_id,
            to_state=EnumPatternState.PROVISIONAL,
            reason="Test",
            state_manager=mock_state_manager,
            conn=mock_conn,
            correlation_id=correlation_id,
        )

        assert event.correlation_id == correlation_id


# =============================================================================
# ModelPatternPromotedEvent.is_valid_transition Tests
# =============================================================================


@pytest.mark.unit
class TestEventValidTransition:
    """Tests for ModelPatternPromotedEvent.is_valid_transition method."""

    @pytest.mark.asyncio
    async def test_event_is_valid_transition_true(
        self,
        mock_state_manager: MockPatternStateManager,
        mock_conn: MagicMock,
    ) -> None:
        """Event should report is_valid_transition() = True for valid transitions."""
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        event = await handle_promote_pattern(
            pattern_id=pattern_id,
            to_state=EnumPatternState.PROVISIONAL,
            reason="Test",
            state_manager=mock_state_manager,
            conn=mock_conn,
        )

        assert event.is_valid_transition() is True


# =============================================================================
# validate_promotion_transition Function Tests (Dry-Run Validation)
# =============================================================================


@pytest.mark.unit
class TestValidatePromotionTransition:
    """Tests for pure validation function (no database required).

    The validate_promotion_transition function provides dry-run validation
    capability, returning detailed results about whether a transition would
    be valid without actually performing it.
    """

    def test_valid_candidate_to_provisional(self) -> None:
        """CANDIDATE -> PROVISIONAL should be valid."""
        result = validate_promotion_transition(
            from_state=EnumPatternState.CANDIDATE,
            to_state=EnumPatternState.PROVISIONAL,
        )
        assert result.is_valid is True
        assert result.error_message is None
        assert result.from_state == EnumPatternState.CANDIDATE
        assert result.to_state == EnumPatternState.PROVISIONAL

    def test_valid_provisional_to_validated(self) -> None:
        """PROVISIONAL -> VALIDATED should be valid."""
        result = validate_promotion_transition(
            from_state=EnumPatternState.PROVISIONAL,
            to_state=EnumPatternState.VALIDATED,
        )
        assert result.is_valid is True
        assert result.error_message is None
        assert result.from_state == EnumPatternState.PROVISIONAL
        assert result.to_state == EnumPatternState.VALIDATED

    def test_invalid_candidate_to_validated(self) -> None:
        """CANDIDATE -> VALIDATED (skipping PROVISIONAL) should be invalid."""
        result = validate_promotion_transition(
            from_state=EnumPatternState.CANDIDATE,
            to_state=EnumPatternState.VALIDATED,
        )
        assert result.is_valid is False
        assert result.error_message is not None
        # Error message should mention the valid target
        assert "provisional" in result.error_message.lower()
        # Valid targets should include PROVISIONAL
        assert EnumPatternState.PROVISIONAL in result.valid_targets

    def test_invalid_from_terminal_state(self) -> None:
        """VALIDATED -> any should be invalid (terminal state)."""
        result = validate_promotion_transition(
            from_state=EnumPatternState.VALIDATED,
            to_state=EnumPatternState.PROVISIONAL,
        )
        assert result.is_valid is False
        assert result.error_message is not None
        # Error message should indicate terminal state
        assert "terminal" in result.error_message.lower()
        # Terminal state has no valid targets
        assert result.valid_targets == []

    def test_invalid_validated_to_candidate(self) -> None:
        """VALIDATED -> CANDIDATE should be invalid (terminal + reverse)."""
        result = validate_promotion_transition(
            from_state=EnumPatternState.VALIDATED,
            to_state=EnumPatternState.CANDIDATE,
        )
        assert result.is_valid is False
        assert result.valid_targets == []
        assert result.from_state == EnumPatternState.VALIDATED
        assert result.to_state == EnumPatternState.CANDIDATE

    def test_invalid_reverse_provisional_to_candidate(self) -> None:
        """PROVISIONAL -> CANDIDATE (reverse) should be invalid."""
        result = validate_promotion_transition(
            from_state=EnumPatternState.PROVISIONAL,
            to_state=EnumPatternState.CANDIDATE,
        )
        assert result.is_valid is False
        assert result.error_message is not None
        # Should mention the only valid target (VALIDATED)
        assert "validated" in result.error_message.lower()
        assert EnumPatternState.VALIDATED in result.valid_targets

    def test_result_includes_from_and_to_state(self) -> None:
        """Result should echo from_state and to_state correctly."""
        # Valid transition
        valid_result = validate_promotion_transition(
            from_state=EnumPatternState.CANDIDATE,
            to_state=EnumPatternState.PROVISIONAL,
        )
        assert valid_result.from_state == EnumPatternState.CANDIDATE
        assert valid_result.to_state == EnumPatternState.PROVISIONAL

        # Invalid transition
        invalid_result = validate_promotion_transition(
            from_state=EnumPatternState.CANDIDATE,
            to_state=EnumPatternState.VALIDATED,
        )
        assert invalid_result.from_state == EnumPatternState.CANDIDATE
        assert invalid_result.to_state == EnumPatternState.VALIDATED

    def test_valid_targets_for_candidate(self) -> None:
        """CANDIDATE should have PROVISIONAL as only valid target."""
        result = validate_promotion_transition(
            from_state=EnumPatternState.CANDIDATE,
            to_state=EnumPatternState.PROVISIONAL,
        )
        assert result.valid_targets == [EnumPatternState.PROVISIONAL]

    def test_valid_targets_for_provisional(self) -> None:
        """PROVISIONAL should have VALIDATED as only valid target."""
        result = validate_promotion_transition(
            from_state=EnumPatternState.PROVISIONAL,
            to_state=EnumPatternState.VALIDATED,
        )
        assert result.valid_targets == [EnumPatternState.VALIDATED]

    def test_valid_targets_included_in_invalid_result(self) -> None:
        """Invalid result should still include valid_targets for guidance."""
        result = validate_promotion_transition(
            from_state=EnumPatternState.CANDIDATE,
            to_state=EnumPatternState.VALIDATED,
        )
        # Even though the transition is invalid, valid_targets should be populated
        assert result.is_valid is False
        assert result.valid_targets == [EnumPatternState.PROVISIONAL]

    def test_self_transition_invalid(self) -> None:
        """Self-transitions should be invalid for all states."""
        for state in EnumPatternState:
            result = validate_promotion_transition(
                from_state=state,
                to_state=state,
            )
            assert result.is_valid is False
            assert result.error_message is not None
            assert result.from_state == state
            assert result.to_state == state

    def test_result_is_frozen_dataclass(self) -> None:
        """Result should be immutable (frozen dataclass)."""
        result = validate_promotion_transition(
            from_state=EnumPatternState.CANDIDATE,
            to_state=EnumPatternState.PROVISIONAL,
        )
        # Verify it's a TransitionValidationResult
        assert isinstance(result, TransitionValidationResult)

        # Frozen dataclass should raise on attribute modification
        import dataclasses

        assert dataclasses.is_dataclass(result)
        # Try to modify - should raise FrozenInstanceError
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.is_valid = False  # type: ignore[misc]
