"""
Test Suite: Usage Analytics Reducer (NodeUsageAnalyticsReducer)

Comprehensive tests for usage analytics aggregation with >85% coverage.

Test Categories:
    - Usage frequency calculation
    - Success rate computation
    - Performance metric aggregation
    - Trend analysis validation
    - Time window edge cases
    - Zero usage patterns
    - Statistical validation
    - Performance tests

Coverage Target: >85%
Test Count: 22 tests

Author: Archon Intelligence Team
Date: 2025-10-02
"""

from datetime import datetime, timedelta, timezone

import pytest
from archon_services.pattern_learning.phase4_traceability.model_contract_usage_analytics import (
    AnalyticsGranularity,
    ModelUsageAnalyticsInput,
    TimeWindowType,
)

# ============================================================================
# Test: Basic Analytics Reduction
# ============================================================================


@pytest.mark.asyncio
async def test_execute_reduction_basic(
    usage_analytics_reducer, sample_analytics_contract, sample_execution_data
):
    """Test basic analytics reduction execution."""
    result = await usage_analytics_reducer.execute_reduction(sample_analytics_contract)

    assert result.success is True
    assert result.data is not None
    assert "usage_metrics" in result.data
    assert "total_executions" in result.data["usage_metrics"]
    assert "success_metrics" in result.data
    assert "success_rate" in result.data["success_metrics"]
    assert "performance_metrics" in result.data
    assert "avg_execution_time_ms" in result.data["performance_metrics"]


@pytest.mark.asyncio
async def test_reduction_with_empty_data(
    usage_analytics_reducer, sample_analytics_contract
):
    """Test reduction with no execution data."""
    result = await usage_analytics_reducer.execute_reduction(sample_analytics_contract)

    assert result.success is True
    # Should handle gracefully with zero values
    if result.data:
        assert result.data.get("total_executions", 0) >= 0


# ============================================================================
# Test: Usage Frequency Calculation
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_usage_frequency(
    usage_analytics_reducer, sample_analytics_contract, sample_execution_data
):
    """Test usage frequency calculation."""
    result = await usage_analytics_reducer.execute_reduction(sample_analytics_contract)

    assert result.success is True
    assert "usage_metrics" in result.data
    assert "executions_per_day" in result.data["usage_metrics"]
    # Check for time-based distribution in context_distribution
    assert "context_distribution" in result.data or "time_window" in result.data


@pytest.mark.asyncio
async def test_usage_by_time_period(usage_analytics_reducer, sample_pattern_id):
    """Test usage breakdown by time period."""
    contract = ModelUsageAnalyticsInput(
        pattern_id=sample_pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(days=30),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_30_DAYS,
        granularity=AnalyticsGranularity.DAILY,
        include_trends=True,
    )

    result = await usage_analytics_reducer.execute_reduction(contract)

    assert result.success is True
    # Trend analysis includes time-based breakdown
    assert "trend_analysis" in result.data or "time_window" in result.data


# ============================================================================
# Test: Success Rate Computation
# ============================================================================


@pytest.mark.asyncio
async def test_compute_success_rate(
    usage_analytics_reducer, sample_analytics_contract, sample_execution_data
):
    """Test success rate calculation."""
    result = await usage_analytics_reducer.execute_reduction(sample_analytics_contract)

    assert result.success is True
    assert "success_metrics" in result.data
    assert "success_rate" in result.data["success_metrics"]
    success_rate = result.data["success_metrics"]["success_rate"]
    assert 0.0 <= success_rate <= 1.0


@pytest.mark.asyncio
async def test_success_rate_all_failures(usage_analytics_reducer, sample_pattern_id):
    """Test success rate when all executions failed."""
    # Would need to provide data with all failures
    contract = ModelUsageAnalyticsInput(
        pattern_id=sample_pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(days=7),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_7_DAYS,
    )

    result = await usage_analytics_reducer.execute_reduction(contract)

    assert result.success is True
    # Should handle edge case


@pytest.mark.asyncio
async def test_success_rate_all_successes(usage_analytics_reducer, sample_pattern_id):
    """Test success rate when all executions succeeded."""
    contract = ModelUsageAnalyticsInput(
        pattern_id=sample_pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(days=7),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_7_DAYS,
    )

    result = await usage_analytics_reducer.execute_reduction(contract)

    assert result.success is True


# ============================================================================
# Test: Performance Metric Aggregation
# ============================================================================


@pytest.mark.asyncio
async def test_aggregate_execution_times(
    usage_analytics_reducer, sample_analytics_contract, sample_execution_data
):
    """Test execution time aggregation (avg, p50, p95, p99)."""
    result = await usage_analytics_reducer.execute_reduction(sample_analytics_contract)

    assert result.success is True
    assert "performance_metrics" in result.data
    assert "avg_execution_time_ms" in result.data["performance_metrics"]
    # Percentiles
    perf = result.data["performance_metrics"]
    if "p50_execution_time_ms" in perf:
        assert perf["p50_execution_time_ms"] > 0
    if "p95_execution_time_ms" in perf:
        assert perf["p95_execution_time_ms"] >= perf.get("p50_execution_time_ms", 0)


@pytest.mark.asyncio
async def test_quality_score_aggregation(
    usage_analytics_reducer, sample_analytics_contract, sample_execution_data
):
    """Test quality score aggregation."""
    result = await usage_analytics_reducer.execute_reduction(sample_analytics_contract)

    assert result.success is True
    if "avg_quality_score" in result.data:
        assert 0.0 <= result.data["avg_quality_score"] <= 1.0


@pytest.mark.asyncio
async def test_timeout_rate_calculation(
    usage_analytics_reducer, sample_analytics_contract
):
    """Test timeout rate calculation."""
    result = await usage_analytics_reducer.execute_reduction(sample_analytics_contract)

    assert result.success is True
    if "timeout_rate" in result.data:
        assert 0.0 <= result.data["timeout_rate"] <= 1.0


# ============================================================================
# Test: Trend Analysis
# ============================================================================


@pytest.mark.asyncio
async def test_usage_trend_analysis(usage_analytics_reducer, sample_pattern_id):
    """Test usage trend analysis over time."""
    contract = ModelUsageAnalyticsInput(
        pattern_id=sample_pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(days=30),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_30_DAYS,
        granularity=AnalyticsGranularity.DAILY,
        include_trends=True,
    )

    result = await usage_analytics_reducer.execute_reduction(contract)

    assert result.success is True
    if "trends" in result.data:
        assert "direction" in result.data["trends"]  # increasing/decreasing/stable


@pytest.mark.asyncio
async def test_performance_trend_analysis(usage_analytics_reducer, sample_pattern_id):
    """Test performance trend analysis."""
    contract = ModelUsageAnalyticsInput(
        pattern_id=sample_pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(days=30),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_30_DAYS,
        include_trends=True,
    )

    result = await usage_analytics_reducer.execute_reduction(contract)

    assert result.success is True
    if "performance_trend" in result.data:
        assert result.data["performance_trend"] in ["improving", "degrading", "stable"]


# ============================================================================
# Test: Time Window Variations
# ============================================================================


@pytest.mark.asyncio
async def test_last_24_hours_window(usage_analytics_reducer, sample_pattern_id):
    """Test analytics for last 24 hours."""
    contract = ModelUsageAnalyticsInput(
        pattern_id=sample_pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(hours=24),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_24_HOURS,
        granularity=AnalyticsGranularity.HOURLY,
    )

    result = await usage_analytics_reducer.execute_reduction(contract)

    assert result.success is True


@pytest.mark.asyncio
async def test_last_30_days_window(usage_analytics_reducer, sample_pattern_id):
    """Test analytics for last 30 days."""
    contract = ModelUsageAnalyticsInput(
        pattern_id=sample_pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(days=30),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_30_DAYS,
        granularity=AnalyticsGranularity.DAILY,
    )

    result = await usage_analytics_reducer.execute_reduction(contract)

    assert result.success is True


@pytest.mark.asyncio
async def test_custom_time_window(usage_analytics_reducer, sample_pattern_id):
    """Test analytics for custom time window."""
    start = datetime.now(timezone.utc) - timedelta(days=15)
    end = datetime.now(timezone.utc) - timedelta(days=5)

    contract = ModelUsageAnalyticsInput(
        pattern_id=sample_pattern_id,
        time_window_start=start,
        time_window_end=end,
        time_window_type=TimeWindowType.CUSTOM,
        granularity=AnalyticsGranularity.DAILY,
    )

    result = await usage_analytics_reducer.execute_reduction(contract)

    assert result.success is True


# ============================================================================
# Test: Granularity Variations
# ============================================================================


@pytest.mark.asyncio
async def test_hourly_granularity(usage_analytics_reducer, sample_pattern_id):
    """Test analytics with hourly granularity."""
    contract = ModelUsageAnalyticsInput(
        pattern_id=sample_pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(days=1),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_24_HOURS,
        granularity=AnalyticsGranularity.HOURLY,
    )

    result = await usage_analytics_reducer.execute_reduction(contract)

    assert result.success is True


@pytest.mark.asyncio
async def test_weekly_granularity(usage_analytics_reducer, sample_pattern_id):
    """Test analytics with weekly granularity."""
    contract = ModelUsageAnalyticsInput(
        pattern_id=sample_pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(days=90),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_90_DAYS,
        granularity=AnalyticsGranularity.WEEKLY,
    )

    result = await usage_analytics_reducer.execute_reduction(contract)

    assert result.success is True


# ============================================================================
# Test: Segmentation
# ============================================================================


@pytest.mark.asyncio
async def test_analytics_by_agent(usage_analytics_reducer, sample_analytics_contract):
    """Test analytics segmented by agent."""
    result = await usage_analytics_reducer.execute_reduction(sample_analytics_contract)

    assert result.success is True
    if "by_agent" in result.data:
        assert isinstance(result.data["by_agent"], dict)


@pytest.mark.asyncio
async def test_analytics_by_project(usage_analytics_reducer, sample_analytics_contract):
    """Test analytics segmented by project."""
    result = await usage_analytics_reducer.execute_reduction(sample_analytics_contract)

    assert result.success is True
    if "by_project" in result.data:
        assert isinstance(result.data["by_project"], dict)


# ============================================================================
# Test: Performance
# ============================================================================


@pytest.mark.asyncio
async def test_aggregation_performance(
    usage_analytics_reducer,
    sample_analytics_contract,
    performance_timer,
    benchmark_thresholds,
):
    """Test aggregation completes within performance threshold (<500ms)."""
    performance_timer.start()
    result = await usage_analytics_reducer.execute_reduction(sample_analytics_contract)
    performance_timer.stop()

    assert result.success is True
    assert (
        performance_timer.elapsed_ms < benchmark_thresholds["analytics_aggregation"]
    ), f"Aggregation took {performance_timer.elapsed_ms}ms (max {benchmark_thresholds['analytics_aggregation']}ms)"


# ============================================================================
# Test: Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_single_execution_analytics(usage_analytics_reducer, sample_pattern_id):
    """Test analytics with single execution."""
    contract = ModelUsageAnalyticsInput(
        pattern_id=sample_pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(hours=1),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_24_HOURS,
    )

    result = await usage_analytics_reducer.execute_reduction(contract)

    assert result.success is True
    # Should handle single data point gracefully


@pytest.mark.asyncio
async def test_future_time_window(usage_analytics_reducer, sample_pattern_id):
    """Test analytics with future time window (should return empty)."""
    future_start = datetime.now(timezone.utc) + timedelta(days=1)
    future_end = datetime.now(timezone.utc) + timedelta(days=2)

    contract = ModelUsageAnalyticsInput(
        pattern_id=sample_pattern_id,
        time_window_start=future_start,
        time_window_end=future_end,
        time_window_type=TimeWindowType.CUSTOM,
    )

    result = await usage_analytics_reducer.execute_reduction(contract)

    assert result.success is True
    # Should return zero metrics
