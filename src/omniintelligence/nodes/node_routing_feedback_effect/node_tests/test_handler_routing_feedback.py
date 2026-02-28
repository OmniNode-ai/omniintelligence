# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for routing feedback handler (OMN-2622).

Tests the handler that processes routing-feedback.v1 events from omniclaude
and either upserts idempotent records to routing_feedback_scores (produced)
or logs and skips (skipped).

Test organization:
1. Happy Path - Successful produced event processing
2. Skipped Events - feedback_status=="skipped" events skip DB write
3. Idempotency - Re-processing same event is safe (no duplicate rows)
4. Kafka Graceful Degradation - DB succeeds even without Kafka
5. Kafka Publish Failure - DB upsert succeeds when Kafka publish fails
6. Database Error - Structured ERROR result on DB failure
7. Kafka Published Event Contents - Payload shape including event_name and datetimes
8. DLQ Routing - Dead-letter queue publish on Kafka failure, failure swallowing
9. Model Validation - Event model validation and frozen invariants
10. Protocol Compliance - Mock conformance verification
11. Topic Names - Correct Kafka topic constants

Reference:
    - OMN-2366: Add routing.feedback consumer in omniintelligence
    - OMN-2935: Fix routing feedback loop — subscribe to routing-outcome-raw.v1
    - OMN-2622: Fold routing-feedback-skipped.v1 into routing-feedback.v1
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from omniintelligence.constants import TOPIC_ROUTING_FEEDBACK_PROCESSED
from omniintelligence.nodes.node_routing_feedback_effect.handlers.handler_routing_feedback import (
    DLQ_TOPIC,
    process_routing_feedback,
)
from omniintelligence.nodes.node_routing_feedback_effect.models import (
    EnumRoutingFeedbackStatus,
    ModelRoutingFeedbackPayload,
    ModelRoutingFeedbackResult,
)
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository

from .conftest import MockKafkaPublisher, MockRoutingFeedbackRepository

# =============================================================================
# Test Class: Happy Path
# =============================================================================


@pytest.mark.unit
class TestHappyPath:
    """Tests for successful produced event processing."""

    @pytest.mark.asyncio
    async def test_produced_event_is_upserted(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
        sample_session_id: str,
    ) -> None:
        """feedback_status='produced' event is upserted to routing_feedback_scores."""
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
        )

        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result.was_upserted is True
        assert result.session_id == sample_session_id
        assert result.feedback_status == "produced"
        assert result.skip_reason is None
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_row_is_persisted_in_repository(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
        sample_session_id: str,
    ) -> None:
        """Exactly one row is written to routing_feedback_scores."""
        await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
        )

        assert mock_repository.row_count() == 1
        row = mock_repository.get_row(sample_session_id)
        assert row is not None
        assert row["outcome"] == "success"

    @pytest.mark.asyncio
    async def test_processed_at_is_recent(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """processed_at in result is a recent UTC timestamp."""
        before = datetime.now(UTC)
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
        )
        after = datetime.now(UTC)

        assert before <= result.processed_at <= after

    @pytest.mark.asyncio
    async def test_success_with_kafka_publisher(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """When Kafka publisher is provided, confirmation event is published."""
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert len(mock_publisher.published) == 1
        topic, key, value = mock_publisher.published[0]
        assert topic == TOPIC_ROUTING_FEEDBACK_PROCESSED
        assert key == sample_routing_feedback_event_produced.session_id
        assert value["feedback_status"] == "produced"


# =============================================================================
# Test Class: Skipped Events
# =============================================================================


@pytest.mark.unit
class TestSkippedEvents:
    """Tests for feedback_status=='skipped' event handling."""

    @pytest.mark.asyncio
    async def test_skipped_event_does_not_upsert(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_skipped: ModelRoutingFeedbackPayload,
    ) -> None:
        """feedback_status='skipped' event skips DB write."""
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_skipped,
            repository=mock_repository,
        )

        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result.was_upserted is False
        assert mock_repository.row_count() == 0

    @pytest.mark.asyncio
    async def test_skipped_event_preserves_skip_reason(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_skipped: ModelRoutingFeedbackPayload,
    ) -> None:
        """Result for a skipped event includes the skip_reason from input."""
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_skipped,
            repository=mock_repository,
        )

        assert result.feedback_status == "skipped"
        assert result.skip_reason == "NO_INJECTION"

    @pytest.mark.asyncio
    async def test_skipped_event_does_not_publish_to_kafka(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_skipped: ModelRoutingFeedbackPayload,
    ) -> None:
        """Skipped events do not publish a confirmation event to Kafka."""
        await process_routing_feedback(
            event=sample_routing_feedback_event_skipped,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        assert len(mock_publisher.published) == 0

    @pytest.mark.asyncio
    async def test_skipped_event_result_is_success(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_skipped: ModelRoutingFeedbackPayload,
    ) -> None:
        """Skipped events return SUCCESS status (not an error)."""
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_skipped,
            repository=mock_repository,
        )

        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_produced_and_skipped_events_same_session(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_session_id: str,
    ) -> None:
        """A produced and skipped event for the same session ID: produced upserts, skipped does not."""
        produced_event = ModelRoutingFeedbackPayload(
            session_id=sample_session_id,
            outcome="success",
            feedback_status="produced",
            skip_reason=None,
            emitted_at=datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC),
        )
        skipped_event = ModelRoutingFeedbackPayload(
            session_id="other-session-skipped",
            outcome="unknown",
            feedback_status="skipped",
            skip_reason="UNCLEAR_OUTCOME",
            emitted_at=datetime(2026, 2, 28, 12, 0, 1, tzinfo=UTC),
        )

        await process_routing_feedback(event=produced_event, repository=mock_repository)
        await process_routing_feedback(event=skipped_event, repository=mock_repository)

        # Only the produced event should be in the DB
        assert mock_repository.row_count() == 1
        assert mock_repository.get_row(sample_session_id) is not None
        assert mock_repository.get_row("other-session-skipped") is None


# =============================================================================
# Test Class: Idempotency
# =============================================================================


@pytest.mark.unit
class TestIdempotency:
    """Tests verifying idempotent upsert semantics (OMN-2366, OMN-2622 acceptance test)."""

    @pytest.mark.asyncio
    async def test_processing_same_session_twice_creates_one_row(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
        sample_session_id: str,
    ) -> None:
        """Processing the same feedback event twice must not create duplicate rows.

        Simulates at-least-once Kafka delivery.
        """
        # First delivery
        result1 = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
        )
        # Second delivery (simulating at-least-once re-delivery)
        result2 = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
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
    async def test_idempotency_key_is_session_id(
        self,
        mock_repository: MockRoutingFeedbackRepository,
    ) -> None:
        """Different session_ids produce distinct rows (idempotency key = session_id)."""
        event_a = ModelRoutingFeedbackPayload(
            session_id="session-a",
            outcome="success",
            feedback_status="produced",
            skip_reason=None,
            emitted_at=datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC),
        )
        event_b = ModelRoutingFeedbackPayload(
            session_id="session-b",
            outcome="failed",
            feedback_status="produced",
            skip_reason=None,
            emitted_at=datetime(2026, 2, 28, 12, 0, 1, tzinfo=UTC),
        )

        await process_routing_feedback(event=event_a, repository=mock_repository)
        await process_routing_feedback(event=event_b, repository=mock_repository)

        # Two distinct sessions should produce two rows
        assert mock_repository.row_count() == 2

    @pytest.mark.asyncio
    async def test_five_deliveries_produces_one_row(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """At-least-once delivery of 5x the same session = exactly 1 row."""
        for _ in range(5):
            result = await process_routing_feedback(
                event=sample_routing_feedback_event_produced,
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
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """Handler succeeds when kafka_publisher is None (graceful degradation)."""
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
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
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """kafka_publisher defaults to None when not provided."""
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
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
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """Kafka publish failure is non-fatal; DB upsert result is SUCCESS."""
        mock_publisher.simulate_publish_error = ConnectionError("Kafka unavailable")

        result = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        # DB write succeeded
        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result.was_upserted is True
        assert mock_repository.row_count() == 1
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_kafka_failure_still_persists_db_row(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
        sample_session_id: str,
    ) -> None:
        """Even when Kafka fails, the DB row is persisted."""
        mock_publisher.simulate_publish_error = RuntimeError("Kafka broker down")

        await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        row = mock_repository.get_row(sample_session_id)
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
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """Database error returns structured ERROR result, never raises."""
        mock_repository.simulate_db_error = ConnectionError("DB connection refused")

        result = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
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
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
        sample_session_id: str,
    ) -> None:
        """Even on DB error, event metadata is preserved in the result."""
        mock_repository.simulate_db_error = Exception("Unexpected failure")

        result = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
        )

        assert result.session_id == sample_session_id
        assert result.feedback_status == "produced"

    @pytest.mark.asyncio
    async def test_handler_never_raises(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """Handler catches all exceptions and returns structured result."""
        mock_repository.simulate_db_error = RuntimeError("Catastrophic failure")

        # Must NOT raise - handler contract
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
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
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """Confirmation event is published to the correct topic."""
        await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
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
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
        sample_session_id: str,
    ) -> None:
        """Confirmation event uses session_id as the Kafka message key."""
        await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        _, key, _ = mock_publisher.published[0]
        assert key == sample_session_id

    @pytest.mark.asyncio
    async def test_published_event_contains_feedback_fields(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """Confirmation event payload includes the feedback_status field."""
        await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        _, _, value = mock_publisher.published[0]
        assert value["feedback_status"] == "produced"
        assert value["session_id"] == sample_routing_feedback_event_produced.session_id

    @pytest.mark.asyncio
    async def test_published_event_has_event_name(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """Confirmation event payload includes the fixed event_name discriminator."""
        await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        _, _, value = mock_publisher.published[0]
        assert value["event_name"] == "routing.feedback.processed"

    @pytest.mark.asyncio
    async def test_published_event_has_datetime_fields(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """Confirmation event payload includes emitted_at and processed_at fields."""
        before = datetime.now(UTC)
        await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )
        after = datetime.now(UTC)

        _, _, value = mock_publisher.published[0]
        assert "emitted_at" in value, "emitted_at must be present in published payload"
        assert "processed_at" in value, (
            "processed_at must be present in published payload"
        )

        assert value["emitted_at"] == "2026-02-28T12:00:00Z"

        processed_at_dt = datetime.fromisoformat(value["processed_at"])
        assert before <= processed_at_dt <= after

    @pytest.mark.asyncio
    async def test_no_event_published_without_kafka(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """No Kafka publish occurs when kafka_publisher is None."""
        result = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
            kafka_publisher=None,
        )
        assert result.status == EnumRoutingFeedbackStatus.SUCCESS


# =============================================================================
# Test Class: DLQ Routing
# =============================================================================


@pytest.mark.unit
class TestDlqRouting:
    """Tests verifying dead-letter queue routing on Kafka publish failures."""

    @pytest.mark.asyncio
    async def test_dlq_publish_attempted_on_kafka_failure(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """DLQ publish is attempted when the primary Kafka publish fails."""
        mock_publisher.publish_side_effects = [
            ConnectionError("Kafka broker unreachable"),
            None,  # DLQ publish succeeds
        ]

        result = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result.was_upserted is True

        assert len(mock_publisher.published) == 1
        dlq_topic, dlq_key, dlq_value = mock_publisher.published[0]

        assert dlq_topic == DLQ_TOPIC
        assert dlq_key == sample_routing_feedback_event_produced.session_id
        assert dlq_value["original_topic"] == TOPIC_ROUTING_FEEDBACK_PROCESSED
        assert "error_message" in dlq_value
        assert dlq_value["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_dlq_failure_does_not_propagate(
        self,
        mock_repository: MockRoutingFeedbackRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """Handler returns SUCCESS even when both primary and DLQ publishes fail."""
        mock_publisher.simulate_publish_error = RuntimeError("Kafka cluster down")

        result = await process_routing_feedback(
            event=sample_routing_feedback_event_produced,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result.was_upserted is True
        assert result.error_message is None
        assert len(mock_publisher.published) == 0


# =============================================================================
# Test Class: Model Validation
# =============================================================================


@pytest.mark.unit
class TestModelValidation:
    """Tests for event model validation."""

    def test_routing_feedback_event_is_frozen(
        self,
        sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
    ) -> None:
        """ModelRoutingFeedbackPayload is immutable (frozen)."""
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            sample_routing_feedback_event_produced.feedback_status = "skipped"  # type: ignore[misc]

    def test_result_is_frozen(self) -> None:
        """ModelRoutingFeedbackResult is immutable (frozen)."""
        import pydantic

        result = ModelRoutingFeedbackResult(
            status=EnumRoutingFeedbackStatus.SUCCESS,
            session_id="test",
            outcome="success",
            feedback_status="produced",
            skip_reason=None,
            was_upserted=True,
            processed_at=datetime.now(UTC),
        )

        with pytest.raises(pydantic.ValidationError):
            result.feedback_status = "skipped"  # type: ignore[misc]

    def test_event_rejects_empty_session_id(self) -> None:
        """ModelRoutingFeedbackPayload rejects empty session_id."""
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            ModelRoutingFeedbackPayload(
                session_id="",
                outcome="success",
                feedback_status="produced",
                skip_reason=None,
                emitted_at=datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC),
            )

    def test_event_rejects_invalid_feedback_status(self) -> None:
        """ModelRoutingFeedbackPayload rejects invalid feedback_status values."""
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            ModelRoutingFeedbackPayload(
                session_id="test-session",
                outcome="success",
                feedback_status="invalid_status",  # type: ignore[arg-type]
                skip_reason=None,
                emitted_at=datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC),
            )

    def test_extra_fields_are_silently_dropped(self) -> None:
        """Unknown fields from omniclaude are silently ignored (extra='ignore')."""
        event = ModelRoutingFeedbackPayload.model_validate(
            {
                "session_id": "test-session",
                "outcome": "success",
                "feedback_status": "produced",
                "skip_reason": None,
                "emitted_at": "2026-02-28T12:00:00+00:00",
                "unknown_future_field": "some_value",
                "another_unknown_field": 42,
            }
        )

        assert event.session_id == "test-session"
        assert event.feedback_status == "produced"
        assert not hasattr(event, "unknown_future_field")
        assert not hasattr(event, "another_unknown_field")

    def test_skipped_event_with_skip_reason(self) -> None:
        """ModelRoutingFeedbackPayload accepts skip_reason when feedback_status is skipped."""
        event = ModelRoutingFeedbackPayload(
            session_id="test-session",
            outcome="unknown",
            feedback_status="skipped",
            skip_reason="NO_INJECTION",
            emitted_at=datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC),
        )

        assert event.feedback_status == "skipped"
        assert event.skip_reason == "NO_INJECTION"


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
