"""
Pattern Usage Tracker Service

Centralized service for tracking pattern usage with outcome recording.
Implements comprehensive usage tracking with effectiveness metrics.

ONEX v2.0 Compliance:
- Effect node for usage event recording (external I/O to database)
- Type-safe usage models
- Performance tracking (<200ms target)

Created: 2025-10-28
Track: Pattern Dashboard Backend - Section 2.3
Correlation ID: a06eb29a-8922-4fdf-bb27-96fc40fae415
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Usage Event Models
# ============================================================================


class UsageOutcome(str):
    """Usage outcome enumeration."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL_SUCCESS = "partial_success"
    ERROR = "error"


class PatternUsageEvent(BaseModel):
    """
    Pattern usage event for tracking.

    Records individual pattern usage with outcome and context.
    """

    pattern_id: UUID = Field(..., description="Pattern unique identifier")
    usage_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When pattern was used",
    )
    outcome: str = Field(..., description="Usage outcome (success/failure/etc)")
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Usage context metadata"
    )
    correlation_id: Optional[UUID] = Field(
        default=None, description="Correlation ID for tracing"
    )
    quality_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Quality score if available"
    )
    execution_time_ms: Optional[int] = Field(
        default=None, description="Execution time in milliseconds"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if outcome is error/failure"
    )


class UsageStatistics(BaseModel):
    """
    Aggregated usage statistics for a pattern.

    Provides comprehensive metrics on pattern usage and effectiveness.
    """

    pattern_id: UUID
    total_usages: int
    success_count: int
    failure_count: int
    success_rate: float = Field(ge=0.0, le=1.0)
    average_quality_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    average_execution_time_ms: Optional[float] = None
    usage_trend: str = Field(
        default="stable", description="Trend: increasing, decreasing, stable"
    )
    last_used: Optional[datetime] = None
    first_used: Optional[datetime] = None


# ============================================================================
# Usage Tracker Service
# ============================================================================


class PatternUsageTrackerService:
    """
    Track pattern usage with outcome recording.

    Provides:
    - Usage event recording to database
    - Usage statistics computation
    - Effectiveness metrics calculation
    - Temporal usage analysis
    - Outcome-based analytics
    """

    def __init__(self, db_connection=None):
        """
        Initialize usage tracker.

        Args:
            db_connection: Database connection for persistence (optional)
        """
        self.db = db_connection
        self.in_memory_events: List[PatternUsageEvent] = []
        logger.info("PatternUsageTrackerService initialized")

    # ========================================================================
    # Usage Recording
    # ========================================================================

    async def record_usage(
        self,
        pattern_id: UUID,
        outcome: str,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[UUID] = None,
        quality_score: Optional[float] = None,
        execution_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Record a pattern usage event.

        Args:
            pattern_id: Pattern UUID
            outcome: Usage outcome (success/failure/partial_success/error)
            context: Additional context metadata
            correlation_id: Correlation ID for tracing
            quality_score: Quality score if available (0.0-1.0)
            execution_time_ms: Execution time in milliseconds
            error_message: Error message if outcome is error/failure

        Returns:
            True if recorded successfully, False otherwise
        """
        try:
            event = PatternUsageEvent(
                pattern_id=pattern_id,
                outcome=outcome,
                context=context or {},
                correlation_id=correlation_id,
                quality_score=quality_score,
                execution_time_ms=execution_time_ms,
                error_message=error_message,
            )

            # Store in memory (for non-database mode)
            self.in_memory_events.append(event)

            # Persist to database if available
            if self.db:
                await self._persist_usage_event(event)

            logger.info(
                f"Usage recorded | pattern_id={pattern_id} | outcome={outcome} | "
                f"correlation_id={correlation_id}"
            )

            return True

        except Exception as e:
            logger.error(
                f"Failed to record usage for pattern {pattern_id}: {e}", exc_info=True
            )
            return False

    async def _persist_usage_event(self, event: PatternUsageEvent) -> None:
        """
        Persist usage event to database.

        Args:
            event: Usage event to persist
        """
        if not self.db:
            return

        try:
            query = """
                INSERT INTO pattern_feedback (
                    pattern_id,
                    created_at,
                    success,
                    quality_score,
                    execution_time_ms,
                    context,
                    correlation_id,
                    error_message
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """

            # Determine success boolean from outcome
            success = event.outcome in [
                UsageOutcome.SUCCESS,
                UsageOutcome.PARTIAL_SUCCESS,
            ]

            await self.db.execute(
                query,
                event.pattern_id,
                event.usage_timestamp,
                success,
                event.quality_score,
                event.execution_time_ms,
                event.context,
                event.correlation_id,
                event.error_message,
            )

            logger.debug(
                f"Usage event persisted to database | pattern_id={event.pattern_id}"
            )

        except Exception as e:
            logger.error(f"Failed to persist usage event: {e}", exc_info=True)
            # Don't raise - continue execution even if persistence fails

    # ========================================================================
    # Usage Statistics
    # ========================================================================

    async def get_usage_stats(
        self,
        pattern_id: Optional[UUID] = None,
        time_range_hours: int = 168,  # Default: 7 days
    ) -> Dict[str, Any]:
        """
        Get usage statistics for patterns.

        Args:
            pattern_id: Filter to specific pattern (optional)
            time_range_hours: Time range for analysis in hours

        Returns:
            Dictionary with usage statistics
        """
        logger.info(
            f"Computing usage stats | pattern_id={pattern_id} | time_range_hours={time_range_hours}"
        )

        if self.db:
            return await self._get_usage_stats_from_db(pattern_id, time_range_hours)
        else:
            return await self._get_usage_stats_from_memory(pattern_id, time_range_hours)

    async def _get_usage_stats_from_db(
        self, pattern_id: Optional[UUID], time_range_hours: int
    ) -> Dict[str, Any]:
        """
        Get usage statistics from database.

        Args:
            pattern_id: Filter to specific pattern (optional)
            time_range_hours: Time range for analysis

        Returns:
            Usage statistics dictionary
        """
        start_time = datetime.now(timezone.utc) - timedelta(hours=time_range_hours)

        query = """
            SELECT
                pattern_id,
                COUNT(*) as total_usages,
                SUM(CASE WHEN success = TRUE THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as failure_count,
                AVG(CASE WHEN success = TRUE THEN 1.0 ELSE 0.0 END) as success_rate,
                AVG(quality_score) as avg_quality_score,
                AVG(execution_time_ms) as avg_execution_time_ms,
                MIN(created_at) as first_used,
                MAX(created_at) as last_used
            FROM pattern_feedback
            WHERE created_at >= $1
        """

        params = [start_time]

        if pattern_id:
            query += " AND pattern_id = $2 GROUP BY pattern_id"
            params.append(pattern_id)
        else:
            query += " GROUP BY pattern_id"

        results = await self.db.fetch(query, *params)

        patterns_stats = []
        for row in results:
            # Calculate trend
            trend = await self._calculate_usage_trend(
                row["pattern_id"], time_range_hours
            )

            patterns_stats.append(
                {
                    "pattern_id": row["pattern_id"],
                    "total_usages": row["total_usages"],
                    "success_count": row["success_count"],
                    "failure_count": row["failure_count"],
                    "success_rate": (
                        float(row["success_rate"]) if row["success_rate"] else 0.0
                    ),
                    "average_quality_score": (
                        float(row["avg_quality_score"])
                        if row["avg_quality_score"]
                        else None
                    ),
                    "average_execution_time_ms": (
                        float(row["avg_execution_time_ms"])
                        if row["avg_execution_time_ms"]
                        else None
                    ),
                    "usage_trend": trend,
                    "first_used": row["first_used"],
                    "last_used": row["last_used"],
                }
            )

        return {
            "patterns": patterns_stats,
            "total_patterns": len(patterns_stats),
            "time_range_hours": time_range_hours,
        }

    async def _get_usage_stats_from_memory(
        self, pattern_id: Optional[UUID], time_range_hours: int
    ) -> Dict[str, Any]:
        """
        Get usage statistics from in-memory events.

        Args:
            pattern_id: Filter to specific pattern (optional)
            time_range_hours: Time range for analysis

        Returns:
            Usage statistics dictionary
        """
        start_time = datetime.now(timezone.utc) - timedelta(hours=time_range_hours)

        # Filter events by time range and pattern_id
        filtered_events = [
            e
            for e in self.in_memory_events
            if e.usage_timestamp >= start_time
            and (pattern_id is None or e.pattern_id == pattern_id)
        ]

        # Group by pattern_id
        pattern_events_map: Dict[UUID, List[PatternUsageEvent]] = {}
        for event in filtered_events:
            if event.pattern_id not in pattern_events_map:
                pattern_events_map[event.pattern_id] = []
            pattern_events_map[event.pattern_id].append(event)

        # Compute stats for each pattern
        patterns_stats = []
        for pid, events in pattern_events_map.items():
            success_count = sum(
                1
                for e in events
                if e.outcome in [UsageOutcome.SUCCESS, UsageOutcome.PARTIAL_SUCCESS]
            )
            failure_count = len(events) - success_count
            success_rate = success_count / len(events) if events else 0.0

            quality_scores = [
                e.quality_score for e in events if e.quality_score is not None
            ]
            avg_quality = (
                sum(quality_scores) / len(quality_scores) if quality_scores else None
            )

            exec_times = [
                e.execution_time_ms for e in events if e.execution_time_ms is not None
            ]
            avg_exec_time = sum(exec_times) / len(exec_times) if exec_times else None

            timestamps = [e.usage_timestamp for e in events]

            patterns_stats.append(
                {
                    "pattern_id": pid,
                    "total_usages": len(events),
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "success_rate": success_rate,
                    "average_quality_score": avg_quality,
                    "average_execution_time_ms": avg_exec_time,
                    "usage_trend": "stable",  # Simplified for in-memory
                    "first_used": min(timestamps) if timestamps else None,
                    "last_used": max(timestamps) if timestamps else None,
                }
            )

        return {
            "patterns": patterns_stats,
            "total_patterns": len(patterns_stats),
            "time_range_hours": time_range_hours,
        }

    async def _calculate_usage_trend(
        self, pattern_id: UUID, time_range_hours: int
    ) -> str:
        """
        Calculate usage trend for a pattern.

        Args:
            pattern_id: Pattern UUID
            time_range_hours: Time range for analysis

        Returns:
            Trend string: "increasing", "decreasing", or "stable"
        """
        if not self.db:
            return "stable"

        try:
            # Split time range into two halves and compare
            start_time = datetime.now(timezone.utc) - timedelta(hours=time_range_hours)
            midpoint = start_time + timedelta(hours=time_range_hours / 2)

            query = """
                SELECT
                    SUM(CASE WHEN created_at < $1 THEN 1 ELSE 0 END) as first_half,
                    SUM(CASE WHEN created_at >= $1 THEN 1 ELSE 0 END) as second_half
                FROM pattern_feedback
                WHERE pattern_id = $2 AND created_at >= $3
            """

            result = await self.db.fetchrow(query, midpoint, pattern_id, start_time)

            if not result:
                return "stable"

            first_half = result["first_half"] or 0
            second_half = result["second_half"] or 0

            if second_half > first_half * 1.2:  # 20% increase
                return "increasing"
            elif second_half < first_half * 0.8:  # 20% decrease
                return "decreasing"
            else:
                return "stable"

        except Exception as e:
            logger.error(f"Failed to calculate trend: {e}", exc_info=True)
            return "stable"

    # ========================================================================
    # Effectiveness Metrics
    # ========================================================================

    async def get_pattern_effectiveness(
        self, pattern_id: UUID, time_range_hours: int = 168
    ) -> Dict[str, Any]:
        """
        Get pattern effectiveness metrics.

        Effectiveness combines success rate, quality scores, and usage frequency.

        Args:
            pattern_id: Pattern UUID
            time_range_hours: Time range for analysis

        Returns:
            Effectiveness metrics dictionary
        """
        stats = await self.get_usage_stats(pattern_id, time_range_hours)

        if not stats["patterns"]:
            return {
                "pattern_id": pattern_id,
                "effectiveness_score": 0.0,
                "confidence": 0.0,
                "recommendation": "insufficient_data",
            }

        pattern_stats = stats["patterns"][0]

        # Calculate effectiveness score (weighted combination)
        success_weight = 0.5
        quality_weight = 0.3
        usage_weight = 0.2

        success_component = pattern_stats["success_rate"] * success_weight
        quality_component = (
            pattern_stats["average_quality_score"] or 0.0
        ) * quality_weight

        # Normalize usage count (assume 100+ usages is maximum)
        usage_normalized = min(pattern_stats["total_usages"] / 100.0, 1.0)
        usage_component = usage_normalized * usage_weight

        effectiveness_score = success_component + quality_component + usage_component

        # Calculate confidence based on sample size
        sample_size = pattern_stats["total_usages"]
        confidence = min(sample_size / 30.0, 1.0)  # Full confidence at 30+ samples

        # Generate recommendation
        if effectiveness_score >= 0.8 and confidence >= 0.7:
            recommendation = "highly_recommended"
        elif effectiveness_score >= 0.6 and confidence >= 0.5:
            recommendation = "recommended"
        elif effectiveness_score >= 0.4:
            recommendation = "use_with_caution"
        else:
            recommendation = "not_recommended"

        return {
            "pattern_id": pattern_id,
            "effectiveness_score": effectiveness_score,
            "confidence": confidence,
            "recommendation": recommendation,
            "components": {
                "success_rate": pattern_stats["success_rate"],
                "average_quality": pattern_stats["average_quality_score"],
                "usage_frequency": pattern_stats["total_usages"],
            },
            "metrics": pattern_stats,
        }


# ============================================================================
# Module Initialization
# ============================================================================

# Create singleton instance (can be overridden with custom db connection)
_default_tracker = None


def get_usage_tracker(db_connection=None) -> PatternUsageTrackerService:
    """
    Get usage tracker instance.

    Args:
        db_connection: Optional database connection

    Returns:
        PatternUsageTrackerService instance
    """
    global _default_tracker

    if _default_tracker is None:
        _default_tracker = PatternUsageTrackerService(db_connection)

    return _default_tracker
