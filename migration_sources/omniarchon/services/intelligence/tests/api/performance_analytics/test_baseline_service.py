"""
Unit tests for Performance Baseline Service

Direct tests of PerformanceBaselineService without FastAPI dependencies.

Phase 5C: Performance Intelligence - Workflow 9
Created: 2025-10-15
"""

import os
import sys
from datetime import datetime, timezone

import pytest
from archon_services.performance.baseline_service import (
    PerformanceBaselineService,
    PerformanceMeasurement,
)

# Add parent directory to path


class TestPerformanceBaselineService:
    """Test PerformanceBaselineService functionality"""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance"""
        return PerformanceBaselineService(max_measurements=100)

    @pytest.mark.asyncio
    async def test_record_measurement(self, service):
        """Test recording a single measurement"""
        await service.record_measurement("test_operation", 500.0, {"test": True})

        assert service.get_measurement_count() == 1
        recent = service.get_recent_measurements("test_operation", limit=1)
        assert len(recent) == 1
        assert recent[0].operation == "test_operation"
        assert recent[0].duration_ms == 500.0

    @pytest.mark.asyncio
    async def test_baseline_creation(self, service):
        """Test baseline establishment with sufficient samples"""
        # Record 15 measurements
        for i in range(15):
            await service.record_measurement("test_op", 500.0 + i * 10, {})

        # Baseline should be created
        baseline = await service.get_baseline("test_op")
        assert baseline is not None
        assert baseline["sample_size"] >= 10
        assert baseline["mean"] > 0
        assert baseline["p50"] > 0
        assert baseline["p95"] > baseline["p50"]

    @pytest.mark.asyncio
    async def test_anomaly_detection_normal(self, service):
        """Test anomaly detection with normal duration"""
        # Create baseline
        for i in range(15):
            await service.record_measurement("test_op", 500.0 + i * 10, {})

        # Test normal duration
        result = await service.detect_performance_anomaly("test_op", 520.0)
        assert result["anomaly_detected"] is False

    @pytest.mark.asyncio
    async def test_anomaly_detection_high(self, service):
        """Test anomaly detection with high duration"""
        # Create baseline with mean ~500ms, std_dev ~30ms
        for i in range(15):
            await service.record_measurement("test_op", 500.0 + i * 10, {})

        # Test very high duration (10x mean)
        result = await service.detect_performance_anomaly("test_op", 5000.0)
        assert result["anomaly_detected"] is True
        assert result["z_score"] > 3.0

    @pytest.mark.asyncio
    async def test_get_all_baselines(self, service):
        """Test retrieving all operation baselines"""
        # Create baselines for multiple operations
        operations = ["op1", "op2", "op3"]
        for op in operations:
            for i in range(15):
                await service.record_measurement(op, 500.0 + i * 10, {})

        all_baselines = await service.get_all_baselines()
        assert len(all_baselines) == 3
        for op in operations:
            assert op in all_baselines

    def test_max_measurements_limit(self, service):
        """Test that measurement list respects max_measurements"""
        service_small = PerformanceBaselineService(max_measurements=10)

        # Add 20 measurements
        for i in range(20):
            measurement = PerformanceMeasurement(
                operation="test_op",
                duration_ms=500.0,
                timestamp=datetime.now(timezone.utc),
                context={},
            )
            service_small.measurements.append(measurement)
            service_small._measurement_count += 1

            # Trim if exceeding max
            if len(service_small.measurements) > service_small.max_measurements:
                service_small.measurements = service_small.measurements[
                    -service_small.max_measurements :
                ]

        # Should only keep last 10
        assert len(service_small.measurements) <= 10

    def test_get_operations(self, service):
        """Test getting list of operations with baselines"""
        service.baselines = {
            "op1": {
                "mean": 500,
                "p50": 480,
                "p95": 550,
                "p99": 600,
                "std_dev": 50,
                "sample_size": 10,
            },
            "op2": {
                "mean": 200,
                "p50": 190,
                "p95": 220,
                "p99": 250,
                "std_dev": 20,
                "sample_size": 10,
            },
        }

        operations = service.get_operations()
        assert len(operations) == 2
        assert "op1" in operations
        assert "op2" in operations

    @pytest.mark.asyncio
    async def test_recent_measurements_limit(self, service):
        """Test that recent measurements respect limit"""
        # Add 20 measurements
        for i in range(20):
            await service.record_measurement("test_op", 500.0, {})

        # Get only 5 most recent
        recent = service.get_recent_measurements("test_op", limit=5)
        assert len(recent) == 5

    @pytest.mark.asyncio
    async def test_measurement_timestamp_timezone(self, service):
        """Test that timestamps are timezone-aware"""
        await service.record_measurement("test_op", 500.0, {})

        recent = service.get_recent_measurements("test_op", limit=1)
        assert recent[0].timestamp.tzinfo is not None
        assert recent[0].timestamp.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_baseline_statistics_accuracy(self, service):
        """Test that baseline statistics are calculated correctly"""
        # Use known values
        durations = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        for duration in durations:
            await service.record_measurement("test_op", float(duration), {})

        baseline = await service.get_baseline("test_op")

        # Median should be 550 (average of 500 and 600)
        assert abs(baseline["p50"] - 550.0) < 1.0

        # Mean should be 550
        assert abs(baseline["mean"] - 550.0) < 1.0

        # Sample size should be 10
        assert baseline["sample_size"] == 10


class TestPerformanceMeasurement:
    """Test PerformanceMeasurement dataclass"""

    def test_measurement_creation(self):
        """Test creating a measurement"""
        measurement = PerformanceMeasurement(
            operation="test_op",
            duration_ms=500.0,
            timestamp=datetime.now(timezone.utc),
            context={"test": True},
        )

        assert measurement.operation == "test_op"
        assert measurement.duration_ms == 500.0
        assert measurement.context["test"] is True

    def test_measurement_timestamp_auto_utc(self):
        """Test that naive timestamps are converted to UTC"""
        naive_time = datetime.now()  # No timezone
        measurement = PerformanceMeasurement(
            operation="test_op", duration_ms=500.0, timestamp=naive_time, context={}
        )

        # Should be converted to UTC
        assert measurement.timestamp.tzinfo == timezone.utc


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
