"""
Unit Tests for PerformanceBaselineService

Tests baseline calculation, anomaly detection, and performance tracking.

Phase 5C: Performance Intelligence
Created: 2025-10-15
"""

import os
from datetime import datetime, timezone

import pytest
from archon_services.performance import (
    PerformanceBaselineService,
    PerformanceMeasurement,
)

# Test duration configuration (configurable via environment variables)
TEST_DURATION_FAST_MS = float(os.getenv("TEST_DURATION_FAST_MS", "50"))
TEST_DURATION_MEDIUM_MS = float(os.getenv("TEST_DURATION_MEDIUM_MS", "100"))
TEST_DURATION_SLOW_MS = float(os.getenv("TEST_DURATION_SLOW_MS", "500"))


class TestPerformanceMeasurement:
    """Test PerformanceMeasurement dataclass."""

    def test_create_measurement(self):
        """Test creating a performance measurement."""
        measurement = PerformanceMeasurement(
            operation="test_op",
            duration_ms=100.5,
            timestamp=datetime.now(timezone.utc),
            context={"key": "value"},
        )

        assert measurement.operation == "test_op"
        assert measurement.duration_ms == 100.5
        assert measurement.context == {"key": "value"}
        assert measurement.timestamp.tzinfo is not None

    def test_timezone_aware_timestamp(self):
        """Test that naive timestamps are converted to UTC."""
        naive_time = datetime.now()  # No timezone
        measurement = PerformanceMeasurement(
            operation="test_op",
            duration_ms=TEST_DURATION_FAST_MS,
            timestamp=naive_time,
            context={},
        )

        assert measurement.timestamp.tzinfo is not None
        assert measurement.timestamp.tzinfo == timezone.utc

    def test_default_context(self):
        """Test that context defaults to empty dict."""
        measurement = PerformanceMeasurement(
            operation="test_op", duration_ms=75.0, timestamp=datetime.now(timezone.utc)
        )

        assert measurement.context == {}


class TestPerformanceBaselineService:
    """Test PerformanceBaselineService functionality."""

    @pytest.fixture
    def baseline_service(self):
        """Create a fresh baseline service for each test."""
        return PerformanceBaselineService(max_measurements=100)

    @pytest.mark.asyncio
    async def test_record_measurement(self, baseline_service):
        """Test recording a single measurement."""
        await baseline_service.record_measurement(
            operation="test_operation", duration_ms=150.0, context={"test": "data"}
        )

        assert len(baseline_service.measurements) == 1
        assert baseline_service.measurements[0].operation == "test_operation"
        assert baseline_service.measurements[0].duration_ms == 150.0

    @pytest.mark.asyncio
    async def test_record_multiple_measurements(self, baseline_service):
        """Test recording multiple measurements."""
        for i in range(20):
            await baseline_service.record_measurement(
                operation="multi_test",
                duration_ms=TEST_DURATION_MEDIUM_MS + i,
                context={"iteration": i},
            )

        assert len(baseline_service.measurements) == 20
        assert baseline_service.get_measurement_count() == 20

    @pytest.mark.asyncio
    async def test_max_measurements_limit(self, baseline_service):
        """Test that measurements are trimmed to max_measurements."""
        # Record more than max_measurements (100)
        for i in range(150):
            await baseline_service.record_measurement(
                operation="overflow_test", duration_ms=float(i), context={}
            )

        # Should only keep last 100
        assert len(baseline_service.measurements) <= 100
        assert baseline_service.get_measurement_count() == 150

    @pytest.mark.asyncio
    async def test_insufficient_samples_no_baseline(self, baseline_service):
        """Test that baseline is not created with < 10 samples."""
        # Record 9 measurements (below threshold)
        for i in range(9):
            await baseline_service.record_measurement(
                operation="insufficient_samples",
                duration_ms=TEST_DURATION_MEDIUM_MS,
                context={},
            )

        # Force baseline update
        await baseline_service._update_baseline("insufficient_samples")

        # No baseline should exist
        baseline = await baseline_service.get_baseline("insufficient_samples")
        assert baseline is None

    @pytest.mark.asyncio
    async def test_baseline_creation_with_sufficient_samples(self, baseline_service):
        """Test baseline creation with >= 10 samples."""
        # Record 15 measurements
        durations = [
            100,
            105,
            110,
            115,
            120,
            125,
            130,
            135,
            140,
            145,
            150,
            155,
            160,
            165,
            170,
        ]
        for duration in durations:
            await baseline_service.record_measurement(
                operation="sufficient_samples", duration_ms=float(duration), context={}
            )

        # Force baseline update
        await baseline_service._update_baseline("sufficient_samples")

        # Baseline should exist
        baseline = await baseline_service.get_baseline("sufficient_samples")
        assert baseline is not None
        assert "p50" in baseline
        assert "p95" in baseline
        assert "p99" in baseline
        assert "mean" in baseline
        assert "std_dev" in baseline
        assert "sample_size" in baseline

    @pytest.mark.asyncio
    async def test_baseline_statistics_calculation(self, baseline_service):
        """Test accurate calculation of baseline statistics."""
        # Record 20 measurements with known values
        durations = list(range(100, 120))  # 100-119
        for duration in durations:
            await baseline_service.record_measurement(
                operation="stats_test", duration_ms=float(duration), context={}
            )

        # Force baseline update
        await baseline_service._update_baseline("stats_test")

        baseline = await baseline_service.get_baseline("stats_test")
        assert baseline is not None

        # Verify statistics
        assert baseline["mean"] == 109.5  # Mean of 100-119
        assert baseline["p50"] == 109.5  # Median of 100-119
        assert baseline["sample_size"] == 20
        assert baseline["std_dev"] > 0  # Should have non-zero std_dev

    @pytest.mark.asyncio
    async def test_baseline_p95_calculation(self, baseline_service):
        """Test p95 percentile calculation."""
        # Record 20 measurements (sufficient for p95 calculation)
        durations = list(range(100, 120))
        for duration in durations:
            await baseline_service.record_measurement(
                operation="p95_test", duration_ms=float(duration), context={}
            )

        await baseline_service._update_baseline("p95_test")
        baseline = await baseline_service.get_baseline("p95_test")

        # p95 should be near the 95th percentile (around 118)
        assert baseline["p95"] >= 117
        assert baseline["p95"] <= 119

    @pytest.mark.asyncio
    async def test_baseline_p99_with_100_samples(self, baseline_service):
        """Test p99 calculation with 100+ samples."""
        # Record 100 measurements
        durations = list(range(100, 200))
        for duration in durations:
            await baseline_service.record_measurement(
                operation="p99_test", duration_ms=float(duration), context={}
            )

        await baseline_service._update_baseline("p99_test")
        baseline = await baseline_service.get_baseline("p99_test")

        # p99 should be near the 99th percentile (around 198-199)
        assert baseline["p99"] >= 197
        assert baseline["p99"] <= 199

    @pytest.mark.asyncio
    async def test_anomaly_detection_no_baseline(self, baseline_service):
        """Test anomaly detection when no baseline exists."""
        anomaly = await baseline_service.detect_performance_anomaly(
            operation="nonexistent_op", current_duration_ms=TEST_DURATION_SLOW_MS
        )

        assert anomaly["anomaly_detected"] is False
        assert anomaly["reason"] == "no_baseline"

    @pytest.mark.asyncio
    async def test_anomaly_detection_within_threshold(self, baseline_service):
        """Test that normal performance is not flagged as anomaly."""
        # Create baseline with mean=100, std_dev≈10
        durations = [90, 95, 100, 105, 110]
        for duration in durations * 2:  # 10 samples
            await baseline_service.record_measurement(
                operation="normal_op", duration_ms=float(duration), context={}
            )

        await baseline_service._update_baseline("normal_op")

        # Test duration within 3 std_devs
        anomaly = await baseline_service.detect_performance_anomaly(
            operation="normal_op", current_duration_ms=105.0, threshold_std_devs=3.0
        )

        assert anomaly["anomaly_detected"] is False
        assert abs(anomaly["z_score"]) < 3.0

    @pytest.mark.asyncio
    async def test_anomaly_detection_above_threshold(self, baseline_service):
        """Test that significant performance degradation is detected."""
        # Create baseline with mean=100, std_dev≈10
        durations = [90, 95, 100, 105, 110]
        for duration in durations * 2:  # 10 samples
            await baseline_service.record_measurement(
                operation="slow_op", duration_ms=float(duration), context={}
            )

        await baseline_service._update_baseline("slow_op")

        # Test duration far above mean (should be anomaly)
        anomaly = await baseline_service.detect_performance_anomaly(
            operation="slow_op",
            current_duration_ms=200.0,  # Way above mean
            threshold_std_devs=3.0,
        )

        assert anomaly["anomaly_detected"] is True
        assert anomaly["z_score"] > 3.0

    @pytest.mark.asyncio
    async def test_anomaly_detection_z_score_calculation(self, baseline_service):
        """Test Z-score calculation accuracy."""
        # Create baseline with known mean and std_dev
        # durations: 100, 100, 100, 100, 100 (mean=100, std_dev=0)
        for _ in range(10):
            await baseline_service.record_measurement(
                operation="zero_std_dev",
                duration_ms=TEST_DURATION_MEDIUM_MS,
                context={},
            )

        await baseline_service._update_baseline("zero_std_dev")

        # Test with different duration (std_dev=0 edge case)
        anomaly = await baseline_service.detect_performance_anomaly(
            operation="zero_std_dev", current_duration_ms=110.0
        )

        # Should detect anomaly even with zero std_dev
        assert anomaly["anomaly_detected"] is True
        assert anomaly["baseline_mean"] == 100.0

    @pytest.mark.asyncio
    async def test_anomaly_deviation_percentage(self, baseline_service):
        """Test deviation percentage calculation."""
        # Create baseline with mean=100
        for _ in range(10):
            await baseline_service.record_measurement(
                operation="deviation_test",
                duration_ms=TEST_DURATION_MEDIUM_MS,
                context={},
            )

        await baseline_service._update_baseline("deviation_test")

        # Test 50% slower
        anomaly = await baseline_service.detect_performance_anomaly(
            operation="deviation_test", current_duration_ms=150.0
        )

        # Should report 50% deviation
        assert abs(anomaly["deviation_percentage"] - 50.0) < 1.0

    @pytest.mark.asyncio
    async def test_get_all_baselines(self, baseline_service):
        """Test retrieving all baselines."""
        # Create baselines for multiple operations
        operations = ["op1", "op2", "op3"]
        for op in operations:
            for i in range(10):
                await baseline_service.record_measurement(
                    operation=op, duration_ms=TEST_DURATION_MEDIUM_MS + i, context={}
                )
            await baseline_service._update_baseline(op)

        all_baselines = await baseline_service.get_all_baselines()
        assert len(all_baselines) == 3
        assert "op1" in all_baselines
        assert "op2" in all_baselines
        assert "op3" in all_baselines

    @pytest.mark.asyncio
    async def test_get_operations(self, baseline_service):
        """Test getting list of operations with baselines."""
        # Create baselines
        for op in ["op_a", "op_b"]:
            for i in range(10):
                await baseline_service.record_measurement(op, 100.0, {})
            await baseline_service._update_baseline(op)

        operations = baseline_service.get_operations()
        assert len(operations) == 2
        assert "op_a" in operations
        assert "op_b" in operations

    @pytest.mark.asyncio
    async def test_get_recent_measurements(self, baseline_service):
        """Test retrieving recent measurements."""
        # Record 20 measurements
        for i in range(20):
            await baseline_service.record_measurement(
                operation="recent_test", duration_ms=float(i), context={"index": i}
            )

        # Get last 5
        recent = baseline_service.get_recent_measurements(limit=5)
        assert len(recent) == 5
        assert recent[-1].duration_ms == 19.0  # Last measurement

    @pytest.mark.asyncio
    async def test_get_recent_measurements_filtered(self, baseline_service):
        """Test filtering recent measurements by operation."""
        # Record measurements for multiple operations
        for i in range(10):
            await baseline_service.record_measurement("op_x", float(i), {})
            await baseline_service.record_measurement("op_y", float(i + 100), {})

        # Get recent for specific operation
        recent = baseline_service.get_recent_measurements(operation="op_x", limit=5)
        assert len(recent) == 5
        assert all(m.operation == "op_x" for m in recent)

    @pytest.mark.asyncio
    async def test_baseline_updates_every_10_measurements(self, baseline_service):
        """Test that baseline updates are triggered every 10 measurements."""
        operation = "auto_update_test"

        # Record 10 measurements (should trigger update)
        for i in range(10):
            await baseline_service.record_measurement(operation, 100.0, {})

        # Baseline should exist after 10 measurements
        baseline = await baseline_service.get_baseline(operation)
        assert baseline is not None

    @pytest.mark.asyncio
    async def test_multiple_operations_independent_baselines(self, baseline_service):
        """Test that different operations have independent baselines."""
        # Create different baselines for different operations
        for i in range(10):
            await baseline_service.record_measurement("fast_op", 50.0, {})
            await baseline_service.record_measurement("slow_op", 500.0, {})

        await baseline_service._update_baseline("fast_op")
        await baseline_service._update_baseline("slow_op")

        fast_baseline = await baseline_service.get_baseline("fast_op")
        slow_baseline = await baseline_service.get_baseline("slow_op")

        assert fast_baseline["mean"] == 50.0
        assert slow_baseline["mean"] == 500.0


@pytest.mark.asyncio
async def test_edge_case_single_measurement():
    """Test edge case with single measurement."""
    service = PerformanceBaselineService()
    await service.record_measurement("single_op", 100.0, {})

    # No baseline should exist with < 10 samples
    baseline = await service.get_baseline("single_op")
    assert baseline is None


@pytest.mark.asyncio
async def test_edge_case_zero_duration():
    """Test edge case with zero duration measurement."""
    service = PerformanceBaselineService()

    # Record measurements with zero duration
    for i in range(10):
        await service.record_measurement("zero_duration", 0.0, {})

    await service._update_baseline("zero_duration")

    baseline = await service.get_baseline("zero_duration")
    assert baseline is not None
    assert baseline["mean"] == 0.0
    assert baseline["std_dev"] == 0.0


@pytest.mark.asyncio
async def test_performance_overhead():
    """Test that measurement recording has minimal overhead (<1ms)."""
    import time

    service = PerformanceBaselineService()

    start = time.perf_counter()
    await service.record_measurement("overhead_test", 100.0, {"key": "value"})
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Recording should be fast (<1ms target, allow 5ms buffer)
    assert elapsed_ms < 5.0, f"Recording took {elapsed_ms:.2f}ms (target: <1ms)"
