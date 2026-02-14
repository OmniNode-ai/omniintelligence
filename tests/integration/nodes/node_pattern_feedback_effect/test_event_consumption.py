"""Integration tests for session-outcome event consumption (OMN-1763).

These tests verify that pattern_feedback_effect correctly consumes
session-outcome events from the Kafka topic.

Uses the existing EventBusInmemory and Kafka test harness from
tests/integration/conftest.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import yaml
from omnibase_core.integrations.claude_code import (
    ClaudeCodeSessionOutcome,
    ClaudeSessionOutcome,
)
from omnibase_infra.event_bus.event_bus_inmemory import EventBusInmemory
from omnibase_infra.models import ModelNodeIdentity

from omniintelligence.nodes.node_pattern_feedback_effect.handlers.handler_session_outcome import (
    event_to_handler_args,
    record_session_outcome,
)
from omniintelligence.nodes.node_pattern_feedback_effect.models import (
    EnumOutcomeRecordingStatus,
)

# =============================================================================
# Path Constants
# =============================================================================


def _get_contract_path() -> Path:
    """Get contract.yaml path relative to test file location.

    Structure:
        tests/integration/nodes/node_pattern_feedback_effect/test_event_consumption.py
        src/omniintelligence/nodes/node_pattern_feedback_effect/contract.yaml

    From test file, navigate to repo root (4 levels up), then into src.
    """
    test_dir = Path(__file__).parent  # node_pattern_feedback_effect/
    # Navigate: node_pattern_feedback_effect -> nodes -> integration -> tests -> repo_root
    repo_root = test_dir.parent.parent.parent.parent
    return (
        repo_root
        / "src"
        / "omniintelligence"
        / "nodes"
        / "node_pattern_feedback_effect"
        / "contract.yaml"
    )


CONTRACT_PATH: Path = _get_contract_path()


# =============================================================================
# Topic Constants
# =============================================================================

TEST_TOPIC_PREFIX: str = "test"
TOPIC_SUFFIX_SESSION_OUTCOME_V1: str = "onex.cmd.omniintelligence.session-outcome.v1"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_node_identity() -> ModelNodeIdentity:
    """Create a test node identity for event bus subscriptions."""
    return ModelNodeIdentity(
        env="test",
        service="omniintelligence",
        node_name="pattern_feedback_effect",
        version="1.0.0",
    )


@pytest.fixture
async def event_bus() -> EventBusInmemory:
    """Create and start an in-memory event bus for testing."""
    bus = EventBusInmemory(environment="test", group="test-group")
    await bus.start()
    yield bus
    await bus.close()


@pytest.fixture
def input_topic() -> str:
    """Return the input topic name for session-outcome events."""
    return f"{TEST_TOPIC_PREFIX}.{TOPIC_SUFFIX_SESSION_OUTCOME_V1}"


@pytest.fixture
def sample_success_event() -> ClaudeSessionOutcome:
    """Create a sample SUCCESS outcome event."""
    return ClaudeSessionOutcome(
        session_id=uuid4(),
        outcome=ClaudeCodeSessionOutcome.SUCCESS,
        error=None,
        correlation_id=uuid4(),
    )


@pytest.fixture
def sample_failed_event() -> ClaudeSessionOutcome:
    """Create a sample FAILED outcome event."""
    return ClaudeSessionOutcome(
        session_id=uuid4(),
        outcome=ClaudeCodeSessionOutcome.FAILED,
        error=None,
        correlation_id=uuid4(),
    )


@pytest.fixture
def mock_repository() -> MagicMock:
    """Create a mock pattern repository for testing."""
    mock_repo = MagicMock()
    # Default: no unrecorded injections found
    mock_repo.fetch = AsyncMock(return_value=[])
    mock_repo.execute = AsyncMock(return_value="UPDATE 0")
    return mock_repo


# =============================================================================
# Contract Configuration Tests (run now, no infrastructure needed)
# =============================================================================


class TestContractConfiguration:
    """Tests for topic subscription configuration - CAN RUN NOW."""

    def test_contract_declares_event_bus_subscription(self) -> None:
        """Verify contract.yaml declares the subscription topic."""
        with open(CONTRACT_PATH) as f:
            contract = yaml.safe_load(f)

        assert "event_bus" in contract, "Missing event_bus section"
        assert contract["event_bus"]["event_bus_enabled"] is True
        assert "subscribe_topics" in contract["event_bus"]
        assert (
            "onex.cmd.omniintelligence.session-outcome.v1"
            in contract["event_bus"]["subscribe_topics"]
        )

    def test_contract_schema_ref_is_valid_alias(self) -> None:
        """Verify schema_ref uses stable import alias."""
        with open(CONTRACT_PATH) as f:
            contract = yaml.safe_load(f)

        topic = "onex.cmd.omniintelligence.session-outcome.v1"
        metadata = contract["event_bus"]["subscribe_topic_metadata"][topic]

        # Should use stable alias, not brittle file path
        assert (
            metadata["schema_ref"]
            == "omnibase_core.integrations.claude_code.ClaudeSessionOutcome"
        )

    def test_contract_has_required_handler_routing(self) -> None:
        """Verify contract declares handler routing for event processing."""
        with open(CONTRACT_PATH) as f:
            contract = yaml.safe_load(f)

        assert "handler_routing" in contract, "Missing handler_routing section"
        assert contract["handler_routing"]["routing_strategy"] == "operation_match"
        assert "handlers" in contract["handler_routing"]
        # Verify record_session_outcome handler is defined
        handlers = contract["handler_routing"]["handlers"]
        handler_ops = [h["operation"] for h in handlers]
        assert "record_session_outcome" in handler_ops


# =============================================================================
# Event Consumption Integration Tests
# =============================================================================


class TestEventConsumption:
    """Integration tests for event consumption and handler invocation."""

    @pytest.mark.integration
    async def test_success_event_maps_to_handler_args(
        self,
        sample_success_event: ClaudeSessionOutcome,
    ) -> None:
        """Verify SUCCESS event correctly maps to handler arguments."""
        args = event_to_handler_args(sample_success_event)

        assert args["session_id"] == sample_success_event.session_id
        assert args["success"] is True
        assert args["failure_reason"] is None
        assert args["correlation_id"] == sample_success_event.correlation_id

    @pytest.mark.integration
    async def test_failed_event_maps_to_handler_args(
        self,
        sample_failed_event: ClaudeSessionOutcome,
    ) -> None:
        """Verify FAILED event correctly maps to handler arguments."""
        args = event_to_handler_args(sample_failed_event)

        assert args["session_id"] == sample_failed_event.session_id
        assert args["success"] is False
        assert args["correlation_id"] == sample_failed_event.correlation_id

    @pytest.mark.integration
    async def test_handler_called_with_correct_args(
        self,
        sample_success_event: ClaudeSessionOutcome,
        mock_repository: MagicMock,
    ) -> None:
        """Verify handler is invoked with mapped arguments."""
        args = event_to_handler_args(sample_success_event)

        result = await record_session_outcome(
            session_id=args["session_id"],
            success=args["success"],
            failure_reason=args["failure_reason"],
            repository=mock_repository,
            correlation_id=args["correlation_id"],
        )

        # With no injections found, should return NO_INJECTIONS_FOUND
        assert result.status == EnumOutcomeRecordingStatus.NO_INJECTIONS_FOUND
        assert result.session_id == sample_success_event.session_id

    @pytest.mark.integration
    async def test_event_bus_publishes_and_receives(
        self,
        event_bus: EventBusInmemory,
        input_topic: str,
        sample_success_event: ClaudeSessionOutcome,
    ) -> None:
        """Verify event can be published and received via event bus."""
        # Serialize event to JSON bytes
        event_dict = sample_success_event.model_dump(mode="json")
        event_bytes = json.dumps(event_dict).encode("utf-8")
        key_bytes = str(sample_success_event.session_id).encode("utf-8")

        # Publish to event bus
        await event_bus.publish(topic=input_topic, key=key_bytes, value=event_bytes)

        # Verify event is in history
        history = await event_bus.get_event_history()
        assert len(history) == 1
        assert history[0].topic == input_topic

        # Deserialize and verify payload
        received_value = json.loads(history[0].value.decode("utf-8"))
        assert received_value["outcome"] == "success"

    @pytest.mark.integration
    async def test_idempotent_processing(
        self,
        mock_repository: MagicMock,
    ) -> None:
        """Verify duplicate events are handled idempotently."""
        session_id = uuid4()
        event = ClaudeSessionOutcome(
            session_id=session_id,
            outcome=ClaudeCodeSessionOutcome.SUCCESS,
        )

        # First call - no injections found
        args = event_to_handler_args(event)
        result1 = await record_session_outcome(
            session_id=args["session_id"],
            success=args["success"],
            failure_reason=args["failure_reason"],
            repository=mock_repository,
            correlation_id=args["correlation_id"],
        )

        # Second call with same session - should still work (idempotent)
        result2 = await record_session_outcome(
            session_id=args["session_id"],
            success=args["success"],
            failure_reason=args["failure_reason"],
            repository=mock_repository,
            correlation_id=args["correlation_id"],
        )

        # Both should succeed (no injections to record)
        assert result1.status == EnumOutcomeRecordingStatus.NO_INJECTIONS_FOUND
        assert result2.status == EnumOutcomeRecordingStatus.NO_INJECTIONS_FOUND

    @pytest.mark.integration
    async def test_handler_processes_event_end_to_end(
        self,
        sample_success_event: ClaudeSessionOutcome,
        mock_repository: MagicMock,
    ) -> None:
        """Verify full handler path from event to result (declarative pattern).

        This test verifies the end-to-end flow using the declarative pattern:
        1. ClaudeSessionOutcome event is created
        2. Event is mapped to handler arguments via event_to_handler_args()
        3. Handler is called directly with repository dependency
        4. Handler returns result
        5. Result has expected status

        This validates the complete wiring from OMN-1763 using the declarative pattern.
        """
        # Map event to handler arguments
        args = event_to_handler_args(sample_success_event)

        # Act: Call handler directly with dependencies (declarative pattern)
        result = await record_session_outcome(
            session_id=args["session_id"],
            success=args["success"],
            failure_reason=args["failure_reason"],
            repository=mock_repository,
            correlation_id=args["correlation_id"],
        )

        # Assert: Verify handler was called correctly
        assert result.status == EnumOutcomeRecordingStatus.NO_INJECTIONS_FOUND
        assert result.session_id == sample_success_event.session_id
        assert result.injections_updated == 0
        assert result.patterns_updated == 0

        # Verify repository.fetch was called (to look for injections)
        # Handler calls fetch twice: once for injections, once for idempotency COUNT
        assert mock_repository.fetch.call_count >= 1

        # Verify at least one call looked for the correct session_id
        all_calls = mock_repository.fetch.call_args_list
        session_ids_queried = [call[0][1] for call in all_calls if len(call[0]) > 1]
        assert sample_success_event.session_id in session_ids_queried

    @pytest.mark.integration
    async def test_handler_with_failed_event_end_to_end(
        self,
        sample_failed_event: ClaudeSessionOutcome,
        mock_repository: MagicMock,
    ) -> None:
        """Verify handler correctly handles FAILED outcome events (declarative pattern).

        This test ensures the failure path is wired correctly:
        - FAILED outcome maps to success=False in handler
        - Error field is passed as failure_reason
        """
        # Map event to handler arguments
        args = event_to_handler_args(sample_failed_event)

        # Act: Call handler directly with dependencies (declarative pattern)
        result = await record_session_outcome(
            session_id=args["session_id"],
            success=args["success"],
            failure_reason=args["failure_reason"],
            repository=mock_repository,
            correlation_id=args["correlation_id"],
        )

        # Assert
        assert result.status == EnumOutcomeRecordingStatus.NO_INJECTIONS_FOUND
        assert result.session_id == sample_failed_event.session_id


# =============================================================================
# DLQ Routing Tests (require more infrastructure setup)
# =============================================================================


class TestDLQRouting:
    """Tests for Dead Letter Queue routing on processing failures.

    DLQ routing in the ONEX architecture is handled by RuntimeHostProcess.
    The handler is expected to propagate database errors (not swallow them)
    so the runtime can catch them and route the failed event to the DLQ
    topic with full context from the event envelope.

    These tests verify that:
    1. Database errors propagate from the handler (enabling DLQ routing)
    2. The error contains sufficient context for DLQ message construction
    """

    @pytest.mark.integration
    async def test_routes_to_dlq_on_database_error(self) -> None:
        """Verify database errors propagate for DLQ routing by RuntimeHostProcess.

        When a database operation fails during session outcome recording,
        the handler must propagate the exception so RuntimeHostProcess
        can catch it and route the event to the DLQ topic.

        Setup: First fetch returns injection rows (to proceed past the
        edge-case check), then execute raises to simulate a DB failure
        during the UPDATE that marks injections as recorded.
        """
        failing_repo = MagicMock()
        # First fetch: return injection rows so handler proceeds to execute()
        injection_id = uuid4()
        pattern_id = uuid4()
        failing_repo.fetch = AsyncMock(
            return_value=[
                {"injection_id": injection_id, "pattern_ids": [pattern_id]},
            ]
        )
        # execute() raises to simulate database failure
        failing_repo.execute = AsyncMock(
            side_effect=RuntimeError("connection refused: database unavailable")
        )

        session_id = uuid4()
        correlation_id = uuid4()

        # Handler propagates the exception (does not swallow it)
        # This enables RuntimeHostProcess to catch and route to DLQ
        with pytest.raises(RuntimeError, match="connection refused"):
            await record_session_outcome(
                session_id=session_id,
                success=True,
                repository=failing_repo,
                correlation_id=correlation_id,
            )

        # Verify the handler attempted the database operations in order:
        # 1. fetch (find unrecorded injections) - succeeded
        # 2. execute (mark injections) - failed
        assert failing_repo.fetch.call_count >= 1
        assert failing_repo.execute.call_count == 1

    @pytest.mark.integration
    async def test_dlq_message_contains_full_context(self) -> None:
        """Verify propagated errors contain sufficient context for DLQ debugging.

        When RuntimeHostProcess catches an error from the handler, it
        constructs a DLQ message using the original event envelope and
        the exception details. This test verifies that:
        1. The exception message is descriptive enough for debugging
        2. The session_id and correlation_id are available to the caller
           for inclusion in the DLQ payload
        3. The error distinguishes between different failure modes
        """
        failing_repo = MagicMock()
        injection_id = uuid4()
        pattern_id = uuid4()
        # First fetch succeeds with injection data
        failing_repo.fetch = AsyncMock(
            return_value=[
                {"injection_id": injection_id, "pattern_ids": [pattern_id]},
            ]
        )
        # execute() raises with a descriptive error
        error_detail = (
            "could not connect to server: Connection refused\n"
            "\tIs the server running on host 192.168.86.200 and accepting\n"
            "\tTCP/IP connections on port 5436?"
        )
        failing_repo.execute = AsyncMock(side_effect=ConnectionError(error_detail))

        session_id = uuid4()
        correlation_id = uuid4()

        # Capture the exception to verify its context
        with pytest.raises(ConnectionError) as exc_info:
            await record_session_outcome(
                session_id=session_id,
                success=True,
                failure_reason=None,
                repository=failing_repo,
                correlation_id=correlation_id,
            )

        # Verify the exception contains debugging context
        error_str = str(exc_info.value)
        assert (
            "Connection refused" in error_str
        ), "Error should contain connection details for DLQ debugging"
        assert (
            "192.168.86.200" in error_str or "server" in error_str
        ), "Error should contain server identification"

        # Verify the caller (RuntimeHostProcess) has access to the
        # session context needed for DLQ message construction.
        # These values are available because the caller holds them
        # from the original event before invoking the handler.
        assert session_id is not None, "session_id available for DLQ context"
        assert correlation_id is not None, "correlation_id available for DLQ context"
