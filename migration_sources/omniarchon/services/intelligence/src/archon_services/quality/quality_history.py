"""
Quality History Service

Tracks quality metrics over time for trend analysis and regression detection.
Part of Phase 5B: Quality Intelligence Upgrades.

Features:
- Quality snapshot recording with time-series data
- Linear regression-based trend calculation
- Threshold-based regression detection
- Project and file-level quality tracking
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class QualitySnapshot:
    """Quality metrics snapshot for time-series tracking"""

    timestamp: datetime
    project_id: str
    file_path: str
    quality_score: float
    compliance_score: float
    violations: List[str]
    warnings: List[str]
    correlation_id: str

    def __post_init__(self):
        """Ensure timezone awareness for timestamps"""
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)


class QualityHistoryService:
    """
    Track quality metrics over time for trend analysis.

    Capabilities:
    - Record quality snapshots with timestamps
    - Calculate quality trends using linear regression
    - Detect quality regressions using threshold comparison
    - Support project and file-level tracking
    """

    def __init__(self):
        """Initialize quality history service with in-memory storage"""
        self.snapshots: List[QualitySnapshot] = []
        logger.info("QualityHistoryService initialized")

    async def record_snapshot(
        self,
        project_id: str,
        file_path: str,
        validation_result: Dict[str, Any],
        correlation_id: str,
    ) -> None:
        """
        Record quality snapshot from validation result.

        Args:
            project_id: Project identifier
            file_path: Path to the file being validated
            validation_result: Validation result containing quality metrics
            correlation_id: Correlation ID for traceability
        """
        try:
            snapshot = QualitySnapshot(
                timestamp=datetime.now(timezone.utc),
                project_id=project_id,
                file_path=file_path,
                quality_score=validation_result.get("quality_score", 0.0),
                compliance_score=validation_result.get("onex_compliance_score", 0.0),
                violations=validation_result.get("violations", []),
                warnings=validation_result.get("warnings", []),
                correlation_id=correlation_id,
            )

            self.snapshots.append(snapshot)

            logger.info(
                f"Recorded quality snapshot for {project_id}/{file_path}: "
                f"quality={snapshot.quality_score:.2f}, "
                f"compliance={snapshot.compliance_score:.2f}"
            )
        except Exception as e:
            logger.error(f"Failed to record quality snapshot: {e}")
            raise

    async def get_quality_trend(
        self,
        project_id: str,
        file_path: Optional[str] = None,
        time_window_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Calculate quality trend over time using linear regression.

        Args:
            project_id: Project identifier
            file_path: Optional file path filter (None for project-level)
            time_window_days: Time window in days (default: 30)

        Returns:
            Dictionary containing:
            - trend: "improving" | "declining" | "stable" | "insufficient_data"
            - current_quality: Most recent quality score
            - avg_quality: Average quality score in window
            - slope: Linear regression slope
            - snapshots_count: Number of snapshots analyzed
            - time_window_days: Time window used
        """
        try:
            # Calculate cutoff time
            cutoff = datetime.now(timezone.utc) - timedelta(days=time_window_days)

            # Filter relevant snapshots
            relevant_snapshots = [
                s
                for s in self.snapshots
                if s.project_id == project_id
                and s.timestamp >= cutoff
                and (file_path is None or s.file_path == file_path)
            ]

            if not relevant_snapshots:
                logger.warning(
                    f"Insufficient data for quality trend: "
                    f"project={project_id}, file={file_path}"
                )
                return {
                    "trend": "insufficient_data",
                    "snapshots_count": 0,
                    "time_window_days": time_window_days,
                }

            # Sort by timestamp
            relevant_snapshots.sort(key=lambda x: x.timestamp)

            # Extract quality scores
            quality_scores = [s.quality_score for s in relevant_snapshots]
            n = len(quality_scores)

            # Calculate average quality
            avg_quality = sum(quality_scores) / n

            # Simple linear regression for trend
            # y = mx + b, where m is slope
            x = list(range(n))
            y = quality_scores

            x_mean = sum(x) / n
            y_mean = sum(y) / n

            # Calculate slope: m = Σ((x - x̄)(y - ȳ)) / Σ((x - x̄)²)
            numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

            # Handle edge case where all x values are the same
            if denominator == 0:
                slope = 0.0
            else:
                slope = numerator / denominator

            # Determine trend based on slope
            # Threshold: ±0.01 (1% change per unit)
            if slope > 0.01:
                trend = "improving"
            elif slope < -0.01:
                trend = "declining"
            else:
                trend = "stable"

            result = {
                "trend": trend,
                "current_quality": quality_scores[-1],
                "avg_quality": avg_quality,
                "slope": slope,
                "snapshots_count": n,
                "time_window_days": time_window_days,
            }

            logger.info(
                f"Quality trend calculated: project={project_id}, "
                f"file={file_path}, trend={trend}, slope={slope:.4f}"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to calculate quality trend: {e}")
            raise

    async def detect_quality_regression(
        self, project_id: str, current_score: float, threshold: float = 0.1
    ) -> Dict[str, Any]:
        """
        Detect quality regression by comparing current score to recent average.

        Args:
            project_id: Project identifier
            current_score: Current quality score to check
            threshold: Regression threshold (default: 0.1 = 10% decline)

        Returns:
            Dictionary containing:
            - regression_detected: Boolean indicating regression
            - current_score: Score being checked
            - avg_recent_score: Average of recent snapshots
            - difference: Difference from average
            - threshold: Threshold used for detection
        """
        try:
            # Get last 10 snapshots for project
            recent_snapshots = [
                s for s in self.snapshots[-10:] if s.project_id == project_id
            ]

            if not recent_snapshots:
                logger.warning(
                    f"No recent snapshots for regression detection: "
                    f"project={project_id}"
                )
                return {
                    "regression_detected": False,
                    "current_score": current_score,
                    "reason": "no_baseline_data",
                }

            # Calculate average recent quality
            avg_recent_quality = sum(s.quality_score for s in recent_snapshots) / len(
                recent_snapshots
            )

            # Calculate difference
            difference = avg_recent_quality - current_score

            # Detect regression: current score significantly below average
            regression_detected = difference > threshold

            result = {
                "regression_detected": regression_detected,
                "current_score": current_score,
                "avg_recent_score": avg_recent_quality,
                "difference": difference,
                "threshold": threshold,
                "snapshots_evaluated": len(recent_snapshots),
            }

            if regression_detected:
                logger.warning(
                    f"Quality regression detected: project={project_id}, "
                    f"current={current_score:.2f}, "
                    f"avg={avg_recent_quality:.2f}, "
                    f"difference={difference:.2f}"
                )
            else:
                logger.info(
                    f"No quality regression: project={project_id}, "
                    f"current={current_score:.2f}, "
                    f"avg={avg_recent_quality:.2f}"
                )

            return result

        except Exception as e:
            logger.error(f"Failed to detect quality regression: {e}")
            raise

    async def get_quality_history(
        self, project_id: str, file_path: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get quality history for specific file.

        Args:
            project_id: Project identifier
            file_path: File path
            limit: Maximum number of snapshots to return

        Returns:
            List of snapshot dictionaries sorted by timestamp (newest first)
        """
        try:
            # Filter snapshots for specific file
            file_snapshots = [
                s
                for s in self.snapshots
                if s.project_id == project_id and s.file_path == file_path
            ]

            # Sort by timestamp (newest first)
            file_snapshots.sort(key=lambda x: x.timestamp, reverse=True)

            # Limit results
            file_snapshots = file_snapshots[:limit]

            # Convert to dictionaries
            history = [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "quality_score": s.quality_score,
                    "compliance_score": s.compliance_score,
                    "violations": s.violations,
                    "warnings": s.warnings,
                    "correlation_id": s.correlation_id,
                }
                for s in file_snapshots
            ]

            logger.info(
                f"Retrieved quality history: project={project_id}, "
                f"file={file_path}, count={len(history)}"
            )

            return history

        except Exception as e:
            logger.error(f"Failed to get quality history: {e}")
            raise

    def get_snapshot_count(self) -> int:
        """Get total number of snapshots stored"""
        return len(self.snapshots)

    def clear_snapshots(self, project_id: Optional[str] = None) -> int:
        """
        Clear snapshots, optionally filtered by project.

        Args:
            project_id: Optional project filter (None clears all)

        Returns:
            Number of snapshots cleared
        """
        if project_id is None:
            count = len(self.snapshots)
            self.snapshots.clear()
            logger.info(f"Cleared all snapshots: count={count}")
            return count
        else:
            original_count = len(self.snapshots)
            self.snapshots = [s for s in self.snapshots if s.project_id != project_id]
            cleared_count = original_count - len(self.snapshots)
            logger.info(
                f"Cleared snapshots for project={project_id}: " f"count={cleared_count}"
            )
            return cleared_count
