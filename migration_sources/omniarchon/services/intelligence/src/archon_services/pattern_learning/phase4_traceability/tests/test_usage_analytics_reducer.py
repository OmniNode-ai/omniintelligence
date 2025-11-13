"""
Unit Tests: Usage Analytics Reducer

Tests for ONEX Reducer node that aggregates pattern usage metrics.

ONEX Compliance: Test coverage >95%, performance <500ms
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from ..model_contract_usage_analytics import (
    AnalyticsGranularity,
    ModelUsageAnalyticsInput,
    TimeWindowType,
    UsageTrendType,
)
from ..node_usage_analytics_reducer import NodeUsageAnalyticsReducer

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def reducer():
    """Create usage analytics reducer instance."""
    return NodeUsageAnalyticsReducer()


@pytest.fixture
def sample_execution_data():
    """Create sample execution data for testing."""
    now = datetime.now(timezone.utc)
    data = []

    # Create 100 execution records over 7 days
    for i in range(100):
        timestamp = now - timedelta(days=6 - (i // 15), hours=i % 24)

        data.append(
            {
                "execution_id": str(uuid4()),
                "timestamp": timestamp,
                "success": i % 5 != 0,  # 80% success rate
                "execution_time_ms": 100 + (i % 50) * 10,  # 100-590ms
                "quality_score": 0.7 + (i % 30) * 0.01,  # 0.7-0.99
                "quality_gates_passed": i % 10 != 0,  # 90% pass rate
                "timeout": i % 20 == 0,  # 5% timeout rate
                "context_type": ["debugging", "api_design", "performance"][i % 3],
                "agent": f"agent-{i % 5}",  # 5 different agents
                "project": f"project-{i % 3}",  # 3 different projects
                "file_path": f"src/file_{i % 10}.py",  # 10 different files
            }
        )

    return data


@pytest.fixture
def empty_execution_data():
    """Create empty execution data for testing."""
    return []


@pytest.fixture
def single_execution_data():
    """Create single execution record for edge case testing."""
    now = datetime.now(timezone.utc)
    return [
        {
            "execution_id": str(uuid4()),
            "timestamp": now,
            "success": True,
            "execution_time_ms": 250,
            "quality_score": 0.85,
            "quality_gates_passed": True,
            "timeout": False,
            "context_type": "debugging",
            "agent": "agent-1",
            "project": "project-1",
            "file_path": "src/test.py",
        }
    ]


# ============================================================================
# Core Reducer Tests
# ============================================================================


@pytest.mark.asyncio
async def test_execute_reduction_basic(reducer, sample_execution_data):
    """Test basic analytics reduction execution."""
    now = datetime.now(timezone.utc)
    pattern_id = uuid4()

    contract = ModelUsageAnalyticsInput(
        pattern_id=pattern_id,
        time_window_start=now - timedelta(days=7),
        time_window_end=now,
        time_window_type=TimeWindowType.WEEKLY,
        granularity=AnalyticsGranularity.DETAILED,
        execution_data=sample_execution_data,
    )

    result = await reducer.execute_reduction(contract)

    # Verify output structure
    assert result.pattern_id == pattern_id
    assert result.total_data_points == len(sample_execution_data)
    assert result.computation_time_ms < 500  # Performance target
    assert 0.0 <= result.analytics_quality_score <= 1.0

    # Verify core metrics are present
    assert result.usage_metrics is not None
    assert result.success_metrics is not None
    assert result.performance_metrics is not None
    assert result.trend_analysis is not None
    assert result.context_distribution is not None


@pytest.mark.asyncio
async def test_execute_reduction_empty_data(reducer):
    """Test analytics reduction with empty execution data."""
    now = datetime.now(timezone.utc)
    pattern_id = uuid4()

    contract = ModelUsageAnalyticsInput(
        pattern_id=pattern_id,
        time_window_start=now - timedelta(days=7),
        time_window_end=now,
        execution_data=[],
    )

    result = await reducer.execute_reduction(contract)

    # Should return empty analytics without errors
    assert result.pattern_id == pattern_id
    assert result.total_data_points == 0
    assert result.usage_metrics.total_executions == 0
    assert result.success_metrics.success_count == 0


@pytest.mark.asyncio
async def test_execute_reduction_single_execution(reducer, single_execution_data):
    """Test analytics reduction with single execution."""
    now = datetime.now(timezone.utc)
    pattern_id = uuid4()

    contract = ModelUsageAnalyticsInput(
        pattern_id=pattern_id,
        time_window_start=now - timedelta(days=1),
        time_window_end=now,
        execution_data=single_execution_data,
    )

    result = await reducer.execute_reduction(contract)

    assert result.total_data_points == 1
    assert result.usage_metrics.total_executions == 1
    assert result.success_metrics.success_count == 1


# ============================================================================
# Usage Frequency Tests
# ============================================================================


def test_compute_usage_frequency(reducer, sample_execution_data):
    """Test usage frequency computation."""
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=7)
    end_time = now

    metrics = reducer._compute_usage_frequency(
        sample_execution_data, start_time, end_time
    )

    # Verify basic counts
    assert metrics.total_executions == 100
    assert metrics.executions_per_day > 0
    assert metrics.executions_per_week > 0
    assert metrics.executions_per_month > 0

    # Verify unique counts
    assert metrics.unique_contexts == 3  # 3 different context types
    assert metrics.unique_users == 5  # 5 different agents
    assert metrics.peak_daily_usage > 0

    # Verify time since last use is recent
    assert metrics.time_since_last_use is not None
    assert metrics.time_since_last_use < 24  # Within last 24 hours


def test_compute_usage_frequency_edge_cases(reducer, single_execution_data):
    """Test usage frequency with edge cases."""
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=1)
    end_time = now

    metrics = reducer._compute_usage_frequency(
        single_execution_data, start_time, end_time
    )

    assert metrics.total_executions == 1
    assert metrics.unique_contexts == 1
    assert metrics.unique_users == 1
    assert metrics.peak_daily_usage == 1


# ============================================================================
# Success Metrics Tests
# ============================================================================


def test_compute_success_metrics(reducer, sample_execution_data):
    """Test success/failure metrics computation."""
    metrics = reducer._compute_success_metrics(sample_execution_data)

    # Verify counts
    assert metrics.success_count > 0
    assert metrics.failure_count > 0
    assert metrics.success_count + metrics.failure_count == 100

    # Verify rates
    assert 0.0 <= metrics.success_rate <= 1.0
    assert 0.0 <= metrics.error_rate <= 1.0
    assert abs(metrics.success_rate + metrics.error_rate - 1.0) < 0.01

    # Verify other metrics
    assert metrics.timeout_count >= 0
    assert metrics.quality_gate_failures >= 0
    assert 0.0 <= metrics.avg_quality_score <= 1.0


def test_compute_success_metrics_perfect_success(reducer):
    """Test success metrics with 100% success rate."""
    data = [
        {"success": True, "quality_score": 0.95, "quality_gates_passed": True}
        for _ in range(10)
    ]

    metrics = reducer._compute_success_metrics(data)

    assert metrics.success_count == 10
    assert metrics.failure_count == 0
    assert metrics.success_rate == 1.0
    assert metrics.error_rate == 0.0


def test_compute_success_metrics_perfect_failure(reducer):
    """Test success metrics with 100% failure rate."""
    data = [
        {
            "success": False,
            "quality_score": 0.5,
            "quality_gates_passed": False,
            "timeout": True,
        }
        for _ in range(10)
    ]

    metrics = reducer._compute_success_metrics(data)

    assert metrics.success_count == 0
    assert metrics.failure_count == 10
    assert metrics.success_rate == 0.0
    assert metrics.error_rate == 1.0
    assert metrics.timeout_count == 10
    assert metrics.quality_gate_failures == 10


# ============================================================================
# Performance Metrics Tests
# ============================================================================


def test_compute_performance_metrics(reducer, sample_execution_data):
    """Test performance metrics computation."""
    metrics = reducer._compute_performance_metrics(sample_execution_data)

    # Verify all metrics are computed
    assert metrics.avg_execution_time_ms > 0
    assert metrics.p50_execution_time_ms > 0
    assert metrics.p95_execution_time_ms > 0
    assert metrics.p99_execution_time_ms > 0
    assert metrics.min_execution_time_ms > 0
    assert metrics.max_execution_time_ms > 0
    assert metrics.total_execution_time_ms > 0

    # Verify ordering
    assert metrics.min_execution_time_ms <= metrics.p50_execution_time_ms
    assert metrics.p50_execution_time_ms <= metrics.p95_execution_time_ms
    assert metrics.p95_execution_time_ms <= metrics.p99_execution_time_ms
    assert metrics.p99_execution_time_ms <= metrics.max_execution_time_ms


def test_compute_performance_metrics_uniform_times(reducer):
    """Test performance metrics with uniform execution times."""
    data = [{"execution_time_ms": 100} for _ in range(50)]

    metrics = reducer._compute_performance_metrics(data)

    # All percentiles should be the same
    assert metrics.avg_execution_time_ms == 100
    assert metrics.p50_execution_time_ms == 100
    assert metrics.p95_execution_time_ms == 100
    assert metrics.p99_execution_time_ms == 100
    assert metrics.min_execution_time_ms == 100
    assert metrics.max_execution_time_ms == 100
    assert metrics.std_dev_ms == 0.0


def test_compute_percentile(reducer):
    """Test percentile computation."""
    values = list(range(1, 101))  # 1-100

    p50 = reducer._compute_percentile(values, 50)
    p95 = reducer._compute_percentile(values, 95)
    p99 = reducer._compute_percentile(values, 99)

    # Approximate checks
    assert 49 <= p50 <= 51  # Should be ~50
    assert 94 <= p95 <= 96  # Should be ~95
    assert 98 <= p99 <= 100  # Should be ~99


# ============================================================================
# Trend Analysis Tests
# ============================================================================


def test_compute_trend_analysis(reducer, sample_execution_data):
    """Test trend analysis computation."""
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=7)
    end_time = now

    trend = reducer._compute_trend_analysis(
        sample_execution_data, start_time, end_time, TimeWindowType.WEEKLY
    )

    # Verify trend metrics are computed
    assert trend.trend_type in UsageTrendType
    assert isinstance(trend.velocity, float)
    assert isinstance(trend.acceleration, float)
    assert 0.0 <= trend.retention_rate <= 1.0
    assert 0.0 <= trend.churn_rate <= 1.0
    assert 0.0 <= trend.confidence_score <= 1.0

    # Retention + churn should be ~1.0
    assert abs(trend.retention_rate + trend.churn_rate - 1.0) < 0.01


def test_classify_trend(reducer):
    """Test trend classification."""
    # Growing trend
    trend = reducer._classify_trend(
        velocity=2.0, acceleration=0.5, total_executions=100
    )
    assert trend == UsageTrendType.GROWING

    # Declining trend
    trend = reducer._classify_trend(
        velocity=-2.0, acceleration=-0.5, total_executions=100
    )
    assert trend == UsageTrendType.DECLINING

    # Stable trend
    trend = reducer._classify_trend(
        velocity=0.1, acceleration=0.0, total_executions=100
    )
    assert trend == UsageTrendType.STABLE

    # Emerging pattern
    trend = reducer._classify_trend(velocity=0.5, acceleration=0.0, total_executions=5)
    assert trend == UsageTrendType.EMERGING

    # Abandoned pattern
    trend = reducer._classify_trend(
        velocity=-2.0, acceleration=-1.0, total_executions=3
    )
    assert trend == UsageTrendType.ABANDONED


def test_compute_velocity(reducer):
    """Test velocity computation."""
    # Increasing pattern
    increasing = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    velocity = reducer._compute_velocity(increasing)
    assert velocity > 0  # Positive velocity for growth

    # Decreasing pattern
    decreasing = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    velocity = reducer._compute_velocity(decreasing)
    assert velocity < 0  # Negative velocity for decline

    # Stable pattern
    stable = [5, 5, 5, 5, 5, 5, 5, 5, 5, 5]
    velocity = reducer._compute_velocity(stable)
    assert abs(velocity) < 0.1  # Near zero for stability


# ============================================================================
# Context Distribution Tests
# ============================================================================


def test_compute_context_distribution(reducer, sample_execution_data):
    """Test context distribution computation."""
    distribution = reducer._compute_context_distribution(sample_execution_data)

    # Verify all distribution types are computed
    assert len(distribution.by_context_type) > 0
    assert len(distribution.by_agent) > 0
    assert len(distribution.by_project) > 0
    assert len(distribution.by_file_type) > 0
    assert len(distribution.by_time_of_day) > 0
    assert len(distribution.by_day_of_week) > 0

    # Verify counts sum to total executions
    assert sum(distribution.by_context_type.values()) == 100
    assert sum(distribution.by_agent.values()) == 100
    assert sum(distribution.by_project.values()) == 100

    # Verify expected values
    assert "debugging" in distribution.by_context_type
    assert "api_design" in distribution.by_context_type
    assert "performance" in distribution.by_context_type


def test_compute_context_distribution_single_context(reducer):
    """Test context distribution with single context."""
    data = [
        {
            "context_type": "debugging",
            "agent": "agent-1",
            "project": "project-1",
            "file_path": "test.py",
            "timestamp": datetime.now(timezone.utc),
        }
        for _ in range(10)
    ]

    distribution = reducer._compute_context_distribution(data)

    # Should have single entry in each category
    assert len(distribution.by_context_type) == 1
    assert distribution.by_context_type["debugging"] == 10
    assert len(distribution.by_agent) == 1
    assert distribution.by_agent["agent-1"] == 10


# ============================================================================
# Quality and Utility Tests
# ============================================================================


def test_compute_analytics_quality_score(reducer):
    """Test analytics quality score computation."""
    now = datetime.now(timezone.utc)

    # High quality: many data points, long time window
    score = reducer._compute_analytics_quality_score(
        total_data_points=200, start_time=now - timedelta(days=30), end_time=now
    )
    assert 0.7 <= score <= 1.0

    # Medium quality: moderate data points
    score = reducer._compute_analytics_quality_score(
        total_data_points=50, start_time=now - timedelta(days=7), end_time=now
    )
    assert 0.3 <= score <= 0.7

    # Low quality: few data points, short time window
    score = reducer._compute_analytics_quality_score(
        total_data_points=5, start_time=now - timedelta(days=1), end_time=now
    )
    assert 0.0 <= score <= 0.3


def test_create_empty_analytics(reducer):
    """Test empty analytics creation."""
    now = datetime.now(timezone.utc)
    pattern_id = uuid4()

    contract = ModelUsageAnalyticsInput(
        pattern_id=pattern_id,
        time_window_start=now - timedelta(days=7),
        time_window_end=now,
        execution_data=[],
    )

    result = reducer._create_empty_analytics(contract)

    assert result.pattern_id == pattern_id
    assert result.total_data_points == 0
    assert result.usage_metrics.total_executions == 0
    assert result.success_metrics.success_count == 0
    assert result.analytics_quality_score == 0.0


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_performance_large_dataset(reducer):
    """Test performance with large dataset (1000+ records)."""
    now = datetime.now(timezone.utc)
    pattern_id = uuid4()

    # Create 1000 execution records
    large_dataset = []
    for i in range(1000):
        timestamp = now - timedelta(days=30 - (i // 35), hours=i % 24)
        large_dataset.append(
            {
                "execution_id": str(uuid4()),
                "timestamp": timestamp,
                "success": i % 4 != 0,
                "execution_time_ms": 100 + (i % 100) * 5,
                "quality_score": 0.7 + (i % 30) * 0.01,
                "context_type": ["debugging", "api", "performance"][i % 3],
                "agent": f"agent-{i % 10}",
                "project": f"project-{i % 5}",
                "file_path": f"src/file_{i % 20}.py",
            }
        )

    contract = ModelUsageAnalyticsInput(
        pattern_id=pattern_id,
        time_window_start=now - timedelta(days=30),
        time_window_end=now,
        execution_data=large_dataset,
    )

    result = await reducer.execute_reduction(contract)

    # Verify performance target
    assert result.computation_time_ms < 500  # <500ms target
    assert result.total_data_points == 1000


# ============================================================================
# Contract Validation Tests
# ============================================================================


def test_input_contract_validation():
    """Test input contract validation."""
    now = datetime.now(timezone.utc)

    # Invalid: end time before start time
    with pytest.raises(ValueError):
        ModelUsageAnalyticsInput(
            pattern_id=uuid4(),
            time_window_start=now,
            time_window_end=now - timedelta(days=1),
        )


def test_output_contract_to_dict(reducer, sample_execution_data):
    """Test output contract serialization."""
    now = datetime.now(timezone.utc)

    result_dict = {
        "pattern_id": str(uuid4()),
        "time_window": {
            "start": (now - timedelta(days=7)).isoformat(),
            "end": now.isoformat(),
            "type": TimeWindowType.WEEKLY.value,
        },
        "usage_metrics": {
            "total_executions": 100,
            "executions_per_day": 14.29,
        },
    }

    # Should serialize without errors
    assert isinstance(result_dict, dict)
    assert "pattern_id" in result_dict
    assert "time_window" in result_dict
    assert "usage_metrics" in result_dict


# ============================================================================
# Edge Case Tests
# ============================================================================


@pytest.mark.asyncio
async def test_missing_optional_fields(reducer):
    """Test handling of missing optional fields in execution data."""
    now = datetime.now(timezone.utc)
    pattern_id = uuid4()

    # Data with minimal fields
    minimal_data = [
        {
            "timestamp": now - timedelta(hours=i),
            "success": True,
        }
        for i in range(10)
    ]

    contract = ModelUsageAnalyticsInput(
        pattern_id=pattern_id,
        time_window_start=now - timedelta(days=1),
        time_window_end=now,
        execution_data=minimal_data,
    )

    result = await reducer.execute_reduction(contract)

    # Should handle missing fields gracefully
    assert result.total_data_points == 10
    assert result.usage_metrics.total_executions == 10
    assert result.success_metrics.success_count == 10


@pytest.mark.asyncio
async def test_optional_analytics_flags(reducer, sample_execution_data):
    """Test disabling optional analytics."""
    now = datetime.now(timezone.utc)
    pattern_id = uuid4()

    contract = ModelUsageAnalyticsInput(
        pattern_id=pattern_id,
        time_window_start=now - timedelta(days=7),
        time_window_end=now,
        execution_data=sample_execution_data,
        include_performance=False,
        include_trends=False,
        include_distribution=False,
    )

    result = await reducer.execute_reduction(contract)

    # Optional metrics should be None
    assert result.performance_metrics is None
    assert result.trend_analysis is None
    assert result.context_distribution is None

    # Core metrics should still be present
    assert result.usage_metrics is not None
    assert result.success_metrics is not None


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_full_analytics_workflow(reducer):
    """Test complete analytics workflow from end to end."""
    now = datetime.now(timezone.utc)
    pattern_id = uuid4()

    # Create realistic execution data over 30 days
    execution_data = []
    for day in range(30):
        # Simulate increasing usage over time
        executions_per_day = 5 + day  # Growing pattern

        for execution in range(executions_per_day):
            timestamp = now - timedelta(days=29 - day, hours=execution % 24)

            execution_data.append(
                {
                    "execution_id": str(uuid4()),
                    "timestamp": timestamp,
                    "success": execution % 10 != 0,  # 90% success
                    "execution_time_ms": 150 + (execution % 20) * 10,
                    "quality_score": 0.8 + (execution % 20) * 0.01,
                    "quality_gates_passed": execution % 15 != 0,
                    "timeout": False,
                    "context_type": ["debugging", "api"][execution % 2],
                    "agent": f"agent-{execution % 3}",
                    "project": "project-alpha",
                    "file_path": f"src/module_{execution % 5}.py",
                }
            )

    contract = ModelUsageAnalyticsInput(
        pattern_id=pattern_id,
        time_window_start=now - timedelta(days=30),
        time_window_end=now,
        time_window_type=TimeWindowType.MONTHLY,
        granularity=AnalyticsGranularity.COMPREHENSIVE,
        include_trends=True,
        include_performance=True,
        include_distribution=True,
        execution_data=execution_data,
    )

    result = await reducer.execute_reduction(contract)

    # Verify comprehensive analytics
    assert result.total_data_points > 0
    assert result.usage_metrics.total_executions > 0

    # Should detect growing trend
    assert result.trend_analysis is not None
    assert result.trend_analysis.trend_type == UsageTrendType.GROWING
    assert result.trend_analysis.velocity > 0

    # Performance metrics should be present
    assert result.performance_metrics is not None
    assert result.performance_metrics.avg_execution_time_ms > 0

    # Context distribution should show 2 context types, 3 agents
    assert result.context_distribution is not None
    assert len(result.context_distribution.by_context_type) == 2
    assert len(result.context_distribution.by_agent) == 3

    # Quality score should be high (lots of data)
    assert result.analytics_quality_score > 0.7

    # Performance target
    assert result.computation_time_ms < 500
