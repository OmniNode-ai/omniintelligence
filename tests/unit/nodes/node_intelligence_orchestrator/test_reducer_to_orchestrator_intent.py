# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""End-to-end test for reducer-to-orchestrator intent channel.

This test proves the intent channel works by:
    1. Creating a reducer input for a PATTERN_LIFECYCLE transition
    2. Processing it through the reducer handler (handle_pattern_lifecycle_process)
    3. Extracting the emitted ModelIntent from the reducer output
    4. Passing it to the orchestrator handler (handle_receive_intent)
    5. Verifying the receipt confirms successful reception

This is the core verification for OMN-2034: "Wire intelligence reducer
intent emission to orchestrator."

Ticket: OMN-2034
"""

from __future__ import annotations

from uuid import UUID

import pytest
from omnibase_core.models.reducer.model_intent import ModelIntent
from omnibase_core.models.reducer.payloads.model_extension_payloads import (
    ModelPayloadExtension,
)

from omniintelligence.nodes.node_intelligence_orchestrator.handlers.handler_receive_intent import (
    handle_receive_intent,
    handle_receive_intents,
)
from omniintelligence.nodes.node_intelligence_reducer.handlers.handler_process import (
    handle_pattern_lifecycle_process,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_pattern_lifecycle_reducer_input import (
    ModelPatternLifecycleReducerInput,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input import (
    ModelReducerInputPatternLifecycle,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_correlation_id() -> UUID:
    """Fixed correlation ID for tracing."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_request_id() -> UUID:
    """Fixed request ID for idempotency."""
    return UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def sample_pattern_id() -> str:
    """Fixed pattern ID."""
    return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture
def promote_direct_input(
    sample_pattern_id: str,
    sample_correlation_id: UUID,
    sample_request_id: UUID,
) -> ModelReducerInputPatternLifecycle:
    """Create a valid promote_direct transition input."""
    return ModelReducerInputPatternLifecycle(
        fsm_type="PATTERN_LIFECYCLE",
        entity_id=sample_pattern_id,
        action="promote_direct",
        payload=ModelPatternLifecycleReducerInput(
            pattern_id=sample_pattern_id,
            from_status="candidate",
            to_status="validated",
            trigger="promote_direct",
            actor_type="handler",
            actor="test_actor",
            reason="Test promotion for OMN-2034",
        ),
        correlation_id=sample_correlation_id,
        request_id=sample_request_id,
    )


@pytest.fixture
def deprecate_input(
    sample_pattern_id: str,
    sample_correlation_id: UUID,
    sample_request_id: UUID,
) -> ModelReducerInputPatternLifecycle:
    """Create a valid deprecate transition input."""
    return ModelReducerInputPatternLifecycle(
        fsm_type="PATTERN_LIFECYCLE",
        entity_id=sample_pattern_id,
        action="deprecate",
        payload=ModelPatternLifecycleReducerInput(
            pattern_id=sample_pattern_id,
            from_status="validated",
            to_status="deprecated",
            trigger="deprecate",
            actor_type="system",
            actor="test_system",
            reason="Pattern no longer relevant",
        ),
        correlation_id=sample_correlation_id,
        request_id=sample_request_id,
    )


# =============================================================================
# End-to-End Intent Channel Tests
# =============================================================================


class TestReducerToOrchestratorIntentChannel:
    """Proves the reducer-to-orchestrator intent channel works end-to-end."""

    def test_promote_direct_intent_reaches_orchestrator(
        self,
        promote_direct_input: ModelReducerInputPatternLifecycle,
        sample_correlation_id: UUID,
        sample_pattern_id: str,
    ) -> None:
        """Reducer emits promote_direct intent; orchestrator receives and logs it.

        This is the primary acceptance test for OMN-2034.
        """
        # Step 1: Reducer processes the transition
        reducer_output = handle_pattern_lifecycle_process(promote_direct_input)

        # Step 2: Verify reducer emitted intents
        assert (
            len(reducer_output.intents) == 1
        ), "Reducer must emit exactly one intent for a successful transition"

        # Step 3: Extract the ModelIntent
        intent = reducer_output.intents[0]
        assert isinstance(intent, ModelIntent)
        assert intent.intent_type == "extension"
        assert intent.target == f"postgres://patterns/{sample_pattern_id}"

        # Step 4: Orchestrator receives the intent
        receipt = handle_receive_intent(
            intent,
            correlation_id=sample_correlation_id,
        )

        # Step 5: Verify receipt
        assert receipt.received is True
        assert receipt.intent_id == intent.intent_id
        assert receipt.intent_type == "extension"
        assert receipt.target == intent.target
        assert receipt.correlation_id == sample_correlation_id

    def test_deprecate_intent_reaches_orchestrator(
        self,
        deprecate_input: ModelReducerInputPatternLifecycle,
        sample_correlation_id: UUID,
    ) -> None:
        """Reducer emits deprecate intent; orchestrator receives and logs it."""
        # Reducer processes the transition
        reducer_output = handle_pattern_lifecycle_process(deprecate_input)
        assert len(reducer_output.intents) == 1

        intent = reducer_output.intents[0]

        # Orchestrator receives
        receipt = handle_receive_intent(
            intent,
            correlation_id=sample_correlation_id,
        )
        assert receipt.received is True
        assert receipt.intent_type == "extension"

    def test_failed_transition_emits_no_intents(
        self,
        sample_correlation_id: UUID,
        sample_request_id: UUID,
        sample_pattern_id: str,
    ) -> None:
        """Failed reducer transition emits no intents for orchestrator."""
        # Create an invalid transition (candidate -> deprecated via promote_direct)
        invalid_input = ModelReducerInputPatternLifecycle(
            fsm_type="PATTERN_LIFECYCLE",
            entity_id=sample_pattern_id,
            action="promote_direct",
            payload=ModelPatternLifecycleReducerInput(
                pattern_id=sample_pattern_id,
                from_status="candidate",
                to_status="deprecated",  # Wrong: promote_direct should go to validated
                trigger="promote_direct",
                actor_type="handler",
                actor="test_actor",
                reason="Invalid transition test",
            ),
            correlation_id=sample_correlation_id,
            request_id=sample_request_id,
        )

        reducer_output = handle_pattern_lifecycle_process(invalid_input)

        # Failed transition emits no intents
        assert len(reducer_output.intents) == 0

        # Orchestrator receives empty batch
        receipts = handle_receive_intents(
            reducer_output.intents,
            correlation_id=sample_correlation_id,
        )
        assert receipts == []

    def test_batch_intents_from_multiple_transitions(
        self,
        sample_correlation_id: UUID,
        sample_request_id: UUID,
    ) -> None:
        """Multiple reducer transitions produce intents that orchestrator batch-processes."""
        # Two separate successful transitions
        inputs = [
            ModelReducerInputPatternLifecycle(
                fsm_type="PATTERN_LIFECYCLE",
                entity_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                action="promote_direct",
                payload=ModelPatternLifecycleReducerInput(
                    pattern_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    from_status="candidate",
                    to_status="validated",
                    trigger="promote_direct",
                    actor_type="handler",
                    actor="test_actor",
                    reason="First promotion",
                ),
                correlation_id=sample_correlation_id,
                request_id=sample_request_id,
            ),
            ModelReducerInputPatternLifecycle(
                fsm_type="PATTERN_LIFECYCLE",
                entity_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
                action="deprecate",
                payload=ModelPatternLifecycleReducerInput(
                    pattern_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
                    from_status="validated",
                    to_status="deprecated",
                    trigger="deprecate",
                    actor_type="system",
                    actor="test_system",
                    reason="Deprecation",
                ),
                correlation_id=sample_correlation_id,
                request_id=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
            ),
        ]

        # Collect intents from both transitions
        all_intents: list[ModelIntent] = []
        for input_data in inputs:
            output = handle_pattern_lifecycle_process(input_data)
            all_intents.extend(output.intents)

        assert len(all_intents) == 2

        # Orchestrator batch-processes
        receipts = handle_receive_intents(
            tuple(all_intents),
            correlation_id=sample_correlation_id,
        )
        assert len(receipts) == 2
        assert all(r.received for r in receipts)
        assert all(r.correlation_id == sample_correlation_id for r in receipts)

    def test_intent_payload_contains_pattern_data(
        self,
        promote_direct_input: ModelReducerInputPatternLifecycle,
        sample_pattern_id: str,
    ) -> None:
        """The intent payload carries pattern lifecycle data observable at orchestrator."""
        reducer_output = handle_pattern_lifecycle_process(promote_direct_input)
        intent = reducer_output.intents[0]

        # Verify payload contains pattern lifecycle data
        payload = intent.payload
        assert isinstance(payload, ModelPayloadExtension)
        data = payload.data

        # The intent data should contain pattern lifecycle details
        assert data.get("pattern_id") == sample_pattern_id
        assert data.get("from_status") == "candidate"
        assert data.get("to_status") == "validated"
        assert data.get("trigger") == "promote_direct"

    def test_intent_data_is_observable_via_receipt(
        self,
        promote_direct_input: ModelReducerInputPatternLifecycle,
        sample_correlation_id: UUID,
    ) -> None:
        """Intent data is observable: receipt captures type, target, and ID."""
        reducer_output = handle_pattern_lifecycle_process(promote_direct_input)
        intent = reducer_output.intents[0]

        receipt = handle_receive_intent(
            intent,
            correlation_id=sample_correlation_id,
        )

        # All key intent fields are observable in the receipt
        assert receipt.intent_id is not None
        assert receipt.intent_type == "extension"
        assert "postgres://patterns/" in receipt.target
        assert receipt.correlation_id == sample_correlation_id
        assert receipt.received_at is not None
        assert "extension" in receipt.message
