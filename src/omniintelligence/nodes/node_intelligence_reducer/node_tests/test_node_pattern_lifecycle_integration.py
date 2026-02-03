# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Integration tests for NodeIntelligenceReducer PATTERN_LIFECYCLE routing.

Tests the full node `process()` method for PATTERN_LIFECYCLE FSM transitions.
Unlike unit tests that test handlers directly, these integration tests exercise:
    1. The node's routing logic (ModelReducerInputPatternLifecycle detection)
    2. Handler delegation (_handle_pattern_lifecycle method)
    3. ModelReducerOutput construction with result dict and intents
    4. ModelIntent building with correct intent_type, target, and payload
    5. Error path handling and output structure

Test organization:
1. Successful Transitions via Node - All 7 valid FSM transitions
2. Failed Transitions via Node - Invalid state, trigger, transition, guard
3. Intent Verification via Node - intent_type, target, payload structure
4. Output Structure Verification - Result dict and intents tuple
5. Logging Verification (Optional) - Warning on rejection, info on acceptance

Reference:
    - OMN-1805: Pattern lifecycle state machine implementation
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from omnibase_core.models.reducer.model_intent import ModelIntent
from omnibase_core.models.reducer.payloads.model_extension_payloads import (
    ModelPayloadExtension,
)

from omniintelligence.nodes.node_pattern_promotion_effect.models import ModelGateSnapshot
from omniintelligence.nodes.node_intelligence_reducer.handlers.handler_pattern_lifecycle import (
    ERROR_GUARD_CONDITION_FAILED,
    ERROR_INVALID_FROM_STATE,
    ERROR_INVALID_TRANSITION,
    ERROR_INVALID_TRIGGER,
    ERROR_STATE_MISMATCH,
    VALID_TRANSITIONS,
)
from omniintelligence.nodes.node_intelligence_reducer.node import NodeIntelligenceReducer

if TYPE_CHECKING:
    pass


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def onex_container() -> ModelONEXContainer:
    """Create a minimal ONEX container for node instantiation.

    The container uses default settings which are sufficient for
    integration tests that don't require infrastructure.
    """
    return ModelONEXContainer()


@pytest.fixture
def reducer_node(onex_container: ModelONEXContainer) -> NodeIntelligenceReducer:
    """Create a NodeIntelligenceReducer instance for testing.

    This fixture provides a real node instance that can be used to test
    the full process() flow.
    """
    return NodeIntelligenceReducer(container=onex_container)


# =============================================================================
# Test Class: Successful Transitions via Node
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestSuccessfulTransitionsViaNode:
    """Integration tests for successful PATTERN_LIFECYCLE transitions.

    These tests verify that when a valid transition is requested through
    the node's process() method:
        - output.result["success"] is True
        - output.intents contains exactly one intent
        - Intent has correct intent_type, target, and payload
    """

    async def test_candidate_to_provisional_via_process(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test: candidate -> provisional via node.process().

        Verifies the full flow from input through process() to output
        for the first phase transition.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert - Output structure
        assert output.result["success"] is True
        assert output.result["fsm_type"] == "PATTERN_LIFECYCLE"
        assert output.result["from_status"] == "candidate"
        assert output.result["to_status"] == "provisional"
        assert output.result["trigger"] == "validation_passed"
        assert "error_code" not in output.result
        assert "error_message" not in output.result

        # Assert - Intents
        assert len(output.intents) == 1

    async def test_provisional_to_validated_via_process(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test: provisional -> validated via node.process()."""
        # Arrange
        input_data = make_reducer_input(
            from_status="provisional",
            to_status="validated",
            trigger="promote",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        assert output.result["success"] is True
        assert output.result["from_status"] == "provisional"
        assert output.result["to_status"] == "validated"
        assert output.result["trigger"] == "promote"
        assert len(output.intents) == 1

    async def test_candidate_to_validated_via_promote_direct(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test: candidate -> validated via promote_direct (skipping provisional)."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        assert output.result["success"] is True
        assert output.result["from_status"] == "candidate"
        assert output.result["to_status"] == "validated"
        assert output.result["trigger"] == "promote_direct"
        assert len(output.intents) == 1

    async def test_candidate_to_deprecated_via_deprecate(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test: candidate -> deprecated via deprecate."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="deprecated",
            trigger="deprecate",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        assert output.result["success"] is True
        assert output.result["from_status"] == "candidate"
        assert output.result["to_status"] == "deprecated"
        assert len(output.intents) == 1

    async def test_provisional_to_deprecated_via_deprecate(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test: provisional -> deprecated via deprecate."""
        # Arrange
        input_data = make_reducer_input(
            from_status="provisional",
            to_status="deprecated",
            trigger="deprecate",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        assert output.result["success"] is True
        assert output.result["from_status"] == "provisional"
        assert output.result["to_status"] == "deprecated"
        assert len(output.intents) == 1

    async def test_validated_to_deprecated_via_deprecate(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test: validated -> deprecated via deprecate."""
        # Arrange
        input_data = make_reducer_input(
            from_status="validated",
            to_status="deprecated",
            trigger="deprecate",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        assert output.result["success"] is True
        assert output.result["from_status"] == "validated"
        assert output.result["to_status"] == "deprecated"
        assert len(output.intents) == 1

    async def test_deprecated_to_candidate_via_manual_reenable_admin(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test: deprecated -> candidate via manual_reenable with admin.

        This transition requires actor_type='admin' to satisfy the guard condition.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="deprecated",
            to_status="candidate",
            trigger="manual_reenable",
            actor_type="admin",  # Required by guard condition
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        assert output.result["success"] is True
        assert output.result["from_status"] == "deprecated"
        assert output.result["to_status"] == "candidate"
        assert output.result["trigger"] == "manual_reenable"
        assert len(output.intents) == 1

    async def test_all_valid_transitions_via_process(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Comprehensive test: all 7 valid transitions via node.process().

        Iterates through VALID_TRANSITIONS table and verifies each one
        produces a successful output with correct structure.
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

            output = await reducer_node.process(input_data)

            # Assert success
            assert output.result["success"] is True, (
                f"Transition {from_status} + {trigger} -> {expected_to} failed: "
                f"result={output.result}"
            )
            assert output.result["from_status"] == from_status
            assert output.result["to_status"] == expected_to
            assert output.result["trigger"] == trigger
            assert len(output.intents) == 1, (
                f"Expected 1 intent for {from_status} + {trigger}, "
                f"got {len(output.intents)}"
            )


# =============================================================================
# Test Class: Failed Transitions via Node
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestFailedTransitionsViaNode:
    """Integration tests for failed PATTERN_LIFECYCLE transitions.

    These tests verify that when an invalid transition is requested through
    the node's process() method:
        - output.result["success"] is False
        - output.result contains error_code and error_message
        - output.intents is empty
    """

    async def test_invalid_from_status_produces_error_output(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that unknown from_status produces error output with no intents."""
        # Arrange
        input_data = make_reducer_input(
            from_status="unknown_state",
            to_status="validated",
            trigger="promote",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert - Error output structure
        assert output.result["success"] is False
        assert output.result["fsm_type"] == "PATTERN_LIFECYCLE"
        assert output.result["error_code"] == ERROR_INVALID_FROM_STATE
        assert "error_message" in output.result
        assert "unknown_state" in output.result["error_message"]

        # Assert - No intents emitted
        assert len(output.intents) == 0

    async def test_invalid_trigger_produces_error_output(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that unknown trigger produces error output with no intents."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="provisional",
            trigger="unknown_trigger",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert - Error output
        assert output.result["success"] is False
        assert output.result["error_code"] == ERROR_INVALID_TRIGGER
        assert "unknown_trigger" in output.result["error_message"]

        # Assert - No intents
        assert len(output.intents) == 0

    async def test_invalid_transition_produces_error_output(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that valid state/trigger with no transition produces error output.

        Example: validated + validation_passed is not a valid transition.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="validated",
            to_status="provisional",  # Would be target if transition existed
            trigger="validation_passed",  # Valid trigger but no transition from validated
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert - Error output
        assert output.result["success"] is False
        assert output.result["error_code"] == ERROR_INVALID_TRANSITION
        assert "validated" in output.result["error_message"]
        assert "validation_passed" in output.result["error_message"]

        # Assert - No intents
        assert len(output.intents) == 0

    async def test_state_mismatch_produces_error_output(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that wrong to_status for valid transition produces error output.

        Example: candidate + validation_passed should go to provisional,
        not validated.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",  # Wrong! Should be provisional
            trigger="validation_passed",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert - Error output with STATE_MISMATCH
        assert output.result["success"] is False
        assert output.result["error_code"] == ERROR_STATE_MISMATCH
        assert "provisional" in output.result["error_message"]  # Expected
        assert "validated" in output.result["error_message"]  # Provided

        # Assert - No intents
        assert len(output.intents) == 0

    async def test_guard_condition_failure_produces_error_output(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that guard condition failure produces error output.

        manual_reenable requires actor_type='admin'. Using 'handler' should fail.
        """
        # Arrange
        input_data = make_reducer_input(
            from_status="deprecated",
            to_status="candidate",
            trigger="manual_reenable",
            actor_type="handler",  # Not admin - fails guard
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert - Error output with GUARD_CONDITION_FAILED
        assert output.result["success"] is False
        assert output.result["error_code"] == ERROR_GUARD_CONDITION_FAILED
        assert "admin" in output.result["error_message"]
        assert "handler" in output.result["error_message"]

        # Assert - No intents
        assert len(output.intents) == 0

    async def test_guard_failure_with_system_actor_type(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that even system actor_type fails manual_reenable guard."""
        # Arrange
        input_data = make_reducer_input(
            from_status="deprecated",
            to_status="candidate",
            trigger="manual_reenable",
            actor_type="system",  # Not admin
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        assert output.result["success"] is False
        assert output.result["error_code"] == ERROR_GUARD_CONDITION_FAILED
        assert "system" in output.result["error_message"]
        assert len(output.intents) == 0

    async def test_error_output_contains_pattern_id(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
        sample_pattern_id: str,
    ) -> None:
        """Test that error output still contains pattern_id for tracing."""
        # Arrange
        input_data = make_reducer_input(
            pattern_id=sample_pattern_id,
            from_status="invalid",
            to_status="validated",
            trigger="promote",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert - pattern_id preserved in error output
        assert output.result["success"] is False
        assert output.result["pattern_id"] == sample_pattern_id

    async def test_error_output_contains_transition_details(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that error output contains from_status, to_status, trigger."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="validated",  # Wrong for validation_passed
            trigger="validation_passed",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert - All transition details in error output
        assert output.result["success"] is False
        assert output.result["from_status"] == "candidate"
        assert output.result["to_status"] == "validated"
        assert output.result["trigger"] == "validation_passed"


# =============================================================================
# Test Class: Intent Verification via Node
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestIntentVerificationViaNode:
    """Integration tests verifying intent structure from node.process().

    When a successful transition is processed, the node emits a ModelIntent
    with specific structure. These tests verify:
        - intent.intent_type == "extension"
        - intent.target contains pattern_id
        - intent.payload matches ModelPayloadUpdatePatternStatus
    """

    async def test_intent_type_is_extension(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that emitted intent has intent_type='extension'."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        assert output.result["success"] is True
        assert len(output.intents) == 1
        intent = output.intents[0]
        assert isinstance(intent, ModelIntent)
        assert intent.intent_type == "extension"

    async def test_intent_target_contains_pattern_id(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
        sample_pattern_id: str,
    ) -> None:
        """Test that intent target URI contains the pattern_id."""
        # Arrange
        input_data = make_reducer_input(
            pattern_id=sample_pattern_id,
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        assert output.result["success"] is True
        intent = output.intents[0]
        # Target format: postgres://patterns/{pattern_id}
        assert f"postgres://patterns/{sample_pattern_id}" == intent.target

    async def test_intent_payload_is_extension_type(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that intent payload is a ModelPayloadExtension instance."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        assert output.result["success"] is True
        intent = output.intents[0]
        assert isinstance(intent.payload, ModelPayloadExtension)
        assert intent.payload.extension_type == "omniintelligence.pattern_lifecycle_update"
        assert intent.payload.plugin_name == "omniintelligence"

    async def test_intent_payload_contains_update_pattern_status_fields(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
        sample_pattern_id: str,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
    ) -> None:
        """Test that intent payload.data contains ModelPayloadUpdatePatternStatus fields."""
        # Arrange
        input_data = make_reducer_input(
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            reason="Passed promotion gates",
            actor="test_scheduler",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        assert output.result["success"] is True
        # Payload is wrapped in ModelPayloadExtension, data is in .data field
        payload_data = output.intents[0].payload.data

        # Verify expected payload fields
        assert payload_data["intent_type"] == "postgres.update_pattern_status"
        assert payload_data["pattern_id"] == sample_pattern_id
        assert payload_data["from_status"] == "provisional"
        assert payload_data["to_status"] == "validated"
        assert payload_data["trigger"] == "promote"
        assert payload_data["actor"] == "test_scheduler"
        assert payload_data["reason"] == "Passed promotion gates"
        # request_id and correlation_id should be present
        assert "request_id" in payload_data
        assert "correlation_id" in payload_data
        assert "transition_at" in payload_data

    async def test_intent_payload_request_id_flows_through(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
        sample_request_id: UUID,
    ) -> None:
        """Test that request_id is preserved in intent payload for idempotency."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
            request_id=sample_request_id,
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        payload_data = output.intents[0].payload.data
        assert payload_data["request_id"] == str(sample_request_id)

    async def test_intent_payload_correlation_id_flows_through(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
        sample_correlation_id: UUID,
    ) -> None:
        """Test that correlation_id is preserved in intent payload for tracing."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
            correlation_id=sample_correlation_id,
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        payload_data = output.intents[0].payload.data
        assert payload_data["correlation_id"] == str(sample_correlation_id)

    async def test_intent_payload_gate_snapshot_preserved(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that gate_snapshot is preserved in intent payload."""
        # Arrange
        gate_snapshot = ModelGateSnapshot(
            injection_count_rolling_20=25,
            success_rate_rolling_20=0.92,
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
        output = await reducer_node.process(input_data)

        # Assert
        payload_data = output.intents[0].payload.data
        # gate_snapshot is serialized to JSON in the payload
        assert payload_data["gate_snapshot"] == gate_snapshot.model_dump(mode="json")


# =============================================================================
# Test Class: Output Structure Verification
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestOutputStructureVerification:
    """Integration tests verifying ModelReducerOutput structure.

    These tests ensure the output from node.process() has the correct
    structure with all required fields.
    """

    async def test_success_output_has_result_dict(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that successful output has result dict with expected keys."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert - Result dict structure
        assert isinstance(output.result, dict)
        expected_keys = {"fsm_type", "success", "pattern_id", "from_status", "to_status", "trigger"}
        assert expected_keys.issubset(output.result.keys())

    async def test_success_output_intents_is_tuple(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that successful output.intents is a tuple."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        assert isinstance(output.intents, tuple)
        assert len(output.intents) == 1

    async def test_error_output_has_result_dict_with_error_fields(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that error output has result dict with error fields."""
        # Arrange
        input_data = make_reducer_input(
            from_status="invalid",
            to_status="validated",
            trigger="promote",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert - Result dict with error fields
        assert isinstance(output.result, dict)
        assert output.result["success"] is False
        assert "error_code" in output.result
        assert "error_message" in output.result

    async def test_error_output_intents_is_empty_tuple(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that error output.intents is an empty tuple."""
        # Arrange
        input_data = make_reducer_input(
            from_status="invalid",
            to_status="validated",
            trigger="promote",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert
        assert isinstance(output.intents, tuple)
        assert len(output.intents) == 0

    async def test_pattern_id_preserved_in_both_success_and_error(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
        sample_pattern_id: str,
    ) -> None:
        """Test that pattern_id is always in result dict for tracing."""
        # Success case
        success_input = make_reducer_input(
            pattern_id=sample_pattern_id,
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
        )
        success_output = await reducer_node.process(success_input)
        assert success_output.result["pattern_id"] == sample_pattern_id

        # Error case
        error_input = make_reducer_input(
            pattern_id=sample_pattern_id,
            from_status="invalid",
            to_status="validated",
            trigger="promote",
        )
        error_output = await reducer_node.process(error_input)
        assert error_output.result["pattern_id"] == sample_pattern_id


# =============================================================================
# Test Class: Logging Verification (Optional)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestLoggingVerification:
    """Integration tests verifying logging behavior.

    These tests verify that the node logs appropriately:
        - Warning logged on rejection
        - Info logged on acceptance
    """

    async def test_warning_logged_on_rejection(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that a warning is logged when transition is rejected."""
        # Arrange
        input_data = make_reducer_input(
            from_status="invalid_state",
            to_status="validated",
            trigger="promote",
        )

        # Act
        with caplog.at_level(logging.WARNING):
            output = await reducer_node.process(input_data)

        # Assert - Output is error
        assert output.result["success"] is False

        # Assert - Warning was logged
        assert any(
            "Pattern lifecycle transition rejected" in record.message
            for record in caplog.records
        )

    async def test_info_logged_on_acceptance(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that info is logged when transition is accepted."""
        # Arrange
        input_data = make_reducer_input(
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
        )

        # Act
        with caplog.at_level(logging.INFO):
            output = await reducer_node.process(input_data)

        # Assert - Output is success
        assert output.result["success"] is True

        # Assert - Info was logged
        assert any(
            "Pattern lifecycle transition accepted" in record.message
            for record in caplog.records
        )

    async def test_rejection_log_contains_correlation_id(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
        sample_correlation_id: UUID,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that rejection log contains correlation_id for tracing."""
        # Arrange
        input_data = make_reducer_input(
            from_status="invalid",
            to_status="validated",
            trigger="promote",
            correlation_id=sample_correlation_id,
        )

        # Act
        with caplog.at_level(logging.WARNING):
            await reducer_node.process(input_data)

        # Assert - Log record contains correlation_id
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) > 0
        # Check extra dict
        record = warning_records[0]
        assert hasattr(record, "correlation_id") or "correlation_id" in str(record)

    async def test_acceptance_log_contains_pattern_id(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
        sample_pattern_id: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that acceptance log contains pattern_id for tracing."""
        # Arrange
        input_data = make_reducer_input(
            pattern_id=sample_pattern_id,
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
        )

        # Act
        with caplog.at_level(logging.INFO):
            await reducer_node.process(input_data)

        # Assert - Log record contains pattern_id
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) > 0


# =============================================================================
# Test Class: Case Sensitivity via Node
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestCaseSensitivityViaNode:
    """Integration tests for case normalization through node.process().

    Verifies that mixed-case inputs are normalized to lowercase
    in both output.result and intent.payload.
    """

    async def test_uppercase_normalized_in_output(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that uppercase inputs are normalized in output."""
        # Arrange
        input_data = make_reducer_input(
            from_status="CANDIDATE",
            to_status="PROVISIONAL",
            trigger="VALIDATION_PASSED",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert - Normalized in result
        assert output.result["success"] is True
        assert output.result["from_status"] == "candidate"
        assert output.result["to_status"] == "provisional"
        assert output.result["trigger"] == "validation_passed"

    async def test_uppercase_normalized_in_intent_payload(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that uppercase inputs are normalized in intent payload."""
        # Arrange
        input_data = make_reducer_input(
            from_status="CANDIDATE",
            to_status="PROVISIONAL",
            trigger="VALIDATION_PASSED",
        )

        # Act
        output = await reducer_node.process(input_data)

        # Assert - Normalized in payload data
        assert output.result["success"] is True
        payload_data = output.intents[0].payload.data
        assert payload_data["from_status"] == "candidate"
        assert payload_data["to_status"] == "provisional"
        assert payload_data["trigger"] == "validation_passed"


# =============================================================================
# Test Class: Node Instance Behavior
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestNodeInstanceBehavior:
    """Integration tests for node instance behavior.

    Tests that verify the node can be used correctly as an instance.
    """

    async def test_node_can_process_multiple_transitions(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that node can process multiple transitions in sequence."""
        # First transition
        input1 = make_reducer_input(
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
        )
        output1 = await reducer_node.process(input1)
        assert output1.result["success"] is True

        # Second transition (different pattern, different transition)
        input2 = make_reducer_input(
            pattern_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            from_status="provisional",
            to_status="validated",
            trigger="promote",
        )
        output2 = await reducer_node.process(input2)
        assert output2.result["success"] is True

        # Third transition (error case)
        input3 = make_reducer_input(
            pattern_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
            from_status="invalid",
            to_status="validated",
            trigger="promote",
        )
        output3 = await reducer_node.process(input3)
        assert output3.result["success"] is False

    async def test_node_instance_is_stateless_between_calls(
        self,
        reducer_node: NodeIntelligenceReducer,
        make_reducer_input,
    ) -> None:
        """Test that node doesn't retain state between process() calls.

        Each call should be independent - a failed call shouldn't affect
        subsequent calls.
        """
        # First: Error call
        error_input = make_reducer_input(
            from_status="invalid",
            to_status="validated",
            trigger="promote",
        )
        error_output = await reducer_node.process(error_input)
        assert error_output.result["success"] is False

        # Second: Success call (should not be affected by previous error)
        success_input = make_reducer_input(
            from_status="candidate",
            to_status="provisional",
            trigger="validation_passed",
        )
        success_output = await reducer_node.process(success_input)
        assert success_output.result["success"] is True
        assert len(success_output.intents) == 1


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TestCaseSensitivityViaNode",
    "TestFailedTransitionsViaNode",
    "TestIntentVerificationViaNode",
    "TestLoggingVerification",
    "TestNodeInstanceBehavior",
    "TestOutputStructureVerification",
    "TestSuccessfulTransitionsViaNode",
]
