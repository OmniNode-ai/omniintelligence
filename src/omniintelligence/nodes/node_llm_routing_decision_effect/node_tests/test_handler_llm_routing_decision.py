# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for LLM routing decision handler.

Tests the handler that processes onex.evt.omniclaude.llm-routing-decision.v1
events from omniclaude's Bifrost LLM gateway and upserts idempotent records
to llm_routing_decisions.

Test organization:
1. Happy Path - Successful first-time processing
2. Idempotency - Re-processing same event is safe (no duplicate rows)
3. Kafka Graceful Degradation - DB succeeds even without Kafka
4. Kafka Publish Failure - DB upsert succeeds when Kafka publish fails
5. Database Error - Structured ERROR result on DB failure
6. Model Validation - Event model validation and frozen invariants
7. Topic Names - Correct Kafka topic constants
8. Fallback Events - Events where LLM fell back to fuzzy matching

Reference:
    - OMN-2939: Bifrost feedback loop — add LLM routing decision consumer in omniintelligence
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from omniintelligence.constants import TOPIC_LLM_ROUTING_DECISION_PROCESSED
from omniintelligence.nodes.node_llm_routing_decision_effect.handlers.handler_llm_routing_decision import (
    DLQ_TOPIC,
    process_llm_routing_decision,
)
from omniintelligence.nodes.node_llm_routing_decision_effect.models import (
    EnumLlmRoutingDecisionStatus,
    ModelLlmRoutingDecisionEvent,
    ModelLlmRoutingDecisionResult,
)

from .conftest import MockKafkaPublisher, MockLlmRoutingDecisionRepository

# =============================================================================
# Test Class: Happy Path
# =============================================================================


@pytest.mark.unit
class TestHappyPath:
    """Tests for successful first-time processing."""

    @pytest.mark.asyncio
    async def test_success_result_on_valid_event(
        self,
        mock_repository: MockLlmRoutingDecisionRepository,
        sample_routing_decision_event: ModelLlmRoutingDecisionEvent,
        sample_session_id: str,
        sample_correlation_id: str,
    ) -> None:
        """Valid routing decision event is processed and upserted."""
        result = await process_llm_routing_decision(
            event=sample_routing_decision_event,
            repository=mock_repository,
        )

        assert result.status == EnumLlmRoutingDecisionStatus.SUCCESS
        assert result.was_upserted is True
        assert result.session_id == sample_session_id
        assert result.correlation_id == sample_correlation_id
        assert result.selected_agent == "agent-api"
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_row_is_persisted_in_repository(
        self,
        mock_repository: MockLlmRoutingDecisionRepository,
        sample_routing_decision_event: ModelLlmRoutingDecisionEvent,
        sample_session_id: str,
        sample_correlation_id: str,
    ) -> None:
        """Row is written to the mock repository after processing."""
        await process_llm_routing_decision(
            event=sample_routing_decision_event,
            repository=mock_repository,
        )

        row = mock_repository.get_row(sample_session_id, sample_correlation_id)
        assert row is not None
        assert row["selected_agent"] == "agent-api"
        assert row["llm_confidence"] == 0.92
        assert row["agreement"] is True
        assert row["fallback_used"] is False

    @pytest.mark.asyncio
    async def test_fallback_event_is_processed(
        self,
        mock_repository: MockLlmRoutingDecisionRepository,
        sample_routing_decision_event_fallback: ModelLlmRoutingDecisionEvent,
    ) -> None:
        """Fallback routing decision event (LLM fell back to fuzzy) is processed."""
        result = await process_llm_routing_decision(
            event=sample_routing_decision_event_fallback,
            repository=mock_repository,
        )

        assert result.status == EnumLlmRoutingDecisionStatus.SUCCESS
        assert result.was_upserted is True
        assert result.selected_agent == "agent-polymorphic"


# =============================================================================
# Test Class: Idempotency
# =============================================================================


@pytest.mark.unit
class TestIdempotency:
    """Tests for idempotent re-processing of the same event."""

    @pytest.mark.asyncio
    async def test_second_delivery_does_not_create_duplicate_row(
        self,
        mock_repository: MockLlmRoutingDecisionRepository,
        sample_routing_decision_event: ModelLlmRoutingDecisionEvent,
    ) -> None:
        """Re-processing the same event does not create duplicate rows."""
        await process_llm_routing_decision(
            event=sample_routing_decision_event,
            repository=mock_repository,
        )
        await process_llm_routing_decision(
            event=sample_routing_decision_event,
            repository=mock_repository,
        )

        assert mock_repository.row_count() == 1

    @pytest.mark.asyncio
    async def test_second_delivery_returns_success(
        self,
        mock_repository: MockLlmRoutingDecisionRepository,
        sample_routing_decision_event: ModelLlmRoutingDecisionEvent,
    ) -> None:
        """Re-processing the same event returns SUCCESS status."""
        await process_llm_routing_decision(
            event=sample_routing_decision_event,
            repository=mock_repository,
        )
        result = await process_llm_routing_decision(
            event=sample_routing_decision_event,
            repository=mock_repository,
        )

        assert result.status == EnumLlmRoutingDecisionStatus.SUCCESS
        assert result.was_upserted is True


# =============================================================================
# Test Class: Kafka Graceful Degradation
# =============================================================================


@pytest.mark.unit
class TestKafkaGracefulDegradation:
    """Tests for DB-first behavior when Kafka publisher is absent."""

    @pytest.mark.asyncio
    async def test_db_upsert_succeeds_without_kafka(
        self,
        mock_repository: MockLlmRoutingDecisionRepository,
        sample_routing_decision_event: ModelLlmRoutingDecisionEvent,
        sample_session_id: str,
        sample_correlation_id: str,
    ) -> None:
        """DB upsert succeeds when kafka_publisher is None."""
        result = await process_llm_routing_decision(
            event=sample_routing_decision_event,
            repository=mock_repository,
            kafka_publisher=None,
        )

        assert result.status == EnumLlmRoutingDecisionStatus.SUCCESS
        assert result.was_upserted is True
        row = mock_repository.get_row(sample_session_id, sample_correlation_id)
        assert row is not None


# =============================================================================
# Test Class: Kafka Publish Failure
# =============================================================================


@pytest.mark.unit
class TestKafkaPublishFailure:
    """Tests for DB-first behavior when Kafka publish fails."""

    @pytest.mark.asyncio
    async def test_db_upsert_succeeds_when_kafka_fails(
        self,
        mock_repository: MockLlmRoutingDecisionRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_decision_event: ModelLlmRoutingDecisionEvent,
    ) -> None:
        """DB upsert succeeds even when Kafka publish raises."""
        mock_publisher.simulate_publish_error = RuntimeError("Kafka unavailable")

        result = await process_llm_routing_decision(
            event=sample_routing_decision_event,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        assert result.status == EnumLlmRoutingDecisionStatus.SUCCESS
        assert result.was_upserted is True

    @pytest.mark.asyncio
    async def test_dlq_attempted_on_kafka_failure(
        self,
        mock_repository: MockLlmRoutingDecisionRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_decision_event: ModelLlmRoutingDecisionEvent,
    ) -> None:
        """On Kafka failure, DLQ publish is attempted."""
        # First call (main topic) fails; second call (DLQ) succeeds.
        mock_publisher.publish_side_effects = [
            RuntimeError("Kafka unavailable"),  # main topic fails
            None,  # DLQ succeeds
        ]

        await process_llm_routing_decision(
            event=sample_routing_decision_event,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        assert len(mock_publisher.published) == 1
        dlq_topic, _, dlq_value = mock_publisher.published[0]
        assert dlq_topic == DLQ_TOPIC
        assert dlq_value["original_topic"] == TOPIC_LLM_ROUTING_DECISION_PROCESSED
        assert dlq_value["node"] == "node_llm_routing_decision_effect"


# =============================================================================
# Test Class: Database Error
# =============================================================================


@pytest.mark.unit
class TestDatabaseError:
    """Tests for structured error result on database failures."""

    @pytest.mark.asyncio
    async def test_db_error_returns_error_status(
        self,
        mock_repository: MockLlmRoutingDecisionRepository,
        sample_routing_decision_event: ModelLlmRoutingDecisionEvent,
    ) -> None:
        """DB error produces structured ERROR result, not an exception."""
        mock_repository.simulate_db_error = RuntimeError("DB connection lost")

        result = await process_llm_routing_decision(
            event=sample_routing_decision_event,
            repository=mock_repository,
        )

        assert result.status == EnumLlmRoutingDecisionStatus.ERROR
        assert result.was_upserted is False
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_db_error_does_not_raise(
        self,
        mock_repository: MockLlmRoutingDecisionRepository,
        sample_routing_decision_event: ModelLlmRoutingDecisionEvent,
    ) -> None:
        """DB error is swallowed and returned as structured result, never raised."""
        mock_repository.simulate_db_error = RuntimeError("DB connection lost")

        # Should not raise
        result = await process_llm_routing_decision(
            event=sample_routing_decision_event,
            repository=mock_repository,
        )

        assert isinstance(result, ModelLlmRoutingDecisionResult)


# =============================================================================
# Test Class: Model Validation
# =============================================================================


@pytest.mark.unit
class TestModelValidation:
    """Tests for event model validation and invariants."""

    def test_event_model_is_frozen(
        self,
        sample_routing_decision_event: ModelLlmRoutingDecisionEvent,
    ) -> None:
        """ModelLlmRoutingDecisionEvent is immutable (frozen=True)."""
        with pytest.raises(ValidationError):
            sample_routing_decision_event.session_id = "modified"  # type: ignore[misc]

    def test_event_model_defaults(self) -> None:
        """Minimal event construction uses correct defaults."""
        event = ModelLlmRoutingDecisionEvent(
            session_id="s1",
            correlation_id="c1",
            selected_agent="agent-api",
        )
        assert event.event_name == "llm.routing.decision"
        assert event.llm_confidence == 0.0
        assert event.llm_latency_ms == 0
        assert event.fallback_used is False
        assert event.agreement is False
        assert event.fuzzy_top_candidate is None
        assert event.llm_selected_candidate is None
        assert event.emitted_at is None

    def test_event_ignores_unknown_fields(self) -> None:
        """extra='ignore' allows forward-compatible omniclaude events."""
        event = ModelLlmRoutingDecisionEvent(
            session_id="s1",
            correlation_id="c1",
            selected_agent="agent-api",
            unknown_future_field="ignored",  # type: ignore[call-arg]
        )
        assert event.session_id == "s1"


# =============================================================================
# Test Class: Topic Names
# =============================================================================


@pytest.mark.unit
class TestTopicNames:
    """Tests for correct Kafka topic constants."""

    def test_processed_topic_value(self) -> None:
        """TOPIC_LLM_ROUTING_DECISION_PROCESSED has the correct topic name."""
        assert (
            TOPIC_LLM_ROUTING_DECISION_PROCESSED
            == "onex.evt.omniintelligence.llm-routing-decision-processed.v1"
        )

    def test_dlq_topic_derived_from_processed_topic(self) -> None:
        """DLQ_TOPIC is derived from the processed topic."""
        assert f"{TOPIC_LLM_ROUTING_DECISION_PROCESSED}.dlq" == DLQ_TOPIC

    @pytest.mark.asyncio
    async def test_confirmation_published_to_correct_topic(
        self,
        mock_repository: MockLlmRoutingDecisionRepository,
        mock_publisher: MockKafkaPublisher,
        sample_routing_decision_event: ModelLlmRoutingDecisionEvent,
    ) -> None:
        """Confirmation event is published to the correct topic."""
        await process_llm_routing_decision(
            event=sample_routing_decision_event,
            repository=mock_repository,
            kafka_publisher=mock_publisher,
        )

        assert len(mock_publisher.published) == 1
        topic, key, _ = mock_publisher.published[0]
        assert topic == TOPIC_LLM_ROUTING_DECISION_PROCESSED
        assert key == sample_routing_decision_event.session_id
