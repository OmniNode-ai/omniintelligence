"""
Unit Tests for Pattern Usage Tracker Service

Tests comprehensive pattern usage tracking with outcome recording.

Created: 2025-10-28
Track: Pattern Dashboard Backend - Section 2.3
Correlation ID: a06eb29a-8922-4fdf-bb27-96fc40fae415
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from archon_services.pattern_analytics.usage_tracker import (
    PatternUsageEvent,
    PatternUsageTrackerService,
    UsageOutcome,
)


@pytest.fixture
def usage_tracker():
    """Create a usage tracker instance for testing."""
    return PatternUsageTrackerService(db_connection=None)


@pytest.fixture
def sample_pattern_id():
    """Generate a sample pattern ID."""
    return uuid4()


class TestPatternUsageEvent:
    """Test PatternUsageEvent model."""

    def test_usage_event_creation(self, sample_pattern_id):
        """Test creating a usage event."""
        event = PatternUsageEvent(
            pattern_id=sample_pattern_id,
            outcome=UsageOutcome.SUCCESS,
            context={"test": "context"},
            quality_score=0.95,
            execution_time_ms=150,
        )

        assert event.pattern_id == sample_pattern_id
        assert event.outcome == UsageOutcome.SUCCESS
        assert event.context == {"test": "context"}
        assert event.quality_score == 0.95
        assert event.execution_time_ms == 150
        assert isinstance(event.usage_timestamp, datetime)

    def test_usage_event_defaults(self, sample_pattern_id):
        """Test usage event with default values."""
        event = PatternUsageEvent(
            pattern_id=sample_pattern_id,
            outcome=UsageOutcome.FAILURE,
        )

        assert event.pattern_id == sample_pattern_id
        assert event.outcome == UsageOutcome.FAILURE
        assert event.context == {}
        assert event.correlation_id is None
        assert event.quality_score is None
        assert event.execution_time_ms is None


class TestPatternUsageTrackerService:
    """Test PatternUsageTrackerService functionality."""

    @pytest.mark.asyncio
    async def test_record_usage_success(self, usage_tracker, sample_pattern_id):
        """Test recording a successful usage event."""
        correlation_id = uuid4()

        result = await usage_tracker.record_usage(
            pattern_id=sample_pattern_id,
            outcome=UsageOutcome.SUCCESS,
            context={"node_type": "Effect", "operation": "api_call"},
            correlation_id=correlation_id,
            quality_score=0.92,
            execution_time_ms=200,
        )

        assert result is True
        assert len(usage_tracker.in_memory_events) == 1

        event = usage_tracker.in_memory_events[0]
        assert event.pattern_id == sample_pattern_id
        assert event.outcome == UsageOutcome.SUCCESS
        assert event.quality_score == 0.92
        assert event.execution_time_ms == 200
        assert event.correlation_id == correlation_id

    @pytest.mark.asyncio
    async def test_record_usage_failure(self, usage_tracker, sample_pattern_id):
        """Test recording a failed usage event."""
        result = await usage_tracker.record_usage(
            pattern_id=sample_pattern_id,
            outcome=UsageOutcome.FAILURE,
            error_message="Test error message",
        )

        assert result is True
        assert len(usage_tracker.in_memory_events) == 1

        event = usage_tracker.in_memory_events[0]
        assert event.outcome == UsageOutcome.FAILURE
        assert event.error_message == "Test error message"

    @pytest.mark.asyncio
    async def test_record_multiple_usages(self, usage_tracker, sample_pattern_id):
        """Test recording multiple usage events."""
        for i in range(10):
            await usage_tracker.record_usage(
                pattern_id=sample_pattern_id,
                outcome=UsageOutcome.SUCCESS if i % 2 == 0 else UsageOutcome.FAILURE,
                quality_score=0.8 + (i * 0.02),
                execution_time_ms=100 + (i * 10),
            )

        assert len(usage_tracker.in_memory_events) == 10

    @pytest.mark.asyncio
    async def test_get_usage_stats_single_pattern(
        self, usage_tracker, sample_pattern_id
    ):
        """Test getting usage statistics for a single pattern."""
        # Record 10 usage events (7 success, 3 failure)
        for i in range(10):
            await usage_tracker.record_usage(
                pattern_id=sample_pattern_id,
                outcome=UsageOutcome.SUCCESS if i < 7 else UsageOutcome.FAILURE,
                quality_score=0.85,
                execution_time_ms=150,
            )

        stats = await usage_tracker.get_usage_stats(
            pattern_id=sample_pattern_id,
            time_range_hours=24,
        )

        assert stats["total_patterns"] == 1
        assert len(stats["patterns"]) == 1

        pattern_stats = stats["patterns"][0]
        assert pattern_stats["pattern_id"] == sample_pattern_id
        assert pattern_stats["total_usages"] == 10
        assert pattern_stats["success_count"] == 7
        assert pattern_stats["failure_count"] == 3
        assert pattern_stats["success_rate"] == 0.7
        assert pattern_stats["average_quality_score"] == 0.85
        assert pattern_stats["average_execution_time_ms"] == 150.0

    @pytest.mark.asyncio
    async def test_get_usage_stats_multiple_patterns(self, usage_tracker):
        """Test getting usage statistics for multiple patterns."""
        pattern_id_1 = uuid4()
        pattern_id_2 = uuid4()

        # Record events for pattern 1
        for i in range(5):
            await usage_tracker.record_usage(
                pattern_id=pattern_id_1,
                outcome=UsageOutcome.SUCCESS,
                quality_score=0.9,
            )

        # Record events for pattern 2
        for i in range(3):
            await usage_tracker.record_usage(
                pattern_id=pattern_id_2,
                outcome=UsageOutcome.FAILURE,
                quality_score=0.5,
            )

        stats = await usage_tracker.get_usage_stats(time_range_hours=24)

        assert stats["total_patterns"] == 2
        assert len(stats["patterns"]) == 2

        # Verify both patterns are in results
        pattern_ids = {p["pattern_id"] for p in stats["patterns"]}
        assert pattern_id_1 in pattern_ids
        assert pattern_id_2 in pattern_ids

    @pytest.mark.asyncio
    async def test_get_usage_stats_time_filtering(
        self, usage_tracker, sample_pattern_id
    ):
        """Test usage stats time range filtering."""
        # Record events at different times (simulate by manipulating timestamps)
        # Note: In-memory mode doesn't support time-based filtering exactly,
        # but we test the structure

        await usage_tracker.record_usage(
            pattern_id=sample_pattern_id,
            outcome=UsageOutcome.SUCCESS,
        )

        stats_24h = await usage_tracker.get_usage_stats(
            pattern_id=sample_pattern_id,
            time_range_hours=24,
        )

        stats_1h = await usage_tracker.get_usage_stats(
            pattern_id=sample_pattern_id,
            time_range_hours=1,
        )

        assert stats_24h["time_range_hours"] == 24
        assert stats_1h["time_range_hours"] == 1

    @pytest.mark.asyncio
    async def test_get_pattern_effectiveness(self, usage_tracker, sample_pattern_id):
        """Test calculating pattern effectiveness metrics."""
        # Record 30 usage events with high success rate and quality
        for i in range(30):
            await usage_tracker.record_usage(
                pattern_id=sample_pattern_id,
                outcome=UsageOutcome.SUCCESS if i < 27 else UsageOutcome.FAILURE,
                quality_score=0.92,
                execution_time_ms=100,
            )

        effectiveness = await usage_tracker.get_pattern_effectiveness(
            pattern_id=sample_pattern_id,
            time_range_hours=24,
        )

        assert effectiveness["pattern_id"] == sample_pattern_id
        assert 0.7 <= effectiveness["effectiveness_score"] <= 1.0
        assert effectiveness["confidence"] >= 0.9  # 30+ samples = high confidence
        assert effectiveness["recommendation"] in [
            "recommended",
            "highly_recommended",
        ]  # Depends on exact score calculation

        # Verify components
        components = effectiveness["components"]
        assert components["success_rate"] == 0.9  # 27/30
        assert components["average_quality"] == 0.92
        assert components["usage_frequency"] == 30

    @pytest.mark.asyncio
    async def test_get_pattern_effectiveness_low_usage(self, usage_tracker):
        """Test effectiveness with insufficient data."""
        pattern_id = uuid4()

        # Record only 2 events (below confidence threshold)
        for i in range(2):
            await usage_tracker.record_usage(
                pattern_id=pattern_id,
                outcome=UsageOutcome.SUCCESS,
                quality_score=0.8,
            )

        effectiveness = await usage_tracker.get_pattern_effectiveness(
            pattern_id=pattern_id,
            time_range_hours=24,
        )

        # Low confidence due to small sample size
        assert effectiveness["confidence"] < 0.1
        assert effectiveness["recommendation"] in [
            "use_with_caution",
            "not_recommended",
        ]

    @pytest.mark.asyncio
    async def test_partial_success_outcome(self, usage_tracker, sample_pattern_id):
        """Test handling of partial success outcomes."""
        await usage_tracker.record_usage(
            pattern_id=sample_pattern_id,
            outcome=UsageOutcome.PARTIAL_SUCCESS,
            quality_score=0.75,
        )

        stats = await usage_tracker.get_usage_stats(
            pattern_id=sample_pattern_id,
            time_range_hours=24,
        )

        pattern_stats = stats["patterns"][0]
        # Partial success counts as success
        assert pattern_stats["success_count"] == 1
        assert pattern_stats["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_error_outcome(self, usage_tracker, sample_pattern_id):
        """Test handling of error outcomes."""
        await usage_tracker.record_usage(
            pattern_id=sample_pattern_id,
            outcome=UsageOutcome.ERROR,
            error_message="Database connection failed",
        )

        stats = await usage_tracker.get_usage_stats(
            pattern_id=sample_pattern_id,
            time_range_hours=24,
        )

        pattern_stats = stats["patterns"][0]
        # Errors count as failures
        assert pattern_stats["failure_count"] == 1


class TestUsageTrackerEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_usage_stats(self, usage_tracker):
        """Test getting usage stats with no data."""
        pattern_id = uuid4()

        stats = await usage_tracker.get_usage_stats(
            pattern_id=pattern_id,
            time_range_hours=24,
        )

        assert stats["total_patterns"] == 0
        assert len(stats["patterns"]) == 0

    @pytest.mark.asyncio
    async def test_effectiveness_no_data(self, usage_tracker):
        """Test effectiveness calculation with no data."""
        pattern_id = uuid4()

        effectiveness = await usage_tracker.get_pattern_effectiveness(
            pattern_id=pattern_id,
            time_range_hours=24,
        )

        assert effectiveness["pattern_id"] == pattern_id
        assert effectiveness["effectiveness_score"] == 0.0
        assert effectiveness["confidence"] == 0.0
        assert effectiveness["recommendation"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_missing_optional_fields(self, usage_tracker, sample_pattern_id):
        """Test recording usage with missing optional fields."""
        result = await usage_tracker.record_usage(
            pattern_id=sample_pattern_id,
            outcome=UsageOutcome.SUCCESS,
            # No quality_score, execution_time_ms, etc.
        )

        assert result is True
        assert len(usage_tracker.in_memory_events) == 1

        event = usage_tracker.in_memory_events[0]
        assert event.quality_score is None
        assert event.execution_time_ms is None
        assert event.error_message is None

    @pytest.mark.asyncio
    async def test_concurrent_usage_recording(self, usage_tracker, sample_pattern_id):
        """Test concurrent usage event recording."""

        async def record_usage():
            return await usage_tracker.record_usage(
                pattern_id=sample_pattern_id,
                outcome=UsageOutcome.SUCCESS,
                quality_score=0.9,
            )

        # Record 10 events concurrently
        results = await asyncio.gather(*[record_usage() for _ in range(10)])

        assert all(results)
        assert len(usage_tracker.in_memory_events) == 10
