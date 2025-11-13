"""
Pattern Analytics Service

Service layer for pattern feedback analytics, bridging the API and FeedbackLoopOrchestrator.
Provides high-level analytics operations on pattern feedback data.
"""

import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from src.archon_services.pattern_learning.phase4_traceability.models.model_pattern_feedback import (
    ModelPatternFeedback,
)
from src.archon_services.pattern_learning.phase4_traceability.node_feedback_loop_orchestrator import (
    NodeFeedbackLoopOrchestrator,
)

logger = logging.getLogger(__name__)


class PatternAnalyticsService:
    """
    Service for pattern feedback analytics.

    Provides methods to compute pattern success rates, identify top patterns,
    detect emerging patterns, and retrieve feedback history.
    """

    def __init__(
        self,
        feedback_orchestrator: Optional[NodeFeedbackLoopOrchestrator] = None,
        db_pool=None,
    ):
        """
        Initialize pattern analytics service.

        Args:
            feedback_orchestrator: FeedbackLoopOrchestrator instance (optional, will create if not provided)
            db_pool: Database connection pool for quality metric operations (optional)
        """
        self.orchestrator = feedback_orchestrator or NodeFeedbackLoopOrchestrator()
        self.db_pool = db_pool
        self.logger = logging.getLogger("PatternAnalyticsService")

    async def get_pattern_success_rates(
        self,
        pattern_type: Optional[str] = None,
        min_samples: int = 5,
    ) -> Dict[str, Any]:
        """
        Get success rates for all patterns with optional filtering.

        Args:
            pattern_type: Filter by pattern type (architectural, quality, performance, etc.)
            min_samples: Minimum number of feedback samples required

        Returns:
            Dictionary with patterns list and summary statistics
        """
        self.logger.info(
            f"Computing pattern success rates | pattern_type={pattern_type} | min_samples={min_samples}"
        )

        # Get all feedback from orchestrator
        all_feedback = self.orchestrator.feedback_store

        # Group feedback by pattern_id
        pattern_feedback_map: Dict[str, List[ModelPatternFeedback]] = {}
        for feedback in all_feedback:
            pattern_id = str(feedback.pattern_id)
            if pattern_id not in pattern_feedback_map:
                pattern_feedback_map[pattern_id] = []
            pattern_feedback_map[pattern_id].append(feedback)

        # Compute success rates for each pattern
        patterns = []
        for pattern_id, feedback_items in pattern_feedback_map.items():
            # Apply min_samples filter
            if len(feedback_items) < min_samples:
                continue

            # Compute metrics
            success_count = sum(1 for f in feedback_items if f.success)
            success_rate = success_count / len(feedback_items)

            # Compute confidence based on sample size
            sample_factor = min(
                len(feedback_items) / 30.0, 1.0
            )  # Full confidence at 30+ samples
            confidence = success_rate * sample_factor

            # Compute average quality score
            quality_scores = [
                f.quality_score for f in feedback_items if f.quality_score is not None
            ]
            avg_quality_score = mean(quality_scores) if quality_scores else 0.0

            # Extract common issues (most frequent)
            issue_counts = Counter(
                issue for f in feedback_items for issue in (f.issues or [])
            )
            common_issues = [issue for issue, _ in issue_counts.most_common(5)]

            # Determine pattern type and node type from context
            # Extract from first feedback item's context, with proper null handling
            first_feedback = feedback_items[0] if feedback_items else None
            pattern_context = (
                first_feedback.context
                if first_feedback
                and hasattr(first_feedback, "context")
                and first_feedback.context
                else {}
            )
            detected_pattern_type = pattern_context.get("pattern_type", "unknown")
            detected_node_type = pattern_context.get("node_type", "unknown")

            # Apply pattern_type filter
            if pattern_type and detected_pattern_type != pattern_type:
                continue

            patterns.append(
                {
                    "pattern_id": pattern_id,
                    "pattern_name": feedback_items[0].pattern_name
                    or f"pattern_{pattern_id[:8]}",
                    "pattern_type": detected_pattern_type,
                    "node_type": detected_node_type,
                    "success_rate": success_rate,
                    "confidence": confidence,
                    "sample_size": len(feedback_items),
                    "avg_quality_score": avg_quality_score,
                    "common_issues": common_issues,
                }
            )

        # Sort by success_rate descending
        patterns.sort(key=lambda x: x["success_rate"], reverse=True)

        # Compute summary
        summary = {
            "total_patterns": len(patterns),
            "avg_success_rate": (
                mean([p["success_rate"] for p in patterns]) if patterns else 0.0
            ),
            "high_confidence_patterns": sum(
                1 for p in patterns if p["confidence"] >= 0.8
            ),
        }

        self.logger.info(
            f"Computed success rates | total_patterns={summary['total_patterns']} | avg_success_rate={summary['avg_success_rate']:.2f}"
        )

        return {"patterns": patterns, "summary": summary}

    async def get_top_performing_patterns(
        self,
        node_type: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Get top performing patterns by node type.

        Args:
            node_type: Filter by ONEX node type (Effect, Compute, Reducer, Orchestrator)
            limit: Maximum number of patterns to return

        Returns:
            Dictionary with top patterns and filter criteria
        """
        self.logger.info(
            f"Getting top performing patterns | node_type={node_type} | limit={limit}"
        )

        # Get all success rates
        all_patterns_result = await self.get_pattern_success_rates(min_samples=5)
        all_patterns = all_patterns_result["patterns"]

        # Filter by node_type if specified
        if node_type:
            filtered_patterns = []
            for pattern in all_patterns:
                # Extract node_type from pattern data
                pattern_node_type = pattern.get("node_type", "unknown")
                if pattern_node_type.lower() == node_type.lower():
                    filtered_patterns.append(pattern)
            patterns_to_rank = filtered_patterns
        else:
            patterns_to_rank = all_patterns

        # Sort by success_rate * confidence (weighted score)
        patterns_to_rank.sort(
            key=lambda x: x["success_rate"] * x["confidence"], reverse=True
        )

        # Limit results
        top_patterns = patterns_to_rank[:limit]

        # Add ranking
        for rank, pattern in enumerate(top_patterns, start=1):
            pattern["rank"] = rank

        self.logger.info(f"Retrieved {len(top_patterns)} top performing patterns")

        return {
            "top_patterns": top_patterns,
            "total_patterns": len(top_patterns),
            "filter_criteria": {
                "node_type": node_type,
                "limit": limit,
            },
        }

    async def get_emerging_patterns(
        self,
        min_frequency: int = 5,
        time_window_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Get patterns that are emerging recently.

        Args:
            min_frequency: Minimum usage frequency in time window
            time_window_hours: Time window for analysis (hours)

        Returns:
            Dictionary with emerging patterns and filter criteria
        """
        self.logger.info(
            f"Detecting emerging patterns | min_frequency={min_frequency} | time_window_hours={time_window_hours}"
        )

        # Calculate cutoff time
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)

        # Get all feedback from orchestrator
        all_feedback = self.orchestrator.feedback_store

        # Filter feedback within time window
        recent_feedback = [f for f in all_feedback if f.created_at >= cutoff_time]

        # Group by pattern_id
        pattern_feedback_map: Dict[str, List[ModelPatternFeedback]] = {}
        for feedback in recent_feedback:
            pattern_id = str(feedback.pattern_id)
            if pattern_id not in pattern_feedback_map:
                pattern_feedback_map[pattern_id] = []
            pattern_feedback_map[pattern_id].append(feedback)

        # Identify emerging patterns
        emerging_patterns = []
        for pattern_id, feedback_items in pattern_feedback_map.items():
            frequency = len(feedback_items)

            # Apply min_frequency filter
            if frequency < min_frequency:
                continue

            # Sort by timestamp
            feedback_items.sort(key=lambda x: x.created_at)

            first_seen = feedback_items[0].created_at
            last_seen = feedback_items[-1].created_at

            # Calculate success rate
            success_count = sum(1 for f in feedback_items if f.success)
            success_rate = success_count / len(feedback_items)

            # Calculate growth rate (simple linear approximation)
            time_span_hours = (last_seen - first_seen).total_seconds() / 3600
            if time_span_hours > 0:
                growth_rate = frequency / time_span_hours
            else:
                growth_rate = 0.0

            # Calculate confidence
            sample_factor = min(frequency / 10.0, 1.0)
            confidence = success_rate * sample_factor

            emerging_patterns.append(
                {
                    "pattern_id": pattern_id,
                    "pattern_name": feedback_items[0].pattern_name
                    or f"pattern_{pattern_id[:8]}",
                    "pattern_type": feedback_items[0].context.get(
                        "pattern_type", "unknown"
                    ),
                    "frequency": frequency,
                    "first_seen_at": first_seen,
                    "last_seen_at": last_seen,
                    "success_rate": success_rate,
                    "growth_rate": growth_rate,
                    "confidence": confidence,
                }
            )

        # Sort by growth_rate descending
        emerging_patterns.sort(key=lambda x: x["growth_rate"], reverse=True)

        self.logger.info(f"Detected {len(emerging_patterns)} emerging patterns")

        return {
            "emerging_patterns": emerging_patterns,
            "total_emerging": len(emerging_patterns),
            "time_window_hours": time_window_hours,
            "filter_criteria": {
                "min_frequency": min_frequency,
                "time_window_hours": time_window_hours,
            },
        }

    async def get_pattern_feedback_history(
        self,
        pattern_id: str,
    ) -> Dict[str, Any]:
        """
        Get feedback history for a specific pattern.

        Args:
            pattern_id: Pattern identifier

        Returns:
            Dictionary with feedback history and summary statistics
        """
        self.logger.info(f"Retrieving feedback history | pattern_id={pattern_id}")

        # Get all feedback for this pattern
        all_feedback = self.orchestrator.feedback_store
        pattern_feedback = [f for f in all_feedback if str(f.pattern_id) == pattern_id]

        if not pattern_feedback:
            self.logger.warning(f"No feedback found for pattern_id={pattern_id}")
            return {
                "pattern_id": pattern_id,
                "pattern_name": "Unknown Pattern",
                "feedback_history": [],
                "summary": {
                    "total_feedback": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "success_rate": 0.0,
                    "avg_quality_score": 0.0,
                    "avg_execution_time_ms": 0.0,
                    "date_range": None,
                },
            }

        # Sort by timestamp descending (most recent first)
        pattern_feedback.sort(key=lambda x: x.created_at, reverse=True)

        # Build feedback history items
        feedback_history = []
        for feedback in pattern_feedback:
            feedback_history.append(
                {
                    "feedback_id": feedback.feedback_id,
                    "execution_id": feedback.execution_id,
                    "sentiment": feedback.sentiment.value,
                    "success": feedback.success,
                    "quality_score": feedback.quality_score,
                    "performance_score": feedback.performance_score,
                    "execution_time_ms": feedback.implicit_signals.get(
                        "execution_time_ms"
                    ),
                    "issues": feedback.issues,
                    "context": feedback.context,
                    "created_at": feedback.created_at,
                }
            )

        # Compute summary statistics
        success_count = sum(1 for f in pattern_feedback if f.success)
        failure_count = len(pattern_feedback) - success_count
        success_rate = (
            success_count / len(pattern_feedback) if pattern_feedback else 0.0
        )

        quality_scores = [
            f.quality_score for f in pattern_feedback if f.quality_score is not None
        ]
        avg_quality_score = mean(quality_scores) if quality_scores else 0.0

        execution_times = [
            f.implicit_signals.get("execution_time_ms", 0)
            for f in pattern_feedback
            if f.implicit_signals.get("execution_time_ms") is not None
        ]
        avg_execution_time_ms = mean(execution_times) if execution_times else 0.0

        date_range = {
            "earliest": min(f.created_at for f in pattern_feedback),
            "latest": max(f.created_at for f in pattern_feedback),
        }

        summary = {
            "total_feedback": len(pattern_feedback),
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_rate,
            "avg_quality_score": avg_quality_score,
            "avg_execution_time_ms": avg_execution_time_ms,
            "date_range": date_range,
        }

        pattern_name = pattern_feedback[0].pattern_name or f"pattern_{pattern_id[:8]}"

        self.logger.info(
            f"Retrieved {len(feedback_history)} feedback items for pattern {pattern_id}"
        )

        return {
            "pattern_id": pattern_id,
            "pattern_name": pattern_name,
            "feedback_history": feedback_history,
            "summary": summary,
        }

    async def record_quality_metric(
        self,
        pattern_id: UUID,
        quality_score: float,
        confidence: float,
        metadata: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record a quality metric for a pattern.

        This method provides a public API for recording quality metrics,
        which are used by the Pattern Dashboard for trend analysis.

        Args:
            pattern_id: UUID of the pattern
            quality_score: Quality score (0.0-1.0)
            confidence: Confidence in the measurement (0.0-1.0)
            metadata: Optional metadata about the measurement
            version: Optional pattern version string

        Returns:
            Dictionary with recorded metric details

        Raises:
            ValueError: If quality_score or confidence out of range
            Exception: If database operation fails
        """
        # Validate inputs
        if not (0.0 <= quality_score <= 1.0):
            raise ValueError(
                f"quality_score must be between 0.0 and 1.0, got {quality_score}"
            )

        if not (0.0 <= confidence <= 1.0):
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {confidence}"
            )

        if not self.db_pool:
            raise RuntimeError(
                "Database pool not configured for quality metric recording"
            )

        self.logger.info(
            f"Recording quality metric | pattern_id={pattern_id} | "
            f"quality={quality_score:.3f} | confidence={confidence:.3f}"
        )

        # Insert or update quality metric in database (UPSERT)
        query = """
            INSERT INTO pattern_quality_metrics (
                id, pattern_id, quality_score, confidence,
                measurement_timestamp, version, metadata
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7::jsonb
            )
            ON CONFLICT (pattern_id)
            DO UPDATE SET
                quality_score = EXCLUDED.quality_score,
                confidence = EXCLUDED.confidence,
                measurement_timestamp = EXCLUDED.measurement_timestamp,
                version = EXCLUDED.version,
                metadata = EXCLUDED.metadata
            RETURNING id, measurement_timestamp
        """

        metric_id = uuid4()
        measurement_timestamp = datetime.now(timezone.utc)
        metadata_json = json.dumps(metadata or {})

        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.fetchrow(
                    query,
                    metric_id,
                    pattern_id,
                    quality_score,
                    confidence,
                    measurement_timestamp,
                    version,
                    metadata_json,
                )

            self.logger.info(
                f"Quality metric recorded successfully | "
                f"metric_id={result['id']} | pattern_id={pattern_id}"
            )

            return {
                "metric_id": str(result["id"]),
                "pattern_id": str(pattern_id),
                "quality_score": quality_score,
                "confidence": confidence,
                "measurement_timestamp": result["measurement_timestamp"].isoformat(),
                "version": version,
                "metadata": metadata,
            }

        except Exception as e:
            self.logger.error(
                f"Failed to record quality metric for pattern {pattern_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_usage_stats(
        self,
        pattern_id: Optional[UUID] = None,
        time_range: str = "7d",
        group_by: str = "day",
    ) -> Dict[str, Any]:
        """
        Get usage statistics for patterns.

        Args:
            pattern_id: Filter to specific pattern (optional)
            time_range: Time window (1d, 7d, 30d, 90d)
            group_by: Aggregation granularity (hour, day, week)

        Returns:
            Usage counts per time period
        """
        self.logger.info(
            f"Computing usage stats | pattern_id={pattern_id} | time_range={time_range} | group_by={group_by}"
        )

        # Parse time range
        days = self._parse_time_range(time_range)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Get all feedback from orchestrator
        all_feedback = self.orchestrator.feedback_store

        # Filter by time range
        filtered_feedback = [f for f in all_feedback if f.created_at >= start_date]

        # Filter by pattern_id if specified
        if pattern_id:
            filtered_feedback = [
                f for f in filtered_feedback if f.pattern_id == pattern_id
            ]

        # Group by pattern_id
        pattern_feedback_map: Dict[UUID, List[ModelPatternFeedback]] = {}
        for feedback in filtered_feedback:
            pid = feedback.pattern_id
            if pid not in pattern_feedback_map:
                pattern_feedback_map[pid] = []
            pattern_feedback_map[pid].append(feedback)

        # Process each pattern
        patterns = []
        for pid, feedback_items in pattern_feedback_map.items():
            # Group by time bucket
            time_buckets = self._group_by_time(feedback_items, group_by)

            # Build usage data points
            usage_data = []
            for timestamp, count in sorted(time_buckets.items()):
                usage_data.append(
                    {
                        "timestamp": timestamp.isoformat(),
                        "count": count,
                    }
                )

            patterns.append(
                {
                    "pattern_id": str(pid),
                    "pattern_name": feedback_items[0].pattern_name
                    or f"pattern_{str(pid)[:8]}",
                    "usage_data": usage_data,
                    "total_usage": len(feedback_items),
                }
            )

        self.logger.info(
            f"Computed usage stats | patterns={len(patterns)} | time_range={time_range}"
        )

        return {
            "patterns": patterns,
            "time_range": time_range,
            "granularity": group_by,
            "total_patterns": len(patterns),
        }

    def _parse_time_range(self, time_range: str) -> int:
        """Parse time range string to days."""
        mapping = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
        return mapping.get(time_range, 7)

    def _group_by_time(
        self,
        feedback_items: List[ModelPatternFeedback],
        group_by: str,
    ) -> Dict[datetime, int]:
        """
        Group feedback items by time bucket.

        Args:
            feedback_items: List of feedback items
            group_by: Grouping granularity (hour, day, week)

        Returns:
            Dictionary mapping timestamp to count
        """
        from collections import defaultdict

        time_buckets = defaultdict(int)

        for feedback in feedback_items:
            # Truncate timestamp based on granularity
            timestamp = feedback.created_at

            if group_by == "hour":
                bucket = timestamp.replace(minute=0, second=0, microsecond=0)
            elif group_by == "day":
                bucket = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            elif group_by == "week":
                # Get start of week (Monday)
                days_since_monday = timestamp.weekday()
                week_start = timestamp - timedelta(days=days_since_monday)
                bucket = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                # Default to day
                bucket = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)

            time_buckets[bucket] += 1

        return dict(time_buckets)

    # ========================================================================
    # New Dashboard Endpoint Methods (7 endpoints)
    # ========================================================================

    async def get_pattern_stats(self) -> Dict[str, Any]:
        """
        Get overall pattern statistics.

        Returns:
            Dictionary with comprehensive pattern statistics
        """
        self.logger.info("Computing overall pattern statistics")

        all_feedback = self.orchestrator.feedback_store

        # Group by pattern
        pattern_feedback_map: Dict[str, List[ModelPatternFeedback]] = {}
        for feedback in all_feedback:
            pattern_id = str(feedback.pattern_id)
            if pattern_id not in pattern_feedback_map:
                pattern_feedback_map[pattern_id] = []
            pattern_feedback_map[pattern_id].append(feedback)

        # Compute statistics
        total_patterns = len(pattern_feedback_map)
        total_feedback = len(all_feedback)

        # Success rate
        success_count = sum(1 for f in all_feedback if f.success)
        avg_success_rate = success_count / total_feedback if total_feedback > 0 else 0.0

        # Quality score
        quality_scores = [
            f.quality_score for f in all_feedback if f.quality_score is not None
        ]
        avg_quality_score = mean(quality_scores) if quality_scores else 0.0

        # Patterns by type
        patterns_by_type: Dict[str, int] = {}
        for feedback_items in pattern_feedback_map.values():
            if feedback_items:
                pattern_type = feedback_items[0].context.get("pattern_type", "unknown")
                patterns_by_type[pattern_type] = (
                    patterns_by_type.get(pattern_type, 0) + 1
                )

        # Recent activity (last 24 hours)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_activity_count = sum(
            1 for f in all_feedback if f.created_at >= cutoff_time
        )

        # High confidence patterns
        high_confidence_patterns = 0
        for feedback_items in pattern_feedback_map.values():
            if len(feedback_items) >= 5:
                success_rate = sum(1 for f in feedback_items if f.success) / len(
                    feedback_items
                )
                sample_factor = min(len(feedback_items) / 30.0, 1.0)
                confidence = success_rate * sample_factor
                if confidence >= 0.8:
                    high_confidence_patterns += 1

        stats = {
            "total_patterns": total_patterns,
            "total_feedback": total_feedback,
            "avg_success_rate": avg_success_rate,
            "avg_quality_score": avg_quality_score,
            "patterns_by_type": patterns_by_type,
            "recent_activity_count": recent_activity_count,
            "high_confidence_patterns": high_confidence_patterns,
        }

        self.logger.info(f"Pattern stats computed | total_patterns={total_patterns}")

        return {
            "stats": stats,
            "generated_at": datetime.now(timezone.utc),
        }

    async def get_discovery_rate(
        self,
        time_range: str = "7d",
        granularity: str = "day",
    ) -> Dict[str, Any]:
        """
        Get pattern discovery rate over time.

        Args:
            time_range: Time range to analyze (1d, 7d, 30d, 90d)
            granularity: Time granularity (hour, day, week)

        Returns:
            Dictionary with time-series discovery data
        """
        self.logger.info(
            f"Computing discovery rate | time_range={time_range} | granularity={granularity}"
        )

        # Parse time range
        days = self._parse_time_range(time_range)
        start_time = datetime.now(timezone.utc) - timedelta(days=days)

        all_feedback = self.orchestrator.feedback_store
        recent_feedback = [f for f in all_feedback if f.created_at >= start_time]

        # Create buckets
        time_buckets: Dict[datetime, Dict[str, int]] = {}
        discovered_patterns: set = set()

        for feedback in recent_feedback:
            # Bucket timestamp
            bucket_ts = feedback.created_at.replace(minute=0, second=0, microsecond=0)
            if granularity == "day":
                bucket_ts = bucket_ts.replace(hour=0)
            elif granularity == "week":
                bucket_ts = bucket_ts - timedelta(days=bucket_ts.weekday())
                bucket_ts = bucket_ts.replace(hour=0)

            pattern_id = str(feedback.pattern_id)
            pattern_type = feedback.context.get("pattern_type", "unknown")

            if bucket_ts not in time_buckets:
                time_buckets[bucket_ts] = {}

            if pattern_id not in discovered_patterns:
                discovered_patterns.add(pattern_id)
                time_buckets[bucket_ts][pattern_type] = (
                    time_buckets[bucket_ts].get(pattern_type, 0) + 1
                )

        # Build data points
        data_points = []
        for timestamp in sorted(time_buckets.keys()):
            pattern_types = time_buckets[timestamp]
            data_points.append(
                {
                    "timestamp": timestamp,
                    "count": sum(pattern_types.values()),
                    "pattern_types": pattern_types,
                }
            )

        return {
            "data_points": data_points,
            "time_range": time_range,
            "granularity": granularity,
            "total_discovered": len(discovered_patterns),
        }

    async def get_quality_trends(self, time_range: str = "30d") -> Dict[str, Any]:
        """
        Get quality trends over time.

        Args:
            time_range: Time range to analyze

        Returns:
            Dictionary with quality trend data
        """
        self.logger.info(f"Computing quality trends | time_range={time_range}")

        # Parse time range
        days = self._parse_time_range(time_range)
        start_time = datetime.now(timezone.utc) - timedelta(days=days)

        all_feedback = self.orchestrator.feedback_store
        recent_feedback = [
            f
            for f in all_feedback
            if f.created_at >= start_time and f.quality_score is not None
        ]

        # Group by day
        daily_quality: Dict[datetime, List[float]] = {}
        for feedback in recent_feedback:
            day = feedback.created_at.replace(hour=0, minute=0, second=0, microsecond=0)
            if day not in daily_quality:
                daily_quality[day] = []
            daily_quality[day].append(feedback.quality_score)

        # Build trend data points
        trends = []
        for day in sorted(daily_quality.keys()):
            quality_scores = daily_quality[day]
            trends.append(
                {
                    "timestamp": day,
                    "avg_quality": mean(quality_scores),
                    "pattern_count": len(quality_scores),
                    "min_quality": min(quality_scores),
                    "max_quality": max(quality_scores),
                }
            )

        # Calculate overall trend
        if len(trends) >= 2:
            first_avg = trends[0]["avg_quality"]
            last_avg = trends[-1]["avg_quality"]
            diff = last_avg - first_avg
            velocity = diff / len(trends)

            if abs(diff) < 0.05:
                overall_trend = "stable"
            elif diff > 0:
                overall_trend = "increasing"
            else:
                overall_trend = "decreasing"
        else:
            overall_trend = "insufficient_data"
            velocity = 0.0

        return {
            "trends": trends,
            "time_range": time_range,
            "overall_trend": overall_trend,
            "trend_velocity": velocity,
        }

    async def get_top_performing_new(
        self,
        criteria: str = "performance_score",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Get top performing patterns with enhanced metrics.

        Args:
            criteria: Ranking criteria (success_rate, usage, quality, performance_score)
            limit: Number of patterns to return

        Returns:
            Dictionary with top performing patterns
        """
        self.logger.info(
            f"Getting top performing patterns | criteria={criteria} | limit={limit}"
        )

        all_feedback = self.orchestrator.feedback_store

        # Group by pattern
        pattern_stats: Dict[str, Dict[str, Any]] = {}
        for feedback in all_feedback:
            pattern_id = str(feedback.pattern_id)
            if pattern_id not in pattern_stats:
                pattern_stats[pattern_id] = {
                    "pattern_id": pattern_id,
                    "pattern_name": feedback.pattern_name
                    or f"pattern_{pattern_id[:8]}",
                    "pattern_type": feedback.context.get("pattern_type", "unknown"),
                    "feedback_items": [],
                }
            pattern_stats[pattern_id]["feedback_items"].append(feedback)

        # Compute metrics for each pattern
        patterns = []
        for pattern_id, data in pattern_stats.items():
            feedback_items = data["feedback_items"]
            success_count = sum(1 for f in feedback_items if f.success)
            success_rate = success_count / len(feedback_items)
            usage_count = len(feedback_items)

            quality_scores = [
                f.quality_score for f in feedback_items if f.quality_score is not None
            ]
            avg_quality = mean(quality_scores) if quality_scores else 0.0

            # Performance score (weighted combination)
            performance_score = (
                (success_rate * 0.5)
                + (avg_quality * 0.3)
                + (min(usage_count / 100, 1.0) * 0.2)
            )

            patterns.append(
                {
                    "pattern_id": pattern_id,
                    "pattern_name": data["pattern_name"],
                    "pattern_type": data["pattern_type"],
                    "success_rate": success_rate,
                    "usage_count": usage_count,
                    "avg_quality": avg_quality,
                    "performance_score": performance_score,
                }
            )

        # Sort by criteria
        if criteria == "success_rate":
            patterns.sort(key=lambda x: x["success_rate"], reverse=True)
        elif criteria == "usage":
            patterns.sort(key=lambda x: x["usage_count"], reverse=True)
        elif criteria == "quality":
            patterns.sort(key=lambda x: x["avg_quality"], reverse=True)
        else:  # performance_score
            patterns.sort(key=lambda x: x["performance_score"], reverse=True)

        # Limit and add rank
        top_patterns = patterns[:limit]
        for rank, pattern in enumerate(top_patterns, start=1):
            pattern["rank"] = rank

        return {
            "patterns": top_patterns,
            "total_count": len(pattern_stats),
            "criteria": criteria,
        }

    async def get_pattern_relationships(
        self,
        min_co_occurrence: int = 2,
    ) -> Dict[str, Any]:
        """
        Get pattern relationship network data.

        Args:
            min_co_occurrence: Minimum co-occurrence count for relationship

        Returns:
            Dictionary with nodes and relationships for network graph
        """
        self.logger.info(
            f"Computing pattern relationships | min_co_occurrence={min_co_occurrence}"
        )

        all_feedback = self.orchestrator.feedback_store

        # Group feedback by execution_id to find co-occurrences
        execution_patterns: Dict[str, set] = {}
        for feedback in all_feedback:
            if feedback.execution_id:
                if feedback.execution_id not in execution_patterns:
                    execution_patterns[feedback.execution_id] = set()
                execution_patterns[feedback.execution_id].add(str(feedback.pattern_id))

        # Count pattern co-occurrences
        co_occurrences: Dict[tuple, int] = {}
        for pattern_set in execution_patterns.values():
            patterns_list = list(pattern_set)
            for i, pattern1 in enumerate(patterns_list):
                for pattern2 in patterns_list[i + 1 :]:
                    pair = tuple(sorted([pattern1, pattern2]))
                    co_occurrences[pair] = co_occurrences.get(pair, 0) + 1

        # Build pattern stats for nodes
        pattern_stats: Dict[str, Dict[str, Any]] = {}
        for feedback in all_feedback:
            pattern_id = str(feedback.pattern_id)
            if pattern_id not in pattern_stats:
                pattern_stats[pattern_id] = {
                    "pattern_id": pattern_id,
                    "pattern_name": feedback.pattern_name
                    or f"pattern_{pattern_id[:8]}",
                    "pattern_type": feedback.context.get("pattern_type", "unknown"),
                    "usage_count": 0,
                    "success_count": 0,
                    "connection_count": 0,
                }
            pattern_stats[pattern_id]["usage_count"] += 1
            if feedback.success:
                pattern_stats[pattern_id]["success_count"] += 1

        # Build relationships
        relationships = []
        for (source_id, target_id), count in co_occurrences.items():
            if count >= min_co_occurrence:
                # Calculate relationship strength
                source_usage = pattern_stats.get(source_id, {}).get("usage_count", 1)
                target_usage = pattern_stats.get(target_id, {}).get("usage_count", 1)
                strength = count / max(source_usage, target_usage)

                relationships.append(
                    {
                        "source_pattern_id": source_id,
                        "target_pattern_id": target_id,
                        "relationship_type": "used_with",
                        "strength": min(strength, 1.0),
                        "co_occurrence_count": count,
                    }
                )

                # Update connection counts
                if source_id in pattern_stats:
                    pattern_stats[source_id]["connection_count"] += 1
                if target_id in pattern_stats:
                    pattern_stats[target_id]["connection_count"] += 1

        # Build nodes with centrality
        nodes = []
        total_connections = sum(p["connection_count"] for p in pattern_stats.values())
        for pattern_id, stats in pattern_stats.items():
            centrality = (
                stats["connection_count"] / total_connections
                if total_connections > 0
                else 0.0
            )
            success_rate = (
                stats["success_count"] / stats["usage_count"]
                if stats["usage_count"] > 0
                else 0.0
            )

            nodes.append(
                {
                    "pattern_id": pattern_id,
                    "pattern_name": stats["pattern_name"],
                    "pattern_type": stats["pattern_type"],
                    "usage_count": stats["usage_count"],
                    "success_rate": success_rate,
                    "centrality": centrality,
                }
            )

        return {
            "nodes": nodes,
            "relationships": relationships,
            "total_nodes": len(nodes),
            "total_edges": len(relationships),
        }

    async def search_patterns(
        self,
        query: str,
        search_type: str = "full_text",
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Search patterns using full-text or vector search.

        Args:
            query: Search query
            search_type: Search type (full_text, vector, hybrid)
            limit: Maximum results

        Returns:
            Dictionary with search results
        """
        self.logger.info(
            f"Searching patterns | query='{query}' | search_type={search_type}"
        )

        all_feedback = self.orchestrator.feedback_store

        # Group by pattern
        pattern_data: Dict[str, Dict[str, Any]] = {}
        for feedback in all_feedback:
            pattern_id = str(feedback.pattern_id)
            if pattern_id not in pattern_data:
                pattern_data[pattern_id] = {
                    "pattern_id": pattern_id,
                    "pattern_name": feedback.pattern_name
                    or f"pattern_{pattern_id[:8]}",
                    "pattern_type": feedback.context.get("pattern_type", "unknown"),
                    "description": feedback.context.get("description", ""),
                    "tags": feedback.context.get("tags", []),
                    "usage_count": 0,
                    "success_count": 0,
                }
            pattern_data[pattern_id]["usage_count"] += 1
            if feedback.success:
                pattern_data[pattern_id]["success_count"] += 1

        # Simple text-based search (case-insensitive)
        query_lower = query.lower()
        results = []
        for pattern_id, data in pattern_data.items():
            # Calculate relevance score
            relevance_score = 0.0

            # Check pattern name
            if query_lower in data["pattern_name"].lower():
                relevance_score += 0.5

            # Check pattern type
            if query_lower in data["pattern_type"].lower():
                relevance_score += 0.3

            # Check description
            if query_lower in data["description"].lower():
                relevance_score += 0.2

            # Check tags
            for tag in data["tags"]:
                if query_lower in tag.lower():
                    relevance_score += 0.1

            # If any match, add to results
            if relevance_score > 0:
                success_rate = (
                    data["success_count"] / data["usage_count"]
                    if data["usage_count"] > 0
                    else 0.0
                )
                results.append(
                    {
                        "pattern_id": pattern_id,
                        "pattern_name": data["pattern_name"],
                        "pattern_type": data["pattern_type"],
                        "description": data["description"],
                        "relevance_score": min(relevance_score, 1.0),
                        "success_rate": success_rate,
                        "usage_count": data["usage_count"],
                        "tags": data["tags"],
                    }
                )

        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        results = results[:limit]

        return {
            "results": results,
            "total_results": len(results),
            "query": query,
            "search_type": search_type,
        }

    async def get_infrastructure_health(self) -> Dict[str, Any]:
        """
        Get infrastructure health status.

        Returns:
            Dictionary with health status of all components
        """
        self.logger.info("Checking infrastructure health")

        components = []
        now = datetime.now(timezone.utc)

        # Pattern analytics service (self)
        components.append(
            {
                "name": "pattern_analytics_service",
                "status": "healthy",
                "response_time_ms": 1.0,
                "last_check": now,
                "details": {
                    "feedback_store_size": len(self.orchestrator.feedback_store),
                },
            }
        )

        # Feedback orchestrator
        try:
            feedback_count = len(self.orchestrator.feedback_store)
            components.append(
                {
                    "name": "feedback_orchestrator",
                    "status": "healthy",
                    "response_time_ms": 0.5,
                    "last_check": now,
                    "details": {
                        "total_feedback": feedback_count,
                    },
                }
            )
        except Exception as e:
            components.append(
                {
                    "name": "feedback_orchestrator",
                    "status": "unhealthy",
                    "response_time_ms": None,
                    "last_check": now,
                    "details": {
                        "error": str(e),
                    },
                }
            )

        # Determine overall status
        statuses = [c["status"] for c in components]
        if all(s == "healthy" for s in statuses):
            overall_status = "healthy"
        elif any(s == "unhealthy" for s in statuses):
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        # Mock uptime and metrics (would come from real monitoring in production)
        uptime_seconds = 3600.0  # 1 hour
        total_requests = len(self.orchestrator.feedback_store)
        avg_response_time_ms = 50.0

        return {
            "overall_status": overall_status,
            "components": components,
            "uptime_seconds": uptime_seconds,
            "total_requests": total_requests,
            "avg_response_time_ms": avg_response_time_ms,
            "checked_at": now,
        }

    async def get_quality_trend_with_snapshots(
        self,
        project_id: str,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Get quality trend with time-series snapshots from database.

        Queries pattern_quality_metrics table and aggregates data by hourly intervals.

        Args:
            project_id: Project identifier (stored in pattern metadata)
            hours: Time window in hours (default: 24)

        Returns:
            Dictionary containing:
            - trend: "improving" | "declining" | "stable" | "insufficient_data"
            - avg_quality: Average quality score across time window
            - snapshots_count: Number of snapshots
            - snapshots: Array of time-series data points with:
                - timestamp: ISO timestamp
                - overall_quality: Average quality score at that time
                - file_count: Number of unique patterns measured

        Raises:
            RuntimeError: If database pool not configured
            Exception: If database query fails
        """
        if not self.db_pool:
            raise RuntimeError("Database pool not configured for quality trend queries")

        self.logger.info(
            f"Querying quality trend with snapshots | "
            f"project_id={project_id} | hours={hours}"
        )

        # Calculate time window
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        try:
            async with self.db_pool.acquire() as conn:
                # Query pattern_quality_metrics with time-series aggregation
                # Group by 1-hour intervals for granular snapshots
                query = """
                    WITH time_series AS (
                        SELECT
                            date_trunc('hour', pqm.measurement_timestamp) as snapshot_time,
                            AVG(pqm.quality_score) as overall_quality,
                            COUNT(DISTINCT pqm.pattern_id) as file_count
                        FROM pattern_quality_metrics pqm
                        INNER JOIN pattern_lineage_nodes pln ON pqm.pattern_id = pln.id
                        WHERE pqm.measurement_timestamp >= $1
                            AND pqm.measurement_timestamp <= $2
                            AND (pln.metadata->>'project_id' = $3 OR $3 = 'default')
                        GROUP BY snapshot_time
                        ORDER BY snapshot_time ASC
                    ),
                    trend_calc AS (
                        SELECT
                            AVG(overall_quality) as avg_quality,
                            COUNT(*) as snapshot_count,
                            -- Linear regression for trend detection
                            CASE
                                WHEN COUNT(*) >= 2 THEN
                                    regr_slope(overall_quality, EXTRACT(EPOCH FROM snapshot_time))
                                ELSE 0
                            END as slope
                        FROM time_series
                    )
                    SELECT
                        ts.snapshot_time,
                        ts.overall_quality,
                        ts.file_count,
                        tc.avg_quality,
                        tc.snapshot_count,
                        tc.slope
                    FROM time_series ts
                    CROSS JOIN trend_calc tc
                    ORDER BY ts.snapshot_time ASC
                """

                rows = await conn.fetch(query, start_time, end_time, project_id)

                # Process results
                if not rows:
                    self.logger.warning(
                        f"No quality metrics found | "
                        f"project_id={project_id} | time_window={hours}h"
                    )
                    return {
                        "success": True,
                        "project_id": project_id,
                        "trend": "insufficient_data",
                        "avg_quality": 0.0,
                        "snapshots_count": 0,
                        "snapshots": [],
                    }

                # Extract trend metrics (same for all rows due to CROSS JOIN)
                first_row = rows[0]
                avg_quality = (
                    float(first_row["avg_quality"]) if first_row["avg_quality"] else 0.0
                )
                snapshots_count = int(first_row["snapshot_count"])
                slope = float(first_row["slope"]) if first_row["slope"] else 0.0

                # Determine trend based on slope
                # Threshold: ±1e-6 (small slope = stable)
                if slope > 1e-6:
                    trend = "improving"
                elif slope < -1e-6:
                    trend = "declining"
                else:
                    trend = "stable"

                # Build snapshots array
                snapshots = []
                for row in rows:
                    snapshots.append(
                        {
                            "timestamp": row["snapshot_time"].isoformat(),
                            "overall_quality": float(row["overall_quality"]),
                            "file_count": int(row["file_count"]),
                        }
                    )

                self.logger.info(
                    f"Quality trend calculated | "
                    f"project_id={project_id} | trend={trend} | "
                    f"snapshots={snapshots_count} | avg_quality={avg_quality:.3f}"
                )

                return {
                    "success": True,
                    "project_id": project_id,
                    "trend": trend,
                    "avg_quality": round(avg_quality, 3),
                    "snapshots_count": snapshots_count,
                    "snapshots": snapshots,
                }

        except Exception as e:
            self.logger.error(
                f"Failed to get quality trend with snapshots | "
                f"project_id={project_id}: {e}",
                exc_info=True,
            )
            raise
