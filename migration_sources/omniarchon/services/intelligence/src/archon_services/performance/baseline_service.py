"""
Performance Baseline Service

Establishes performance baselines for handler operations and detects anomalies.

Features:
- Time-series performance measurement tracking
- Baseline statistics calculation (p50, p95, p99, mean, std_dev)
- Z-score anomaly detection
- Performance trend monitoring

Phase 5C: Performance Intelligence
Created: 2025-10-15
"""

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# Performance Baseline Constants
# ===============================

# Baseline Calculation Thresholds
MIN_SAMPLES_FOR_BASELINE = 10  # Minimum samples required to establish reliable baseline
MIN_SAMPLES_FOR_P95 = 20  # Minimum samples for accurate p95 calculation
MIN_SAMPLES_FOR_P99 = 100  # Minimum samples for accurate p99 calculation
BASELINE_RECENT_WINDOW_SIZE = 100  # Number of recent measurements to use for baseline

# Anomaly Detection
ANOMALY_THRESHOLD_STD_DEVS = (
    3.0  # Default Z-score threshold for anomaly detection (3 sigma)
)
ANOMALY_TOLERANCE_MS = (
    0.1  # Tolerance for zero std_dev anomaly detection (milliseconds)
)

# Measurement Management
BASELINE_UPDATE_FREQUENCY = 10  # Update baseline every Nth measurement
RECENT_MEASUREMENTS_DEFAULT_LIMIT = 10  # Default limit for recent measurements query

# Cleanup Configuration
MEASUREMENT_RETENTION_HOURS_DEFAULT = 24  # Default hours to keep measurements


@dataclass
class PerformanceMeasurement:
    """
    Performance measurement data point.

    Represents a single performance measurement for an operation,
    capturing execution time, timestamp, and contextual information.
    """

    operation: str
    duration_ms: float
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure timestamp is timezone-aware (UTC)."""
        if self.timestamp.tzinfo is None:
            # Convert naive datetime to UTC
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)


class PerformanceBaselineService:
    """
    Establish and track performance baselines for operations.

    Uses in-memory storage for measurements and baselines. Calculates
    baseline statistics from recent measurements and detects performance
    anomalies using Z-score analysis.

    Memory Management:
    - Automatic cleanup of old measurements to prevent unbounded growth
    - Configurable max_measurements limit (count-based trimming)
    - Time-based cleanup via cleanup_old_measurements() method
    - Baseline recalculation after cleanup operations

    Performance Targets:
    - Measurement recording: <1ms overhead
    - Baseline calculation: <10ms (triggered every 10th measurement)
    - Anomaly detection: <5ms
    - Memory usage: <50MB for 10,000 measurements

    Note: Methods are marked async for interface consistency and forward
    compatibility, though current implementation uses only synchronous
    operations (in-memory list/dict manipulation).
    """

    def __init__(self, max_measurements: int = 1000):
        """
        Initialize performance baseline service.

        Args:
            max_measurements: Maximum measurements to keep in memory (default: 1000)
        """
        self.measurements: List[PerformanceMeasurement] = []
        self.baselines: Dict[str, Dict[str, Union[float, int]]] = {}
        self.max_measurements = max_measurements
        self._measurement_count = 0

        logger.info(
            f"PerformanceBaselineService initialized (max_measurements={max_measurements})"
        )

    async def record_measurement(
        self,
        operation: str,
        duration_ms: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a performance measurement for an operation.

        Stores the measurement and triggers baseline update if sufficient
        samples exist (≥10 samples).

        Args:
            operation: Operation name (e.g., "codegen_validation")
            duration_ms: Operation duration in milliseconds
            context: Optional context dictionary (e.g., node_type, event_type)
        """
        measurement = PerformanceMeasurement(
            operation=operation,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc),
            context=context or {},
        )

        self.measurements.append(measurement)
        self._measurement_count += 1

        # Trim measurements if exceeding max
        if len(self.measurements) > self.max_measurements:
            self.measurements = self.measurements[-self.max_measurements :]

        # Update baseline if enough samples
        if self._measurement_count % BASELINE_UPDATE_FREQUENCY == 0:
            await self._update_baseline(operation)

    async def _update_baseline(
        self, operation: str, correlation_id: Optional[UUID] = None
    ) -> None:
        """
        Update baseline statistics for an operation.

        Calculates baseline metrics from the last 100 measurements for the
        operation. Requires at least 10 samples to establish a baseline.

        Statistics calculated:
        - p50 (median): Middle value
        - p95: 95th percentile
        - p99: 99th percentile
        - mean: Average duration
        - std_dev: Standard deviation
        - sample_size: Number of measurements used

        Args:
            operation: Operation name to update baseline for
        """
        # Get recent measurements for this operation
        recent_measurements = [
            m
            for m in self.measurements[-BASELINE_RECENT_WINDOW_SIZE:]
            if m.operation == operation
        ]

        if len(recent_measurements) < MIN_SAMPLES_FOR_BASELINE:
            # Need sufficient samples for reliable baseline
            logger.debug(
                f"Insufficient samples for {operation} baseline "
                f"(have {len(recent_measurements)}, need {MIN_SAMPLES_FOR_BASELINE})"
            )
            return

        durations = [m.duration_ms for m in recent_measurements]
        sample_size = len(durations)

        # Calculate baseline statistics
        try:
            baseline = {
                "p50": statistics.median(durations),
                "mean": statistics.mean(durations),
                "std_dev": statistics.stdev(durations) if sample_size > 1 else 0.0,
                "sample_size": sample_size,
            }

            # Calculate p95 and p99 with proper quantile calculation
            if sample_size >= MIN_SAMPLES_FOR_P95:
                # Use quantiles for accurate percentile calculation
                baseline["p95"] = statistics.quantiles(
                    durations, n=MIN_SAMPLES_FOR_P95
                )[
                    MIN_SAMPLES_FOR_P95 - 2
                ]  # 95th percentile
            else:
                # Use max for small samples
                baseline["p95"] = max(durations)

            if sample_size >= MIN_SAMPLES_FOR_P99:
                # Use quantiles for accurate p99
                baseline["p99"] = statistics.quantiles(
                    durations, n=MIN_SAMPLES_FOR_P99
                )[
                    MIN_SAMPLES_FOR_P99 - 2
                ]  # 99th percentile
            else:
                # Use max for small samples
                baseline["p99"] = max(durations)

            self.baselines[operation] = baseline

            logger.debug(
                f"Updated baseline for {operation}: "
                f"p50={baseline['p50']:.2f}ms, "
                f"p95={baseline['p95']:.2f}ms, "
                f"mean={baseline['mean']:.2f}ms, "
                f"samples={sample_size}"
            )

        except (ValueError, ZeroDivisionError, statistics.StatisticsError) as e:
            logger.error(f"Invalid data for baseline calculation for {operation}: {e}")
        except Exception as e:
            # Catch-all for unexpected errors (shouldn't occur with in-memory data)
            logger.error(f"Unexpected error updating baseline for {operation}: {e}")

    async def detect_performance_anomaly(
        self,
        operation: str,
        current_duration_ms: float,
        threshold_std_devs: float = ANOMALY_THRESHOLD_STD_DEVS,
    ) -> Dict[str, Any]:
        """
        Detect if current duration is a performance anomaly.

        Uses Z-score analysis to determine if the current duration deviates
        significantly from the established baseline. A Z-score > threshold
        indicates an anomaly (default: 3.0 standard deviations).

        Z-score formula: (current_duration - mean) / std_dev

        Args:
            operation: Operation name
            current_duration_ms: Current operation duration in milliseconds
            threshold_std_devs: Z-score threshold for anomaly detection (default: 3.0)

        Returns:
            Dictionary containing:
            - anomaly_detected (bool): True if anomaly detected
            - z_score (float): Calculated Z-score
            - current_duration_ms (float): Input duration
            - baseline_mean (float): Baseline mean duration
            - baseline_p95 (float): Baseline 95th percentile
            - deviation_percentage (float): Percentage deviation from mean
            - reason (str): Reason if no baseline exists
        """
        baseline = self.baselines.get(operation)

        if not baseline:
            return {
                "anomaly_detected": False,
                "reason": "no_baseline",
                "current_duration_ms": current_duration_ms,
            }

        mean = baseline["mean"]
        std_dev = baseline["std_dev"]

        # Calculate Z-score
        if std_dev > 0:
            z_score = (current_duration_ms - mean) / std_dev
            anomaly_detected = abs(z_score) > threshold_std_devs
        else:
            # Zero std_dev means all measurements are identical
            # Consider anomaly if current duration differs from mean
            z_score = 0.0
            anomaly_detected = abs(current_duration_ms - mean) > ANOMALY_TOLERANCE_MS

        # Calculate deviation percentage
        deviation_percentage = (
            ((current_duration_ms - mean) / mean) * 100 if mean > 0 else 0.0
        )

        result = {
            "anomaly_detected": anomaly_detected,
            "z_score": round(z_score, 4),
            "current_duration_ms": current_duration_ms,
            "baseline_mean": round(mean, 2),
            "baseline_p95": round(baseline["p95"], 2),
            "deviation_percentage": round(deviation_percentage, 2),
        }

        if anomaly_detected:
            logger.warning(
                f"Performance anomaly detected for {operation}: "
                f"current={current_duration_ms:.2f}ms, "
                f"mean={mean:.2f}ms, "
                f"z_score={z_score:.2f}, "
                f"deviation={deviation_percentage:.1f}%"
            )

        return result

    async def get_baseline(
        self, operation: str, correlation_id: Optional[UUID] = None
    ) -> Optional[Dict[str, Union[float, int]]]:
        """
        Get baseline statistics for a specific operation.

        Args:
            operation: Operation name

        Returns:
            Baseline dictionary with statistics, or None if no baseline exists
        """
        return self.baselines.get(operation)

    async def get_all_baselines(self) -> Dict[str, Dict[str, Union[float, int]]]:
        """
        Get all operation baselines.

        Returns:
            Dictionary mapping operation names to baseline statistics
        """
        return self.baselines.copy()

    def get_measurement_count(self) -> int:
        """Get total number of measurements recorded."""
        return self._measurement_count

    def get_operations(self) -> List[str]:
        """Get list of operations with established baselines."""
        return list(self.baselines.keys())

    def get_recent_measurements(
        self,
        operation: Optional[str] = None,
        limit: int = RECENT_MEASUREMENTS_DEFAULT_LIMIT,
    ) -> List[PerformanceMeasurement]:
        """
        Get recent measurements, optionally filtered by operation.

        Args:
            operation: Optional operation name to filter by
            limit: Maximum number of measurements to return

        Returns:
            List of recent measurements
        """
        measurements = self.measurements

        if operation:
            measurements = [m for m in measurements if m.operation == operation]

        return measurements[-limit:]

    async def cleanup_old_measurements(
        self, max_age_hours: int = MEASUREMENT_RETENTION_HOURS_DEFAULT
    ) -> Dict[str, int]:
        """
        Remove measurements older than max_age_hours to prevent unbounded memory growth.

        Filters out measurements exceeding the age threshold, then recalculates
        baselines for affected operations. Operations with insufficient samples
        (<10 measurements) will have their baselines removed.

        Args:
            max_age_hours: Maximum age of measurements to keep (default: 24 hours)

        Returns:
            Dict with cleanup statistics:
            - total_before: Total measurements before cleanup
            - total_after: Total measurements after cleanup
            - removed: Number of measurements removed
            - operations_affected: Number of operations cleaned

        Example:
            cleanup_stats = await service.cleanup_old_measurements(max_age_hours=24)
            # Returns: {"total_before": 1500, "total_after": 800, "removed": 700, "operations_affected": 5}
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        before_count = len(self.measurements)
        operations_before = len(set(m.operation for m in self.measurements))

        # Remove old measurements
        self.measurements = [m for m in self.measurements if m.timestamp > cutoff]

        after_count = len(self.measurements)
        operations_after = len(set(m.operation for m in self.measurements))

        # Recalculate baselines for affected operations
        affected_operations = set(m.operation for m in self.measurements)

        for operation in affected_operations:
            operation_measurements = [
                m for m in self.measurements if m.operation == operation
            ]
            if len(operation_measurements) >= MIN_SAMPLES_FOR_BASELINE:
                [m.duration_ms for m in operation_measurements]
                # Recalculate baseline using existing logic
                await self._update_baseline(operation)
            elif operation in self.baselines:
                # Not enough samples left, remove baseline
                del self.baselines[operation]
                logger.info(
                    f"Removed baseline for {operation} "
                    f"(insufficient samples after cleanup: {len(operation_measurements)})"
                )

        removed_count = before_count - after_count
        operations_cleaned = operations_before - operations_after

        logger.info(
            f"Cleanup completed: removed {removed_count} measurements "
            f"older than {max_age_hours}h, affected {operations_cleaned} operations"
        )

        return {
            "total_before": before_count,
            "total_after": after_count,
            "removed": removed_count,
            "operations_affected": operations_cleaned,
        }
