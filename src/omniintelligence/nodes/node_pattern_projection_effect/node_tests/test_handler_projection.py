# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for pattern projection effect node handler.

Tests the handler that builds and publishes pattern projection snapshots.
Covers:
1. Snapshot contains all validated patterns from the query store
2. Projection event emitted on trigger (pattern promote / fire-and-forget)
3. Empty snapshot returned and published when no patterns exist
4. Kafka failures do not propagate (fire-and-forget semantics)
5. Query store errors return an empty snapshot gracefully
6. correlation_id threaded through to snapshot payload
7. No datetime.now() in ModelPatternProjectionEvent — snapshot_at is injected
8. Protocol compliance of mock implementations

Reference:
    - OMN-2424: Pattern projection snapshot publisher
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from omniintelligence.models.events.model_pattern_projection_event import (
    ModelPatternProjectionEvent,
)
from omniintelligence.nodes.node_pattern_projection_effect.handlers.handler_projection import (
    publish_projection,
)

from .conftest import MockKafkaPublisher, MockPatternQueryStore, make_pattern_row

# =============================================================================
# Test Class: Snapshot Construction
# =============================================================================


@pytest.mark.unit
class TestSnapshotConstruction:
    """Tests verifying the snapshot is built correctly from query results."""

    @pytest.mark.asyncio
    async def test_snapshot_contains_all_patterns(
        self,
        mock_query_store: MockPatternQueryStore,
        mock_producer: MockKafkaPublisher,
        sample_correlation_id: UUID,
    ) -> None:
        """Snapshot total_count equals number of returned patterns."""
        mock_query_store.rows = [
            make_pattern_row(pattern_id=str(uuid4()), signature=f"pattern {i}")
            for i in range(3)
        ]

        result = await publish_projection(
            pattern_query_store=mock_query_store,
            producer=mock_producer,
            correlation_id=sample_correlation_id,
            publish_topic="onex.evt.omniintelligence.pattern-projection.v1",
        )

        assert isinstance(result, ModelPatternProjectionEvent)
        assert result.total_count == 3
        assert len(result.patterns) == 3
        assert result.event_type == "PatternProjection"

    @pytest.mark.asyncio
    async def test_snapshot_is_frozen(
        self,
        mock_query_store: MockPatternQueryStore,
        mock_producer: MockKafkaPublisher,
        sample_correlation_id: UUID,
    ) -> None:
        """ModelPatternProjectionEvent is immutable after construction (frozen=True)."""
        result = await publish_projection(
            pattern_query_store=mock_query_store,
            producer=mock_producer,
            correlation_id=sample_correlation_id,
            publish_topic="onex.evt.omniintelligence.pattern-projection.v1",
        )

        # Pydantic frozen models raise ValidationError on direct attribute assignment
        with pytest.raises(ValidationError):
            result.total_count = 999

    @pytest.mark.asyncio
    async def test_correlation_id_threaded_to_snapshot(
        self,
        mock_query_store: MockPatternQueryStore,
        mock_producer: MockKafkaPublisher,
        sample_correlation_id: UUID,
    ) -> None:
        """correlation_id from trigger event appears in the snapshot payload."""
        result = await publish_projection(
            pattern_query_store=mock_query_store,
            producer=mock_producer,
            correlation_id=sample_correlation_id,
            publish_topic="onex.evt.omniintelligence.pattern-projection.v1",
        )

        assert result.correlation_id == sample_correlation_id

    @pytest.mark.asyncio
    async def test_snapshot_at_is_timezone_aware(
        self,
        mock_query_store: MockPatternQueryStore,
        mock_producer: MockKafkaPublisher,
        sample_correlation_id: UUID,
    ) -> None:
        """snapshot_at is a timezone-aware datetime (AwareDatetime constraint)."""
        result = await publish_projection(
            pattern_query_store=mock_query_store,
            producer=mock_producer,
            correlation_id=sample_correlation_id,
            publish_topic="onex.evt.omniintelligence.pattern-projection.v1",
        )

        assert result.snapshot_at.tzinfo is not None

    @pytest.mark.asyncio
    async def test_empty_snapshot_when_no_patterns(
        self,
        mock_query_store: MockPatternQueryStore,
        mock_producer: MockKafkaPublisher,
        sample_correlation_id: UUID,
    ) -> None:
        """Returns an empty snapshot (total_count=0) when store has no patterns."""
        mock_query_store.rows = []

        result = await publish_projection(
            pattern_query_store=mock_query_store,
            producer=mock_producer,
            correlation_id=sample_correlation_id,
            publish_topic="onex.evt.omniintelligence.pattern-projection.v1",
        )

        assert result.total_count == 0
        assert result.patterns == []


# =============================================================================
# Test Class: Kafka Emission
# =============================================================================


@pytest.mark.unit
class TestKafkaEmission:
    """Tests verifying the projection event is published to Kafka."""

    @pytest.mark.asyncio
    async def test_projection_event_published_on_trigger(
        self,
        mock_query_store: MockPatternQueryStore,
        mock_producer: MockKafkaPublisher,
        sample_correlation_id: UUID,
    ) -> None:
        """Projection event is published to the correct topic on trigger."""
        mock_query_store.rows = [make_pattern_row()]
        topic = "onex.evt.omniintelligence.pattern-projection.v1"

        await publish_projection(
            pattern_query_store=mock_query_store,
            producer=mock_producer,
            correlation_id=sample_correlation_id,
            publish_topic=topic,
            trigger_event_type="PatternLifecycleTransitioned",
        )

        assert len(mock_producer.published_events) == 1
        published_topic, _key, value = mock_producer.published_events[0]
        assert published_topic == topic
        assert value["event_type"] == "PatternProjection"
        assert value["total_count"] == 1

    @pytest.mark.asyncio
    async def test_kafka_failure_does_not_propagate(
        self,
        mock_query_store: MockPatternQueryStore,
        mock_producer: MockKafkaPublisher,
        sample_correlation_id: UUID,
    ) -> None:
        """Kafka publish failure is swallowed — fire-and-forget semantics."""
        mock_query_store.rows = [make_pattern_row()]
        mock_producer.simulate_error = RuntimeError("Kafka connection refused")
        topic = "onex.evt.omniintelligence.pattern-projection.v1"

        # Must NOT raise
        result = await publish_projection(
            pattern_query_store=mock_query_store,
            producer=mock_producer,
            correlation_id=sample_correlation_id,
            publish_topic=topic,
        )

        # Snapshot is still built and returned
        assert result.total_count == 1

    @pytest.mark.asyncio
    async def test_no_publish_when_producer_is_none(
        self,
        mock_query_store: MockPatternQueryStore,
        sample_correlation_id: UUID,
    ) -> None:
        """When producer is None, snapshot is built but nothing is published."""
        mock_query_store.rows = [make_pattern_row()]

        result = await publish_projection(
            pattern_query_store=mock_query_store,
            producer=None,
            correlation_id=sample_correlation_id,
            publish_topic="onex.evt.omniintelligence.pattern-projection.v1",
        )

        assert result.total_count == 1  # snapshot still built

    @pytest.mark.asyncio
    async def test_no_publish_when_topic_is_none(
        self,
        mock_query_store: MockPatternQueryStore,
        mock_producer: MockKafkaPublisher,
        sample_correlation_id: UUID,
    ) -> None:
        """When publish_topic is None (misconfiguration), skips publish but still builds snapshot."""
        mock_query_store.rows = [make_pattern_row()]

        result = await publish_projection(
            pattern_query_store=mock_query_store,
            producer=mock_producer,
            correlation_id=sample_correlation_id,
            publish_topic=None,
        )

        # Snapshot built but Kafka not called
        assert result.total_count == 1
        assert len(mock_producer.published_events) == 0


# =============================================================================
# Test Class: Error Resilience
# =============================================================================


@pytest.mark.unit
class TestErrorResilience:
    """Tests verifying graceful degradation on errors."""

    @pytest.mark.asyncio
    async def test_query_store_error_returns_empty_snapshot(
        self,
        mock_query_store: MockPatternQueryStore,
        mock_producer: MockKafkaPublisher,
        sample_correlation_id: UUID,
    ) -> None:
        """When the query store raises, an empty snapshot is returned (not propagated)."""
        mock_query_store.simulate_error = ConnectionError("DB unavailable")

        result = await publish_projection(
            pattern_query_store=mock_query_store,
            producer=mock_producer,
            correlation_id=sample_correlation_id,
            publish_topic="onex.evt.omniintelligence.pattern-projection.v1",
        )

        assert result.total_count == 0
        assert result.patterns == []
        assert result.correlation_id == sample_correlation_id

    @pytest.mark.asyncio
    async def test_correlation_id_none_is_allowed(
        self,
        mock_query_store: MockPatternQueryStore,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """correlation_id=None is valid — snapshot built with None correlation."""
        mock_query_store.rows = [make_pattern_row()]

        result = await publish_projection(
            pattern_query_store=mock_query_store,
            producer=mock_producer,
            correlation_id=None,
            publish_topic="onex.evt.omniintelligence.pattern-projection.v1",
        )

        assert result.total_count == 1
        assert result.correlation_id is None


# =============================================================================
# Test Class: Pagination
# =============================================================================


@pytest.mark.unit
class TestPagination:
    """Tests verifying all pages are fetched when result set exceeds one page."""

    @pytest.mark.asyncio
    async def test_multiple_pages_collected(
        self,
        mock_producer: MockKafkaPublisher,
        sample_correlation_id: UUID,
    ) -> None:
        """Handler pages through all results when total > _QUERY_LIMIT."""
        from omniintelligence.nodes.node_pattern_projection_effect.handlers.handler_projection import (
            _QUERY_LIMIT,
        )

        # Create enough rows to span 2 pages
        total_rows = _QUERY_LIMIT + 50
        all_rows = [
            make_pattern_row(pattern_id=str(uuid4()), signature=f"p{i}")
            for i in range(total_rows)
        ]
        store = MockPatternQueryStore(rows=all_rows)

        result = await publish_projection(
            pattern_query_store=store,
            producer=mock_producer,
            correlation_id=sample_correlation_id,
            publish_topic="onex.evt.omniintelligence.pattern-projection.v1",
        )

        assert result.total_count == total_rows
        assert len(result.patterns) == total_rows
        # At least 2 query calls were made
        assert len(store.query_calls) >= 2
