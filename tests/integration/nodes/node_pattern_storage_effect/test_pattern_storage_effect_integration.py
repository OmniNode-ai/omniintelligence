# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Integration tests for Pattern Storage Effect node.

Tests the NodePatternStorageEffect with mock infrastructure (MockPatternStore,
MockPatternStateManager, EventBusInmemory) following the established integration
test patterns in the codebase.

Test Coverage:
    - Store pattern operation with governance validation
    - Promote pattern operation with state transitions
    - Idempotency guarantees
    - Event publishing to Kafka topics
    - Governance rejection for low confidence patterns

Infrastructure:
    - MockPatternStore: In-memory pattern storage
    - MockPatternStateManager: In-memory state management
    - EventBusInmemory: In-memory Kafka-like event bus (from omnibase_infra)

Reference:
    - OMN-1668: Pattern storage effect node implementation
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_promote_pattern import (
    PatternNotFoundError,
    PatternStateTransitionError,
    handle_promote_pattern,
)
from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_store_pattern import (
    handle_store_pattern,
)
from omniintelligence.nodes.node_pattern_storage_effect.models import (
    EnumPatternState,
    ModelPatternMetricsSnapshot,
    PatternStorageGovernance,
)
from omniintelligence.nodes.node_pattern_storage_effect.node import NodePatternStorageEffect
from omniintelligence.nodes.node_pattern_storage_effect.contract_loader import (
    get_contract_loader,
)
from omniintelligence.nodes.node_pattern_storage_effect.handlers import (
    route_storage_operation,
)

from .conftest import (
    KAFKA_AVAILABLE,
    MockPatternStateManager,
    MockPatternStore,
    create_valid_input,
)


# =============================================================================
# Store Pattern Integration Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestStorePatternIntegration:
    """Integration tests for the store_pattern operation."""

    async def test_store_pattern_with_mock_store(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Test storing a pattern with the mock pattern store.

        Verifies:
        - Pattern is stored successfully
        - Returns ModelPatternStoredEvent with correct fields
        - Pattern is retrievable from store
        """
        input_data = create_valid_input(
            confidence=0.85,
            domain="integration_test_domain",
        )

        result = await handle_store_pattern(
            input_data,
            pattern_store=mock_pattern_store,
            conn=None,
        )

        # Verify result
        assert result.pattern_id == input_data.pattern_id
        assert result.domain == "integration_test_domain"
        assert result.confidence == 0.85
        assert result.state == EnumPatternState.CANDIDATE
        assert result.version == 1

        # Verify pattern in store
        assert input_data.pattern_id in mock_pattern_store.patterns
        stored = mock_pattern_store.patterns[input_data.pattern_id]
        assert stored["domain"] == "integration_test_domain"
        assert stored["is_current"] is True

    async def test_store_pattern_minimum_confidence(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Test storing a pattern at exactly minimum confidence threshold.

        Verifies:
        - Pattern with confidence == MIN_CONFIDENCE (0.5) is accepted
        - No governance violation raised
        """
        min_confidence = PatternStorageGovernance.MIN_CONFIDENCE
        input_data = create_valid_input(confidence=min_confidence)

        result = await handle_store_pattern(
            input_data,
            pattern_store=mock_pattern_store,
            conn=None,
        )

        assert result.confidence == min_confidence
        assert result.state == EnumPatternState.CANDIDATE
        assert len(mock_pattern_store.patterns) == 1

    async def test_store_pattern_creates_audit_metadata(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Test that stored pattern includes metadata for audit trail.

        Verifies:
        - Actor is stored
        - Source run ID is stored
        - Correlation ID is stored
        - Tags are stored
        """
        correlation_id = uuid4()
        input_data = create_valid_input(
            correlation_id=correlation_id,
            actor="test_actor",
            source_run_id="run_12345",
            tags=["audit", "test"],
        )

        result = await handle_store_pattern(
            input_data,
            pattern_store=mock_pattern_store,
            conn=None,
        )

        stored = mock_pattern_store.patterns[result.pattern_id]
        assert stored["actor"] == "test_actor"
        assert stored["source_run_id"] == "run_12345"
        assert stored["correlation_id"] == correlation_id
        assert "audit" in stored["metadata"]["tags"]


# =============================================================================
# Idempotency Integration Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestIdempotencyIntegration:
    """Integration tests for idempotency guarantees."""

    async def test_idempotent_store_returns_same_result(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Test that storing the same pattern twice returns identical results.

        Verifies:
        - Same (pattern_id, signature_hash) returns same pattern_id
        - Only one pattern is stored
        - Version number remains unchanged
        """
        pattern_id = uuid4()
        signature_hash = f"idem_hash_{uuid4().hex[:12]}"

        input_data = create_valid_input(
            pattern_id=pattern_id,
            signature_hash=signature_hash,
        )

        # First store
        result1 = await handle_store_pattern(
            input_data,
            pattern_store=mock_pattern_store,
            conn=None,
        )

        # Second store (idempotent)
        result2 = await handle_store_pattern(
            input_data,
            pattern_store=mock_pattern_store,
            conn=None,
        )

        # Same pattern_id returned
        assert result1.pattern_id == result2.pattern_id

        # Only one pattern stored
        assert len(mock_pattern_store.patterns) == 1

        # Version unchanged
        assert result1.version == result2.version == 1

    async def test_idempotent_preserves_original_timestamp(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Test that idempotent call preserves original stored_at timestamp.

        Verifies:
        - First stored_at timestamp is preserved
        - Second call returns consistent timestamp
        """
        input_data = create_valid_input()

        result1 = await handle_store_pattern(
            input_data,
            pattern_store=mock_pattern_store,
            conn=None,
        )

        original_stored_at = mock_pattern_store.patterns[input_data.pattern_id]["stored_at"]

        # Wait a tiny bit to ensure time has moved
        import asyncio
        await asyncio.sleep(0.001)

        result2 = await handle_store_pattern(
            input_data,
            pattern_store=mock_pattern_store,
            conn=None,
        )

        # Original timestamp preserved in store
        assert mock_pattern_store.patterns[input_data.pattern_id]["stored_at"] == original_stored_at

    async def test_different_pattern_id_creates_new_version(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Test that different pattern_id for same lineage creates new version.

        Verifies:
        - Same (domain, signature_hash) with different pattern_id increments version
        - Previous version marked as not current
        """
        signature_hash = f"lineage_hash_{uuid4().hex[:12]}"
        domain = "version_test_domain"

        # First pattern in lineage
        input1 = create_valid_input(
            pattern_id=uuid4(),
            signature_hash=signature_hash,
            domain=domain,
        )
        result1 = await handle_store_pattern(input1, pattern_store=mock_pattern_store, conn=None)

        # Second pattern in same lineage
        input2 = create_valid_input(
            pattern_id=uuid4(),
            signature_hash=signature_hash,
            domain=domain,
        )
        result2 = await handle_store_pattern(input2, pattern_store=mock_pattern_store, conn=None)

        # Versions should increment
        assert result1.version == 1
        assert result2.version == 2

        # First should no longer be current
        assert mock_pattern_store.patterns[result1.pattern_id]["is_current"] is False
        assert mock_pattern_store.patterns[result2.pattern_id]["is_current"] is True


# =============================================================================
# Governance Rejection Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestGovernanceRejectionIntegration:
    """Integration tests for governance invariant enforcement."""

    async def test_reject_low_confidence_pattern(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Test that patterns below MIN_CONFIDENCE are rejected.

        Verifies:
        - ValueError raised for confidence < 0.5
        - Pattern is NOT stored in the store
        - Error message mentions governance/confidence
        """
        # Create input dict to bypass Pydantic validation
        # (Pydantic also validates, but we want to test handler layer)
        # Since ModelPatternStorageInput validates at model level,
        # the handler should still reject if it gets through

        # Try with confidence just below threshold
        low_confidence = PatternStorageGovernance.MIN_CONFIDENCE - 0.01

        # Pydantic should reject this at model level
        with pytest.raises(ValueError) as exc_info:
            create_valid_input(confidence=low_confidence)

        assert "confidence" in str(exc_info.value).lower()

        # Verify nothing stored
        assert len(mock_pattern_store.patterns) == 0

    async def test_reject_zero_confidence(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Test that zero confidence patterns are rejected.

        Verifies:
        - ValueError raised for confidence == 0.0
        """
        with pytest.raises(ValueError):
            create_valid_input(confidence=0.0)

        assert len(mock_pattern_store.patterns) == 0

    async def test_reject_negative_confidence(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Test that negative confidence patterns are rejected.

        Verifies:
        - ValueError raised for confidence < 0
        """
        with pytest.raises(ValueError):
            create_valid_input(confidence=-0.5)

        assert len(mock_pattern_store.patterns) == 0


# =============================================================================
# Promote Pattern Integration Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestPromotePatternIntegration:
    """Integration tests for the promote_pattern operation."""

    async def test_promote_candidate_to_provisional(
        self,
        mock_state_manager: MockPatternStateManager,
    ) -> None:
        """Test promoting a pattern from CANDIDATE to PROVISIONAL.

        Verifies:
        - Valid transition CANDIDATE -> PROVISIONAL succeeds
        - State is updated in manager
        - Transition is recorded
        - Event contains correct from_state and to_state
        """
        pattern_id = uuid4()

        # Set initial state
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        result = await handle_promote_pattern(
            pattern_id=pattern_id,
            to_state=EnumPatternState.PROVISIONAL,
            reason="Pattern passed verification",
            state_manager=mock_state_manager,
            conn=None,
            actor="test_promotion",
        )

        # Verify result
        assert result.pattern_id == pattern_id
        assert result.from_state == EnumPatternState.CANDIDATE
        assert result.to_state == EnumPatternState.PROVISIONAL
        assert result.reason == "Pattern passed verification"
        assert result.actor == "test_promotion"

        # Verify state updated
        assert mock_state_manager.states[pattern_id] == EnumPatternState.PROVISIONAL

        # Verify transition recorded
        assert len(mock_state_manager.transitions) == 1
        assert mock_state_manager.transitions[0].from_state == EnumPatternState.CANDIDATE
        assert mock_state_manager.transitions[0].to_state == EnumPatternState.PROVISIONAL

    async def test_promote_provisional_to_validated(
        self,
        mock_state_manager: MockPatternStateManager,
    ) -> None:
        """Test promoting a pattern from PROVISIONAL to VALIDATED.

        Verifies:
        - Valid transition PROVISIONAL -> VALIDATED succeeds
        - Terminal state reached
        """
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.PROVISIONAL)

        result = await handle_promote_pattern(
            pattern_id=pattern_id,
            to_state=EnumPatternState.VALIDATED,
            reason="Pattern met all validation criteria",
            state_manager=mock_state_manager,
            conn=None,
            metrics_snapshot=ModelPatternMetricsSnapshot(
                confidence=0.95,
                match_count=100,
                success_rate=0.99,
            ),
        )

        assert result.to_state == EnumPatternState.VALIDATED
        assert result.metrics_snapshot is not None
        assert result.metrics_snapshot.confidence == 0.95
        assert mock_state_manager.states[pattern_id] == EnumPatternState.VALIDATED

    async def test_reject_invalid_transition(
        self,
        mock_state_manager: MockPatternStateManager,
    ) -> None:
        """Test that invalid state transitions are rejected.

        Verifies:
        - CANDIDATE -> VALIDATED is rejected
        - PatternStateTransitionError raised
        """
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        with pytest.raises(PatternStateTransitionError) as exc_info:
            await handle_promote_pattern(
                pattern_id=pattern_id,
                to_state=EnumPatternState.VALIDATED,  # Invalid: must go through PROVISIONAL
                reason="Trying to skip provisional",
                state_manager=mock_state_manager,
                conn=None,
            )

        assert exc_info.value.from_state == EnumPatternState.CANDIDATE
        assert exc_info.value.to_state == EnumPatternState.VALIDATED

    async def test_reject_transition_from_terminal_state(
        self,
        mock_state_manager: MockPatternStateManager,
    ) -> None:
        """Test that transitions from VALIDATED (terminal) are rejected.

        Verifies:
        - VALIDATED -> any state is rejected
        - Cannot go backwards
        """
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.VALIDATED)

        with pytest.raises(PatternStateTransitionError):
            await handle_promote_pattern(
                pattern_id=pattern_id,
                to_state=EnumPatternState.PROVISIONAL,  # Cannot go backwards
                reason="Trying to demote",
                state_manager=mock_state_manager,
                conn=None,
            )

    async def test_pattern_not_found(
        self,
        mock_state_manager: MockPatternStateManager,
    ) -> None:
        """Test that promoting non-existent pattern raises PatternNotFoundError.

        Verifies:
        - PatternNotFoundError raised for unknown pattern_id
        """
        unknown_pattern_id = uuid4()

        with pytest.raises(PatternNotFoundError) as exc_info:
            await handle_promote_pattern(
                pattern_id=unknown_pattern_id,
                to_state=EnumPatternState.PROVISIONAL,
                reason="Pattern does not exist",
                state_manager=mock_state_manager,
                conn=None,
            )

        assert exc_info.value.pattern_id == unknown_pattern_id


# =============================================================================
# Event Publishing Integration Tests (with EventBusInmemory)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skipif(not KAFKA_AVAILABLE, reason="Event bus not available")
class TestEventPublishingIntegration:
    """Integration tests for Kafka event publishing using EventBusInmemory."""

    async def test_store_pattern_event_structure(
        self,
        event_bus: Any,
        kafka_publisher_adapter: Any,
        pattern_stored_topic: str,
        test_node_identity: Any,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Test that pattern-stored events have correct structure.

        Verifies:
        - Event is published to correct topic
        - Event contains required fields
        """
        from omnibase_infra.event_bus.models import ModelEventMessage

        received_events: list[ModelEventMessage] = []

        async def event_handler(msg: ModelEventMessage) -> None:
            received_events.append(msg)

        # Subscribe to output topic
        unsubscribe = await event_bus.subscribe(
            pattern_stored_topic,
            test_node_identity,
            event_handler,
        )

        try:
            # Store a pattern
            input_data = create_valid_input()
            result = await handle_store_pattern(
                input_data,
                pattern_store=mock_pattern_store,
                conn=None,
            )

            # Publish the event (simulating what the node would do)
            event_data = {
                "event_type": "PatternStored",
                "pattern_id": str(result.pattern_id),
                "domain": result.domain,
                "signature_hash": result.signature_hash,
                "version": result.version,
                "confidence": result.confidence,
                "state": result.state.value,
                "stored_at": result.stored_at.isoformat(),
            }

            await kafka_publisher_adapter.publish(
                topic=pattern_stored_topic,
                key=str(result.pattern_id),
                value=event_data,
            )

            # Verify event received
            assert len(received_events) == 1
            event_content = json.loads(received_events[0].value)
            assert event_content["event_type"] == "PatternStored"
            assert event_content["pattern_id"] == str(result.pattern_id)
            assert event_content["state"] == "candidate"

        finally:
            await unsubscribe()

    async def test_promote_pattern_event_structure(
        self,
        event_bus: Any,
        kafka_publisher_adapter: Any,
        pattern_promoted_topic: str,
        test_node_identity: Any,
        mock_state_manager: MockPatternStateManager,
    ) -> None:
        """Test that pattern-promoted events have correct structure.

        Verifies:
        - Event contains from_state, to_state, reason
        - Metrics snapshot is included if provided
        """
        from omnibase_infra.event_bus.models import ModelEventMessage

        received_events: list[ModelEventMessage] = []

        async def event_handler(msg: ModelEventMessage) -> None:
            received_events.append(msg)

        # Subscribe to output topic
        unsubscribe = await event_bus.subscribe(
            pattern_promoted_topic,
            test_node_identity,
            event_handler,
        )

        try:
            pattern_id = uuid4()
            mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

            result = await handle_promote_pattern(
                pattern_id=pattern_id,
                to_state=EnumPatternState.PROVISIONAL,
                reason="Verification passed",
                state_manager=mock_state_manager,
                conn=None,
                metrics_snapshot=ModelPatternMetricsSnapshot(
                    confidence=0.9,
                    match_count=50,
                    success_rate=0.95,
                ),
            )

            # Publish the event
            event_data = {
                "event_type": "PatternPromoted",
                "pattern_id": str(result.pattern_id),
                "from_state": result.from_state.value,
                "to_state": result.to_state.value,
                "reason": result.reason,
                "promoted_at": result.promoted_at.isoformat(),
                "metrics_snapshot": {
                    "confidence": result.metrics_snapshot.confidence,
                    "match_count": result.metrics_snapshot.match_count,
                    "success_rate": result.metrics_snapshot.success_rate,
                } if result.metrics_snapshot else None,
            }

            await kafka_publisher_adapter.publish(
                topic=pattern_promoted_topic,
                key=str(result.pattern_id),
                value=event_data,
            )

            # Verify event received
            assert len(received_events) == 1
            event_content = json.loads(received_events[0].value)
            assert event_content["event_type"] == "PatternPromoted"
            assert event_content["from_state"] == "candidate"
            assert event_content["to_state"] == "provisional"
            assert event_content["metrics_snapshot"]["confidence"] == 0.9

        finally:
            await unsubscribe()

    async def test_event_history_for_debugging(
        self,
        event_bus: Any,
        kafka_publisher_adapter: Any,
        pattern_stored_topic: str,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Test that event history can be used for debugging.

        Verifies:
        - get_event_history returns published events
        - Events can be inspected for debugging
        """
        # Store and publish a pattern event
        input_data = create_valid_input()
        result = await handle_store_pattern(
            input_data,
            pattern_store=mock_pattern_store,
            conn=None,
        )

        event_data = {
            "event_type": "PatternStored",
            "pattern_id": str(result.pattern_id),
            "domain": result.domain,
        }

        await kafka_publisher_adapter.publish(
            topic=pattern_stored_topic,
            key=str(result.pattern_id),
            value=event_data,
        )

        # Verify history
        history = await event_bus.get_event_history(topic=pattern_stored_topic)
        assert len(history) >= 1

        # Latest event should be ours
        latest_event = json.loads(history[-1].value)
        assert latest_event["pattern_id"] == str(result.pattern_id)


# =============================================================================
# Full Node Integration Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestNodePatternStorageEffectIntegration:
    """Integration tests for the NodePatternStorageEffect handlers.

    Note: With the declarative pattern (OMN-1757), the node is a pure shell.
    Tests now call handlers directly via route_storage_operation instead of
    instantiating the node with a registry.
    """

    async def test_store_pattern_via_route_handler(
        self,
        mock_pattern_store: MockPatternStore,
        mock_state_manager: MockPatternStateManager,
    ) -> None:
        """Test storing a pattern via the route_storage_operation handler.

        Verifies:
        - Contract-driven dispatch works via route_storage_operation
        - Result contains expected fields
        """
        input_data = create_valid_input()

        result = await route_storage_operation(
            operation="store_pattern",
            input_data=input_data.model_dump(mode="json"),
            pattern_store=mock_pattern_store,
            state_manager=mock_state_manager,
            conn=None,
        )

        assert result["success"] is True
        assert result["event_type"] == "pattern_stored"
        assert result["event"]["pattern_id"] == str(input_data.pattern_id)
        assert result["event"]["state"] == "candidate"

    async def test_store_pattern_via_route_handler_returns_typed_result(
        self,
        mock_pattern_store: MockPatternStore,
        mock_state_manager: MockPatternStateManager,
    ) -> None:
        """Test storing a pattern via route_storage_operation returns proper envelope.

        Verifies:
        - route_storage_operation returns success envelope
        - event contains expected fields
        """
        input_data = create_valid_input()

        result = await route_storage_operation(
            operation="store_pattern",
            input_data=input_data.model_dump(mode="json"),
            pattern_store=mock_pattern_store,
            state_manager=mock_state_manager,
            conn=None,
        )

        assert result["success"] is True
        assert result["event_type"] == "pattern_stored"
        assert result["event"]["pattern_id"] == str(input_data.pattern_id)
        assert result["event"]["state"] == "candidate"

    async def test_promote_pattern_via_route_handler_returns_typed_result(
        self,
        mock_pattern_store: MockPatternStore,
        mock_state_manager: MockPatternStateManager,
    ) -> None:
        """Test promoting a pattern via route_storage_operation returns proper envelope.

        Verifies:
        - route_storage_operation returns success envelope
        - event contains expected fields
        """
        pattern_id = uuid4()
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        result = await route_storage_operation(
            operation="promote_pattern",
            input_data={
                "pattern_id": str(pattern_id),
                "to_state": "provisional",
                "reason": "Test promotion",
            },
            pattern_store=mock_pattern_store,
            state_manager=mock_state_manager,
            conn=None,
        )

        assert result["success"] is True
        assert result["event_type"] == "pattern_promoted"
        assert result["event"]["pattern_id"] == str(pattern_id)
        assert result["event"]["from_state"] == "candidate"
        assert result["event"]["to_state"] == "provisional"

    async def test_contract_introspection_properties(self) -> None:
        """Test that contract introspection properties are accessible.

        Verifies:
        - subscribe_topics returns topic list
        - publish_topics returns topic list
        - supported_operations returns operation names

        Note: Introspection is done via ContractLoader, not the node itself,
        following the declarative pattern where nodes are thin shells.
        """
        loader = get_contract_loader()

        # Verify introspection works
        assert isinstance(loader.subscribe_topics, list)
        assert isinstance(loader.publish_topics, list)
        operations = loader.list_operations()
        assert isinstance(operations, list)

        # Check expected operations are present
        assert "store_pattern" in operations
        assert "promote_pattern" in operations


# =============================================================================
# End-to-End Workflow Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestEndToEndWorkflow:
    """End-to-end integration tests for full pattern lifecycle.

    Note: With the declarative pattern (OMN-1757), tests call handlers directly
    via route_storage_operation instead of instantiating the node with a registry.
    """

    async def test_full_pattern_lifecycle(
        self,
        mock_pattern_store: MockPatternStore,
        mock_state_manager: MockPatternStateManager,
    ) -> None:
        """Test full pattern lifecycle: store -> promote to provisional -> promote to validated.

        Verifies:
        - Pattern can be stored as CANDIDATE via route_storage_operation
        - Pattern can be promoted to PROVISIONAL via route_storage_operation
        - Pattern can be promoted to VALIDATED via route_storage_operation
        - All states are tracked correctly
        """
        # Step 1: Store pattern (starts as CANDIDATE)
        input_data = create_valid_input(
            confidence=0.85,
            domain="lifecycle_test",
        )
        store_result = await route_storage_operation(
            operation="store_pattern",
            input_data=input_data.model_dump(mode="json"),
            pattern_store=mock_pattern_store,
            state_manager=mock_state_manager,
            conn=None,
        )

        assert store_result["success"] is True
        assert store_result["event"]["state"] == "candidate"

        # Extract pattern_id from result for subsequent operations
        pattern_id_str = store_result["event"]["pattern_id"]

        # Set up state manager for promotion (need UUID for state manager)
        pattern_id = UUID(pattern_id_str)
        mock_state_manager.set_state(pattern_id, EnumPatternState.CANDIDATE)

        # Step 2: Promote to PROVISIONAL
        promote_result_1 = await route_storage_operation(
            operation="promote_pattern",
            input_data={
                "pattern_id": pattern_id_str,
                "to_state": "provisional",
                "reason": "Passed initial verification",
                "metrics_snapshot": {
                    "confidence": 0.87,
                    "match_count": 25,
                    "success_rate": 0.92,
                },
            },
            pattern_store=mock_pattern_store,
            state_manager=mock_state_manager,
            conn=None,
        )

        assert promote_result_1["success"] is True
        assert promote_result_1["event"]["from_state"] == "candidate"
        assert promote_result_1["event"]["to_state"] == "provisional"

        # Step 3: Promote to VALIDATED
        promote_result_2 = await route_storage_operation(
            operation="promote_pattern",
            input_data={
                "pattern_id": pattern_id_str,
                "to_state": "validated",
                "reason": "Met all validation criteria",
                "metrics_snapshot": {
                    "confidence": 0.95,
                    "match_count": 100,
                    "success_rate": 0.98,
                },
            },
            pattern_store=mock_pattern_store,
            state_manager=mock_state_manager,
            conn=None,
        )

        assert promote_result_2["success"] is True
        assert promote_result_2["event"]["from_state"] == "provisional"
        assert promote_result_2["event"]["to_state"] == "validated"

        # Verify final state
        assert mock_state_manager.states[pattern_id] == EnumPatternState.VALIDATED

        # Verify all transitions recorded
        assert len(mock_state_manager.transitions) == 2

    async def test_versioning_with_promotions(
        self,
        mock_pattern_store: MockPatternStore,
        mock_state_manager: MockPatternStateManager,
    ) -> None:
        """Test that multiple versions can coexist with different promotion states.

        Verifies:
        - Multiple versions of same lineage can be created
        - Each version can be promoted independently
        - Only latest version is current
        """
        signature_hash = f"multi_version_hash_{uuid4().hex[:12]}"
        domain = "multi_version_test"

        # Create version 1 and promote it
        input_v1 = create_valid_input(
            pattern_id=uuid4(),
            signature_hash=signature_hash,
            domain=domain,
            confidence=0.75,
        )
        result_v1 = await handle_store_pattern(input_v1, pattern_store=mock_pattern_store, conn=None)
        mock_state_manager.set_state(result_v1.pattern_id, EnumPatternState.CANDIDATE)

        await handle_promote_pattern(
            pattern_id=result_v1.pattern_id,
            to_state=EnumPatternState.PROVISIONAL,
            reason="V1 promoted",
            state_manager=mock_state_manager,
            conn=None,
        )

        # Create version 2 (now the current version)
        input_v2 = create_valid_input(
            pattern_id=uuid4(),
            signature_hash=signature_hash,
            domain=domain,
            confidence=0.9,
        )
        result_v2 = await handle_store_pattern(input_v2, pattern_store=mock_pattern_store, conn=None)

        # Verify versions
        assert result_v1.version == 1
        assert result_v2.version == 2

        # Verify is_current flags
        assert mock_pattern_store.patterns[result_v1.pattern_id]["is_current"] is False
        assert mock_pattern_store.patterns[result_v2.pattern_id]["is_current"] is True

        # V1 is still PROVISIONAL in state manager
        assert mock_state_manager.states[result_v1.pattern_id] == EnumPatternState.PROVISIONAL


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TestEndToEndWorkflow",
    "TestEventPublishingIntegration",
    "TestGovernanceRejectionIntegration",
    "TestIdempotencyIntegration",
    "TestNodePatternStorageEffectIntegration",
    "TestPromotePatternIntegration",
    "TestStorePatternIntegration",
]
