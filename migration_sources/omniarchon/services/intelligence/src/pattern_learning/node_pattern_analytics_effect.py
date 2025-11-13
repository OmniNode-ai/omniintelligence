"""
ONEX Effect Node: Pattern Analytics
Purpose: Handle analytics computation and aggregation for patterns
Node Type: Effect (External I/O, analytics database operations)

File: node_pattern_analytics_effect.py
Class: NodePatternAnalyticsEffect
Pattern: ONEX 4-Node Architecture - Effect

Track: Track 3-1.2 - PostgreSQL Storage Layer
AI Generated: 70% (Codestral-inspired base, human refinement)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logging.warning("asyncpg not available - pattern analytics will be disabled")


logger = logging.getLogger(__name__)


# ============================================================================
# ONEX Contract Models
# ============================================================================


class ModelResult:
    """Standard result format for ONEX operations"""

    def __init__(
        self,
        success: bool,
        data: Any = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.data = data
        self.error = error
        self.metadata = metadata or {}


class ModelContractEffect:
    """Contract for Effect nodes with analytics specifications"""

    def __init__(
        self,
        operation: str,
        pattern_id: Optional[UUID] = None,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        aggregate_by: Optional[str] = None,
        correlation_id: Optional[UUID] = None,
    ):
        self.operation = operation
        self.pattern_id = pattern_id
        self.period_start = period_start
        self.period_end = period_end
        self.aggregate_by = aggregate_by or "day"
        self.correlation_id = correlation_id or uuid4()


# ============================================================================
# ONEX Effect Node: Pattern Analytics
# ============================================================================


class NodePatternAnalyticsEffect:
    """
    ONEX Effect Node for pattern analytics operations.

    Implements:
    - Suffix naming convention: Node<Name>Effect
    - File pattern: node_*_effect.py
    - Method signature: async def execute_effect(self, contract: ModelContractEffect) -> ModelResult
    - Pure I/O operations with analytics queries
    - Read-heavy with occasional writes for computed analytics

    Responsibilities:
    - Compute pattern analytics for time periods
    - Get usage trends and statistics
    - Analyze pattern effectiveness
    - Generate quality improvement reports
    - Calculate success rates and metrics

    Database Tables:
    - pattern_analytics: Aggregated analytics storage
    - pattern_usage_events: Source data for analytics
    - v_pattern_quality_trends: Trend analysis view
    """

    def __init__(self, db_pool: "asyncpg.Pool"):
        """
        Initialize pattern analytics Effect node.

        Args:
            db_pool: AsyncPG connection pool for database operations
        """
        self.pool = db_pool
        self.logger = logging.getLogger("NodePatternAnalyticsEffect")

    async def execute_effect(self, contract: ModelContractEffect) -> ModelResult:
        """
        Execute pattern analytics operation.

        Args:
            contract: ModelContractEffect with analytics parameters

        Returns:
            ModelResult with analytics data

        Operations:
            - compute_analytics: Compute analytics for period
            - get_usage_trends: Get usage trends over time
            - get_quality_trends: Get quality improvement trends
            - get_effectiveness: Get pattern effectiveness metrics
            - get_global_stats: Get global pattern statistics
        """
        if not ASYNCPG_AVAILABLE:
            return ModelResult(
                success=False,
                error="AsyncPG not available",
                metadata={"correlation_id": str(contract.correlation_id)},
            )

        start_time = datetime.now(timezone.utc)

        try:
            async with self.pool.acquire() as conn:
                self.logger.info(
                    f"Executing pattern analytics operation: {contract.operation}",
                    extra={"correlation_id": str(contract.correlation_id)},
                )

                if contract.operation == "compute_analytics":
                    result_data = await self._compute_analytics(conn, contract)
                elif contract.operation == "get_usage_trends":
                    result_data = await self._get_usage_trends(conn, contract)
                elif contract.operation == "get_quality_trends":
                    result_data = await self._get_quality_trends(conn, contract)
                elif contract.operation == "get_effectiveness":
                    result_data = await self._get_effectiveness(conn, contract)
                elif contract.operation == "get_global_stats":
                    result_data = await self._get_global_stats(conn, contract)
                else:
                    return ModelResult(
                        success=False,
                        error=f"Unsupported operation: {contract.operation}",
                        metadata={"correlation_id": str(contract.correlation_id)},
                    )

            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            return ModelResult(
                success=True,
                data=result_data,
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": contract.operation,
                    "duration_ms": duration_ms,
                },
            )

        except Exception as e:
            self.logger.error(
                f"Pattern analytics operation failed: {e}",
                exc_info=True,
                extra={"correlation_id": str(contract.correlation_id)},
            )
            return ModelResult(
                success=False,
                error=str(e),
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": contract.operation,
                },
            )

    async def _compute_analytics(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> Dict[str, Any]:
        """
        Compute and store analytics for a time period.

        Args:
            conn: AsyncPG connection
            contract: Contract with period_start, period_end, pattern_id

        Returns:
            Dict with computed analytics
        """
        period_start = contract.period_start or (
            datetime.now(timezone.utc) - timedelta(days=30)
        )
        period_end = contract.period_end or datetime.now(timezone.utc)
        pattern_id = contract.pattern_id  # None for global analytics

        # Call database function to compute analytics
        query = "SELECT compute_pattern_analytics($1, $2, $3)"

        analytics_id = await conn.fetchval(query, period_start, period_end, pattern_id)

        # Retrieve computed analytics
        analytics_query = """
            SELECT
                id, period_start, period_end, pattern_id,
                total_usage_count, success_count, failure_count,
                average_execution_time_ms, average_quality_improvement,
                top_patterns, trend_direction, trend_strength,
                computed_at
            FROM pattern_analytics
            WHERE id = $1
        """

        result = await conn.fetchrow(analytics_query, analytics_id)

        self.logger.info(
            f"Computed analytics for period {period_start} to {period_end}"
        )

        return {
            "analytics_id": str(result["id"]),
            "period_start": result["period_start"].isoformat(),
            "period_end": result["period_end"].isoformat(),
            "pattern_id": str(result["pattern_id"]) if result["pattern_id"] else None,
            "total_usage_count": result["total_usage_count"],
            "success_count": result["success_count"],
            "failure_count": result["failure_count"],
            "average_execution_time_ms": (
                float(result["average_execution_time_ms"])
                if result["average_execution_time_ms"]
                else None
            ),
            "average_quality_improvement": (
                float(result["average_quality_improvement"])
                if result["average_quality_improvement"]
                else None
            ),
            "success_rate": (
                result["success_count"] / result["total_usage_count"]
                if result["total_usage_count"] > 0
                else 0
            ),
            "top_patterns": result["top_patterns"],
            "trend_direction": result["trend_direction"],
            "trend_strength": (
                float(result["trend_strength"]) if result["trend_strength"] else None
            ),
            "computed_at": result["computed_at"].isoformat(),
        }

    async def _get_usage_trends(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> List[Dict[str, Any]]:
        """
        Get usage trends for a pattern over time.

        Args:
            conn: AsyncPG connection
            contract: Contract with pattern_id and period

        Returns:
            List of usage trend data points
        """
        pattern_id = contract.pattern_id
        period_start = contract.period_start or (
            datetime.now(timezone.utc) - timedelta(days=90)
        )
        aggregate_by = contract.aggregate_by  # 'day', 'week', 'month'

        if not pattern_id:
            raise ValueError("pattern_id required for get_usage_trends operation")

        # Determine truncation function
        trunc_func = {"day": "day", "week": "week", "month": "month"}.get(
            aggregate_by, "day"
        )

        query = f"""
            SELECT
                date_trunc('{trunc_func}', used_at) as period,
                COUNT(*) as usage_count,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
                AVG(execution_time_ms) as avg_execution_time_ms,
                AVG(quality_improvement) as avg_quality_improvement
            FROM pattern_usage_events
            WHERE pattern_id = $1
                AND used_at >= $2
            GROUP BY date_trunc('{trunc_func}', used_at)
            ORDER BY period ASC
        """

        results = await conn.fetch(query, pattern_id, period_start)

        return [
            {
                "period": row["period"].isoformat(),
                "usage_count": row["usage_count"],
                "success_count": row["success_count"],
                "success_rate": (
                    row["success_count"] / row["usage_count"]
                    if row["usage_count"] > 0
                    else 0
                ),
                "avg_execution_time_ms": (
                    float(row["avg_execution_time_ms"])
                    if row["avg_execution_time_ms"]
                    else None
                ),
                "avg_quality_improvement": (
                    float(row["avg_quality_improvement"])
                    if row["avg_quality_improvement"]
                    else None
                ),
            }
            for row in results
        ]

    async def _get_quality_trends(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> List[Dict[str, Any]]:
        """
        Get quality improvement trends from materialized view.

        Args:
            conn: AsyncPG connection
            contract: Contract with optional pattern_id

        Returns:
            List of quality trend data points
        """
        pattern_id = contract.pattern_id

        query = """
            SELECT
                id, pattern_name, pattern_type, usage_date,
                usage_count, avg_quality_improvement, success_rate
            FROM v_pattern_quality_trends
            WHERE ($1::uuid IS NULL OR id = $1)
            ORDER BY usage_date DESC
            LIMIT 100
        """

        results = await conn.fetch(query, pattern_id)

        return [dict(row) for row in results]

    async def _get_effectiveness(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> Dict[str, Any]:
        """
        Get pattern effectiveness metrics.

        Args:
            conn: AsyncPG connection
            contract: Contract with pattern_id

        Returns:
            Dict with effectiveness metrics
        """
        pattern_id = contract.pattern_id

        if not pattern_id:
            raise ValueError("pattern_id required for get_effectiveness operation")

        query = """
            WITH usage_stats AS (
                SELECT
                    COUNT(*) as total_usage,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
                    AVG(execution_time_ms) as avg_time,
                    AVG(quality_improvement) as avg_quality_improvement,
                    MIN(used_at) as first_used,
                    MAX(used_at) as last_used
                FROM pattern_usage_events
                WHERE pattern_id = $1
            )
            SELECT
                pt.pattern_name,
                pt.pattern_type,
                pt.confidence_score,
                us.total_usage,
                us.successes,
                us.avg_time,
                us.avg_quality_improvement,
                us.first_used,
                us.last_used,
                CASE
                    WHEN us.total_usage > 0 THEN us.successes::DECIMAL / us.total_usage
                    ELSE 0
                END as success_rate
            FROM pattern_templates pt
            CROSS JOIN usage_stats us
            WHERE pt.id = $1
        """

        result = await conn.fetchrow(query, pattern_id)

        if not result:
            raise ValueError(f"Pattern not found: {pattern_id}")

        return {
            "pattern_id": str(pattern_id),
            "pattern_name": result["pattern_name"],
            "pattern_type": result["pattern_type"],
            "confidence_score": float(result["confidence_score"]),
            "total_usage": result["total_usage"],
            "successes": result["successes"],
            "success_rate": float(result["success_rate"]),
            "avg_execution_time_ms": (
                float(result["avg_time"]) if result["avg_time"] else None
            ),
            "avg_quality_improvement": (
                float(result["avg_quality_improvement"])
                if result["avg_quality_improvement"]
                else None
            ),
            "first_used": (
                result["first_used"].isoformat() if result["first_used"] else None
            ),
            "last_used": (
                result["last_used"].isoformat() if result["last_used"] else None
            ),
        }

    async def _get_global_stats(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> Dict[str, Any]:
        """
        Get global pattern statistics across all patterns.

        Args:
            conn: AsyncPG connection
            contract: Contract (no pattern_id for global stats)

        Returns:
            Dict with global statistics
        """
        query = """
            SELECT
                COUNT(DISTINCT pt.id) as total_patterns,
                COUNT(DISTINCT CASE WHEN pt.is_deprecated = FALSE THEN pt.id END) as active_patterns,
                COUNT(pue.id) as total_usage_events,
                AVG(pt.confidence_score) as avg_confidence,
                AVG(pt.success_rate) as avg_success_rate,
                COUNT(DISTINCT pue.pattern_id) as patterns_used,
                SUM(CASE WHEN pue.success THEN 1 ELSE 0 END)::DECIMAL / NULLIF(COUNT(pue.id), 0) as global_success_rate
            FROM pattern_templates pt
            LEFT JOIN pattern_usage_events pue ON pt.id = pue.pattern_id
        """

        result = await conn.fetchrow(query)

        # Get top patterns
        top_patterns_query = """
            SELECT pattern_name, usage_count, success_rate, confidence_score
            FROM v_top_patterns
            LIMIT 10
        """

        top_patterns = await conn.fetch(top_patterns_query)

        return {
            "total_patterns": result["total_patterns"],
            "active_patterns": result["active_patterns"],
            "total_usage_events": result["total_usage_events"],
            "avg_confidence": (
                float(result["avg_confidence"]) if result["avg_confidence"] else 0
            ),
            "avg_success_rate": (
                float(result["avg_success_rate"]) if result["avg_success_rate"] else 0
            ),
            "patterns_used": result["patterns_used"],
            "global_success_rate": (
                float(result["global_success_rate"])
                if result["global_success_rate"]
                else 0
            ),
            "top_patterns": [dict(row) for row in top_patterns],
        }
