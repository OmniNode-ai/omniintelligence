"""
Pattern Usage Analytics

Calculates usage trends and provides analytics for pattern usage:
- Most/least used patterns
- Usage trends (increasing/decreasing/stable)
- Usage by agent type
- Unused patterns (candidates for removal)

Created: 2025-10-28
"""

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

import asyncpg
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TrendDirection(str, Enum):
    """Trend direction enum."""

    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    INSUFFICIENT_DATA = "insufficient_data"


class PatternUsageStats(BaseModel):
    """Pattern usage statistics."""

    pattern_id: str
    pattern_name: str
    pattern_type: str
    usage_count: int
    last_used_at: Optional[datetime]
    used_by_agents: List[str]
    agent_count: int
    trend_direction: TrendDirection
    trend_percentage: float
    first_used_at: Optional[datetime]
    days_since_last_use: Optional[int]


class UsageAnalytics:
    """
    Analyzes pattern usage and calculates trends.

    Provides methods to query:
    - Top used patterns
    - Least used patterns
    - Unused patterns
    - Usage trends
    - Usage by agent
    """

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize usage analytics.

        Args:
            db_pool: Database connection pool
        """
        self.db_pool = db_pool

    async def get_pattern_usage(
        self,
        pattern_id: str,
        include_trend: bool = True,
    ) -> Optional[PatternUsageStats]:
        """
        Get usage statistics for a specific pattern.

        Args:
            pattern_id: Pattern ID to query
            include_trend: Whether to calculate trend (requires historical data)

        Returns:
            PatternUsageStats or None if pattern not found
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    pattern_id,
                    pattern_name,
                    pattern_type,
                    usage_count,
                    last_used_at,
                    used_by_agents,
                    created_at
                FROM pattern_lineage_nodes
                WHERE pattern_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                pattern_id,
            )

            if not row:
                return None

            # Calculate days since last use
            days_since_last_use = None
            if row["last_used_at"]:
                delta = datetime.now(timezone.utc) - row["last_used_at"]
                days_since_last_use = delta.days

            # Calculate trend
            trend_direction = TrendDirection.INSUFFICIENT_DATA
            trend_percentage = 0.0

            if include_trend and row["usage_count"] > 0:
                trend_direction, trend_percentage = await self._calculate_trend(
                    pattern_id, conn
                )

            return PatternUsageStats(
                pattern_id=row["pattern_id"],
                pattern_name=row["pattern_name"],
                pattern_type=row["pattern_type"],
                usage_count=row["usage_count"] or 0,
                last_used_at=row["last_used_at"],
                used_by_agents=list(row["used_by_agents"] or []),
                agent_count=len(row["used_by_agents"] or []),
                trend_direction=trend_direction,
                trend_percentage=trend_percentage,
                first_used_at=row["created_at"],
                days_since_last_use=days_since_last_use,
            )

    async def get_top_patterns(
        self,
        limit: int = 20,
        pattern_type: Optional[str] = None,
    ) -> List[PatternUsageStats]:
        """
        Get most used patterns.

        Args:
            limit: Number of patterns to return
            pattern_type: Filter by pattern type (optional)

        Returns:
            List of PatternUsageStats sorted by usage_count descending
        """
        query = """
            SELECT DISTINCT ON (pattern_id)
                pattern_id,
                pattern_name,
                pattern_type,
                usage_count,
                last_used_at,
                used_by_agents,
                created_at
            FROM pattern_lineage_nodes
            WHERE usage_count > 0
        """

        params = []
        if pattern_type:
            query += " AND pattern_type = $1"
            params.append(pattern_type)

        query += """
            ORDER BY pattern_id, created_at DESC
        """

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

            # Sort by usage_count in Python (after deduplication)
            sorted_rows = sorted(
                rows,
                key=lambda r: (r["usage_count"] or 0),
                reverse=True,
            )[:limit]

            results = []
            for row in sorted_rows:
                days_since_last_use = None
                if row["last_used_at"]:
                    delta = datetime.now(timezone.utc) - row["last_used_at"]
                    days_since_last_use = delta.days

                results.append(
                    PatternUsageStats(
                        pattern_id=row["pattern_id"],
                        pattern_name=row["pattern_name"],
                        pattern_type=row["pattern_type"],
                        usage_count=row["usage_count"] or 0,
                        last_used_at=row["last_used_at"],
                        used_by_agents=list(row["used_by_agents"] or []),
                        agent_count=len(row["used_by_agents"] or []),
                        trend_direction=TrendDirection.INSUFFICIENT_DATA,
                        trend_percentage=0.0,
                        first_used_at=row["created_at"],
                        days_since_last_use=days_since_last_use,
                    )
                )

            return results

    async def get_unused_patterns(
        self,
        min_age_days: int = 30,
    ) -> List[Dict]:
        """
        Get patterns that have never been used.

        Args:
            min_age_days: Minimum age in days to consider (avoid flagging new patterns)

        Returns:
            List of unused patterns with metadata
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=min_age_days)

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (pattern_id)
                    pattern_id,
                    pattern_name,
                    pattern_type,
                    created_at,
                    usage_count,
                    last_used_at
                FROM pattern_lineage_nodes
                WHERE (usage_count = 0 OR usage_count IS NULL)
                  AND created_at < $1
                ORDER BY pattern_id, created_at DESC
                """,
                cutoff_date,
            )

            results = []
            for row in rows:
                age_days = (datetime.now(timezone.utc) - row["created_at"]).days
                results.append(
                    {
                        "pattern_id": row["pattern_id"],
                        "pattern_name": row["pattern_name"],
                        "pattern_type": row["pattern_type"],
                        "created_at": row["created_at"].isoformat(),
                        "age_days": age_days,
                        "usage_count": row["usage_count"] or 0,
                    }
                )

            return results

    async def get_stale_patterns(
        self,
        days_inactive: int = 90,
    ) -> List[Dict]:
        """
        Get patterns not used in specified number of days.

        Args:
            days_inactive: Days of inactivity threshold

        Returns:
            List of stale patterns
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_inactive)

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (pattern_id)
                    pattern_id,
                    pattern_name,
                    pattern_type,
                    usage_count,
                    last_used_at,
                    created_at
                FROM pattern_lineage_nodes
                WHERE last_used_at IS NOT NULL
                  AND last_used_at < $1
                ORDER BY pattern_id, created_at DESC
                """,
                cutoff_date,
            )

            results = []
            for row in rows:
                days_since_use = (
                    (datetime.now(timezone.utc) - row["last_used_at"]).days
                    if row["last_used_at"]
                    else None
                )

                results.append(
                    {
                        "pattern_id": row["pattern_id"],
                        "pattern_name": row["pattern_name"],
                        "pattern_type": row["pattern_type"],
                        "usage_count": row["usage_count"] or 0,
                        "last_used_at": (
                            row["last_used_at"].isoformat()
                            if row["last_used_at"]
                            else None
                        ),
                        "days_since_use": days_since_use,
                    }
                )

            return results

    async def get_usage_by_agent(
        self,
        agent_name: str,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Get patterns used by a specific agent.

        Args:
            agent_name: Agent name to query
            limit: Maximum number of patterns to return

        Returns:
            List of patterns used by the agent
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (pattern_id)
                    pattern_id,
                    pattern_name,
                    pattern_type,
                    usage_count,
                    last_used_at,
                    used_by_agents
                FROM pattern_lineage_nodes
                WHERE $1 = ANY(used_by_agents)
                ORDER BY pattern_id, created_at DESC
                LIMIT $2
                """,
                agent_name,
                limit,
            )

            results = []
            for row in rows:
                results.append(
                    {
                        "pattern_id": row["pattern_id"],
                        "pattern_name": row["pattern_name"],
                        "pattern_type": row["pattern_type"],
                        "usage_count": row["usage_count"] or 0,
                        "last_used_at": (
                            row["last_used_at"].isoformat()
                            if row["last_used_at"]
                            else None
                        ),
                        "used_by_agents": list(row["used_by_agents"] or []),
                    }
                )

            return results

    async def get_usage_summary(self) -> Dict:
        """
        Get overall usage summary statistics.

        Returns:
            Dictionary with summary statistics
        """
        async with self.db_pool.acquire() as conn:
            # Get overall stats
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(DISTINCT pattern_id) as total_patterns,
                    COUNT(DISTINCT pattern_id) FILTER (
                        WHERE usage_count > 0
                    ) as used_patterns,
                    COUNT(DISTINCT pattern_id) FILTER (
                        WHERE usage_count = 0 OR usage_count IS NULL
                    ) as unused_patterns,
                    SUM(usage_count) as total_usage,
                    AVG(usage_count) as avg_usage_per_pattern
                FROM (
                    SELECT DISTINCT ON (pattern_id)
                        pattern_id,
                        usage_count
                    FROM pattern_lineage_nodes
                    ORDER BY pattern_id, created_at DESC
                ) sub
                """
            )

            # Get agent count
            agent_stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(DISTINCT agent) as total_agents
                FROM (
                    SELECT DISTINCT unnest(used_by_agents) as agent
                    FROM pattern_lineage_nodes
                    WHERE used_by_agents IS NOT NULL
                ) sub
                """
            )

            return {
                "total_patterns": stats["total_patterns"],
                "used_patterns": stats["used_patterns"],
                "unused_patterns": stats["unused_patterns"],
                "total_usage": stats["total_usage"] or 0,
                "avg_usage_per_pattern": float(stats["avg_usage_per_pattern"] or 0),
                "usage_rate": (
                    (stats["used_patterns"] / stats["total_patterns"] * 100)
                    if stats["total_patterns"] > 0
                    else 0
                ),
                "total_agents": agent_stats["total_agents"] or 0,
            }

    async def _calculate_trend(
        self,
        pattern_id: str,
        conn: asyncpg.Connection,
    ) -> tuple[TrendDirection, float]:
        """
        Calculate usage trend for pattern.

        Compares usage in last 7 days vs previous 7 days.

        Args:
            pattern_id: Pattern ID
            conn: Database connection

        Returns:
            Tuple of (trend_direction, trend_percentage)
        """
        # For now, return insufficient data
        # TODO: Implement historical usage tracking in separate table
        # to enable trend calculation

        # This would require:
        # 1. pattern_usage_history table with daily snapshots
        # 2. Background job to snapshot usage_count daily
        # 3. Query to compare last 7 days vs previous 7 days

        return TrendDirection.INSUFFICIENT_DATA, 0.0
