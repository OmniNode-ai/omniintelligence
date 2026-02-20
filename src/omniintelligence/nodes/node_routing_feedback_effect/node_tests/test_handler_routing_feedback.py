# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for routing feedback handler.

Tests the handler that processes routing.feedback events from omniclaude
and upserts idempotent records to routing_feedback_scores.

Test organization:
1. Happy Path - Successful first-time processing
2. Idempotency - Re-processing same event is safe (no duplicate rows)
3. Kafka Graceful Degradation - DB succeeds even without Kafka
4. Kafka Publish Failure - DB upsert succeeds when Kafka publish fails
5. Database Error - Structured ERROR result on DB failure
6. Model Validation - Event model validation and frozen invariants
7. Protocol Compliance - Mock conformance verification
8. Topic Names - Correct Kafka topic constants

Reference:
    - OMN-2366: Add routing.feedback consumer in omniintelligence
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from omniintelligence.constants import TOPIC_ROUTING_FEEDBACK_PROCESSED
from omniintelligence.nodes.node_routing_feedback_effect.handlers.handler_routing_feedback import (
    process_routing_feedback,
)
from omniintelligence.nodes.node_routing_feedback_effect.models import (
    EnumRoutingFeedbackStatus,
    ModelRoutingFeedbackEvent,
    ModelRoutingFeedbackResult,
)
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository

from .conftest import MockKafkaPublisher, MockRoutingFeedbackRepository

# =============================================================================
# Test Class: Happy Path
# =============================================================================


@pytest.mark.unit
class TestHappyPath:
    """Tests for successful first-time processing."""

    @pytest.mark.asyncio
    async def test_success_outcome_is_upserted(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
        sample_session_id: str,
        sample_correlation_id: UUID,
        sample_stage: str,
    ) -> None:
        """Success outcome event is upserted to routing_feedback_scores."""
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
        )

        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result.was_upserted is True
        assert result.session_id == sample_session_id
        assert result.correlation_id == sample_correlation_id
        assert result.stage == sample_stage
        assert result.outcome == "success"
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_failed_outcome_is_upserted(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_failed: ModelRoutingFeedbackEvent,
    ) -> None:
        """Failed outcome event is upserted to routing_feedback_scores."""
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_failed,
            repository=mock_repository,
        )

        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result.was_upserted is True
        assert result.outcome == "failed"

    @pytest.mark.asyncio
    async def test_row_is_persisted_in_repository(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
        sample_session_id: str,
        sample_correlation_id: UUID,
        sample_stage: str,
    ) -> None:
        """Exactly one row is written to routing_feedback_scores."""
        await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
        )

        assert mock_repository.row_count() == 1
        row = mock_repository.get_row(
            sample_session_id, sample_correlation_id, sample_stage
        )
        assert row is not None
        assert row["outcome"] == "success"

    @pytest.mark.asyncio
    async def test_processed_at_is_recent(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
    ) -> None:
        """processed_at in result is a recent UTC timestamp."""
        before = datetime.now(UTC)
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
        )
        after = datetime.now(UTC)

        assert before <= result.processed_at <= after

    @pytest.mark.asyncio
    async def test_success_with_kafka_publisher(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
    ) -> None:
        """When Kafka publisher is provided, confirmation event is published."""
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert len(mock_publisher.published) == 1
        topic, key, value = mock_publisher.published[0]
        assert topic == TOPIC_ROUTING_FEEDBACK_PROCESSED
        assert key == sample_routing_feedback_event_success.session_id
        assert value["outcome"] == "success"


# =============================================================================
# Test Class: Idempotency
# =============================================================================


@pytest.mark.unit
class TestIdempotency:
    """Tests verifying idempotent upsert semantics (OMN-2366 acceptance test)."""

    @pytest.mark.asyncio
    async def test_processing_same_event_twice_creates_one_row(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
        sample_session_id: str,
        sample_correlation_id: UUID,
        sample_stage: str,
    ) -> None:
        """Processing the same feedback event twice must not create duplicate rows.

        This is the acceptance test from the OMN-2366 ticket.
        Simulates at-least-once Kafka delivery.
        """
        # First delivery
        result1 = await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
        )
        # Second delivery (simulating at-least-once re-delivery)
        result2 = await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
        )

        # Both results should succeed
        assert result1.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result1.was_upserted is True
        assert result2.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result2.was_upserted is True

        # Exactly ONE row in the table
        assert mock_repository.row_count() == 1, (
            f"Expected 1 row, got {mock_repository.row_count()} — handler is not idempotent"
        )

    @pytest.mark.asyncio
    async def test_idempotency_key_is_composite(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_correlation_id: UUID,
    ) -> None:
        """Different (session_id, correlation_id, stage) combinations are distinct rows."""
        event_a = ModelRoutingFeedbackEvent(
            session_id="session-a",
            correlation_id=sample_correlation_id,
            stage="session_end",
            outcome="success",
            emitted_at=datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC),
        )
        event_b = ModelRoutingFeedbackEvent(
            session_id="session-b",
            correlation_id=sample_correlation_id,
            stage="session_end",
            outcome="failed",
            emitted_at=datetime(2026, 2, 20, 12, 0, 1, tzinfo=UTC),
        )

        await process_routing_feedback(event=event_a, repository=mock_repository)
        await process_routing_feedback(event=event_b, repository=mock_repository)

        # Two distinct sessions should produce two rows
        assert mock_repository.row_count() == 2

    @pytest.mark.asyncio
    async def test_repeated_delivery_does_not_change_outcome(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
        sample_session_id: str,
        sample_correlation_id: UUID,
        sample_stage: str,
    ) -> None:
        """Idempotent re-delivery does not overwrite the outcome field."""
        await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
        )
        await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
        )

        row = mock_repository.get_row(
            sample_session_id, sample_correlation_id, sample_stage
        )
        assert row is not None
        assert row["outcome"] == "success"

    @pytest.mark.asyncio
    async def test_five_deliveries_produces_one_row(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
    ) -> None:
        """At-least-once delivery of 5x the same event = exactly 1 row."""
        for _ in range(5):
            result = await process_routing_feedback(
                event=sample_routing_feedback_event_success,
                repository=mock_repository,
            )
            assert result.status == EnumRoutingFeedbackStatus.SUCCESS

        assert mock_repository.row_count() == 1, (
            f"Expected 1 row after 5 deliveries, got {mock_repository.row_count()}"
        )


# =============================================================================
# Test Class: Kafka Graceful Degradation
# =============================================================================


@pytest.mark.unit
class TestKafkaGracefulDegradation:
    """Tests verifying DB succeeds without Kafka publisher (Repository Invariant)."""

    @pytest.mark.asyncio
    async def test_no_kafka_publisher_still_succeeds(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
    ) -> None:
        """Handler succeeds when kafka_publisher is None (graceful degradation)."""
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
            kafka_publisher=None,
        )

        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result.was_upserted is True
        assert mock_repository.row_count() == 1

    @pytest.mark.asyncio
    async def test_default_kafka_publisher_is_none(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
    ) -> None:
        """kafka_publisher defaults to None when not provided."""
        # Call with only required arguments - should not raise
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
        )

        assert result.status == EnumRoutingFeedbackStatus.SUCCESS


# =============================================================================
# Test Class: Kafka Publish Failure
# =============================================================================


@pytest.mark.unit
class TestKafkaPublishFailure:
    """Tests verifying DB upsert succeeds when Kafka publish fails."""

    @pytest.mark.asyncio
    async def test_kafka_failure_does_not_fail_result(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
    ) -> None:
        """Kafka publish failure is non-fatal; DB upsert result is SUCCESS."""
        mock_publisher.simulate_publish_error = ConnectionError("Kafka unavailable")

        result = await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        # DB write succeeded
        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result.was_upserted is True
        assert mock_repository.row_count() == 1
        # No error message in result (Kafka failure is logged but not surfaced)
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_kafka_failure_still_persists_db_row(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
        sample_session_id: str,
        sample_correlation_id: UUID,
        sample_stage: str,
    ) -> None:
        """Even when Kafka fails, the DB row is persisted."""
        mock_publisher.simulate_publish_error = RuntimeError("Kafka broker down")

        await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        row = mock_repository.get_row(
            sample_session_id, sample_correlation_id, sample_stage
        )
        assert row is not None
        assert row["outcome"] == "success"


# =============================================================================
# Test Class: Database Error
# =============================================================================


@pytest.mark.unit
class TestDatabaseError:
    """Tests for database error scenarios."""

    @pytest.mark.asyncio
    async def test_database_error_returns_structured_error(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
    ) -> None:
        """Database error returns structured ERROR result, never raises."""
        mock_repository.simulate_db_error = ConnectionError("DB connection refused")

        result = await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
        )

        assert result.status == EnumRoutingFeedbackStatus.ERROR
        assert result.was_upserted is False
        assert result.error_message is not None
        assert len(result.error_message) > 0

    @pytest.mark.asyncio
    async def test_database_error_preserves_event_metadata(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
        sample_session_id: str,
        sample_correlation_id: UUID,
        sample_stage: str,
    ) -> None:
        """Even on DB error, event metadata is preserved in the result."""
        mock_repository.simulate_db_error = Exception("Unexpected failure")

        result = await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
        )

        assert result.session_id == sample_session_id
        assert result.correlation_id == sample_correlation_id
        assert result.stage == sample_stage
        assert result.outcome == "success"

    @pytest.mark.asyncio
    async def test_handler_never_raises(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
    ) -> None:
        """Handler catches all exceptions and returns structured result."""
        mock_repository.simulate_db_error = RuntimeError("Catastrophic failure")

        # Must NOT raise - handler contract
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
        )

        assert result.status == EnumRoutingFeedbackStatus.ERROR


# =============================================================================
# Test Class: Kafka Published Event Contents
# =============================================================================


@pytest.mark.unit
class TestKafkaPublishedEvent:
    """Tests verifying the contents of the published confirmation event."""

    @pytest.mark.asyncio
    async def test_published_event_has_correct_topic(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
    ) -> None:
        """Confirmation event is published to the correct topic."""
        await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        assert len(mock_publisher.published) == 1
        topic, _, _ = mock_publisher.published[0]
        assert topic == TOPIC_ROUTING_FEEDBACK_PROCESSED

    @pytest.mark.asyncio
    async def test_published_event_key_is_session_id(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
        sample_session_id: str,
    ) -> None:
        """Confirmation event uses session_id as the Kafka message key."""
        await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        _, key, _ = mock_publisher.published[0]
        assert key == sample_session_id

    @pytest.mark.asyncio
    async def test_published_event_contains_outcome(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
    ) -> None:
        """Confirmation event payload includes the outcome."""
        await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        _, _, value = mock_publisher.published[0]
        assert value["outcome"] == "success"
        assert value["session_id"] == sample_routing_feedback_event_success.session_id

    @pytest.mark.asyncio
    async def test_no_event_published_without_kafka(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
    ) -> None:
        """No Kafka publish occurs when kafka_publisher is None."""
        # No publisher - should succeed silently
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_success,
            repository=mock_repository,
            kafka_publisher=None,
        )
        assert result.status == EnumRoutingFeedbackStatus.SUCCESS


# =============================================================================
# Test Class: Model Validation
# =============================================================================


@pytest.mark.unit
class TestModelValidation:
    """Tests for event model validation."""

    def test_routing_feedback_event_is_frozen(
        self,
        sample_routing_feedback_event_success: ModelRoutingFeedbackEvent,
    ) -> None:
        """ModelRoutingFeedbackEvent is immutable (frozen)."""
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            sample_routing_feedback_event_success.outcome = "failed"

    def test_result_is_frozen(self) -> None:
        """ModelRoutingFeedbackResult is immutable (frozen)."""
        import pydantic

        result = ModelRoutingFeedbackResult(
            status=EnumRoutingFeedbackStatus.SUCCESS,
            session_id="test",
            correlation_id=uuid4(),
            stage="session_end",
            outcome="success",
            processed_at=datetime.now(UTC),
        )

        with pytest.raises(pydantic.ValidationError):
            result.outcome = "failed"

    def test_event_rejects_invalid_outcome(
        self,
        sample_correlation_id: UUID,
    ) -> None:
        """ModelRoutingFeedbackEvent rejects outcomes other than success/failed."""
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            ModelRoutingFeedbackEvent(
                session_id="test-session",
                correlation_id=sample_correlation_id,
                outcome="unknown",  # type: ignore[arg-type]
                emitted_at=datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC),
            )

    def test_event_rejects_empty_session_id(
        self,
        sample_correlation_id: UUID,
    ) -> None:
        """ModelRoutingFeedbackEvent rejects empty session_id."""
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            ModelRoutingFeedbackEvent(
                session_id="",
                correlation_id=sample_correlation_id,
                outcome="success",
                emitted_at=datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC),
            )

    def test_event_default_stage_is_session_end(
        self,
        sample_correlation_id: UUID,
    ) -> None:
        """ModelRoutingFeedbackEvent defaults stage to session_end."""
        event = ModelRoutingFeedbackEvent(
            session_id="test-session",
            correlation_id=sample_correlation_id,
            outcome="success",
            emitted_at=datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC),
        )
        assert event.stage == "session_end"

    def test_extra_fields_are_silently_dropped(
        self,
        sample_correlation_id: UUID,
    ) -> None:
        """Unknown fields from omniclaude are silently ignored (extra='ignore').

        omniclaude may add new fields to the routing.feedback event payload
        before omniintelligence is updated. extra='ignore' prevents validation
        errors and ensures forward-compatible deserialization.
        """
        event = ModelRoutingFeedbackEvent.model_validate(
            {
                "session_id": "test-session",
                "correlation_id": str(sample_correlation_id),
                "outcome": "success",
                "emitted_at": "2026-02-20T12:00:00+00:00",
                "unknown_future_field": "some_value",
                "another_unknown_field": 42,
            }
        )

        # Valid fields are present
        assert event.session_id == "test-session"
        assert event.outcome == "success"

        # Unknown fields are not accessible on the model
        assert not hasattr(event, "unknown_future_field")
        assert not hasattr(event, "another_unknown_field")


# =============================================================================
# Test Class: Topic Names
# =============================================================================


@pytest.mark.unit
class TestTopicNames:
    """Tests verifying correct Kafka topic constants."""

    def test_processed_topic_name(self) -> None:
        """TOPIC_ROUTING_FEEDBACK_PROCESSED has the correct canonical name."""
        assert (
            TOPIC_ROUTING_FEEDBACK_PROCESSED
            == "onex.evt.omniintelligence.routing-feedback-processed.v1"
        )


# =============================================================================
# Test Class: Protocol Compliance
# =============================================================================


@pytest.mark.unit
class TestProtocolCompliance:
    """Tests verifying mock implementations satisfy protocols."""

    def test_mock_repository_is_protocol_compliant(
        self,
        mock_repository: MockRoutingFeedbackRepository,
    ) -> None:
        """MockRoutingFeedbackRepository satisfies ProtocolPatternRepository protocol."""
        assert isinstance(mock_repository, ProtocolPatternRepository)

    def test_mock_publisher_is_protocol_compliant(
        self,
        mock_publisher: MockKafkaPublisher,
    ) -> None:
        """MockKafkaPublisher satisfies ProtocolKafkaPublisher protocol."""
        assert isinstance(mock_publisher, ProtocolKafkaPublisher)
