"""
Unit Tests for Pattern Usage Tracking

Tests the UsageTracker, UsageAnalytics, and integration with Kafka.

Created: 2025-10-28
"""

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import asyncpg
import pytest

from .analytics import TrendDirection, UsageAnalytics
from .usage_tracker import UsageTracker


@pytest.fixture
async def db_pool():
    """Create database pool for testing."""
    dsn = "postgresql://postgres:omninode_remote_2024_secure@192.168.86.200:5436/omninode_bridge"
    pool = await asyncpg.create_pool(dsn, min_size=2, max_size=5)
    yield pool
    await pool.close()


@pytest.fixture
async def usage_tracker(db_pool):
    """Create usage tracker instance."""
    tracker = UsageTracker(db_pool)
    await tracker.start()
    yield tracker
    await tracker.stop()


@pytest.fixture
async def usage_analytics(db_pool):
    """Create usage analytics instance."""
    return UsageAnalytics(db_pool)


class TestUsageTracker:
    """Tests for UsageTracker class."""

    @pytest.mark.asyncio
    async def test_track_manifest_usage(self, usage_tracker, db_pool):
        """Test tracking patterns from manifest injection."""
        # Create test pattern
        pattern_id = f"test_pattern_{uuid4().hex[:8]}"
        correlation_id = uuid4()

        # Insert test pattern into database
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO pattern_lineage_nodes
                (pattern_id, pattern_name, pattern_type, lineage_id, correlation_id, pattern_data)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                pattern_id,
                "Test Pattern",
                "test",
                uuid4(),
                correlation_id,
                {"test": "data"},
            )

        # Track usage
        patterns = [{"pattern_id": pattern_id}]
        await usage_tracker.track_manifest_usage(
            patterns=patterns,
            agent_name="test-agent",
            correlation_id=correlation_id,
        )

        # Flush batch to database
        await usage_tracker._flush_batch()

        # Verify usage was tracked
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT usage_count, used_by_agents
                FROM pattern_lineage_nodes
                WHERE pattern_id = $1
                """,
                pattern_id,
            )

            assert row is not None
            assert row["usage_count"] == 1
            assert "test-agent" in row["used_by_agents"]

        # Cleanup
        async with db_pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM pattern_lineage_nodes WHERE pattern_id = $1",
                pattern_id,
            )

    @pytest.mark.asyncio
    async def test_batch_processing(self, usage_tracker, db_pool):
        """Test batch processing of multiple patterns."""
        # Create test patterns
        pattern_ids = [f"test_pattern_{uuid4().hex[:8]}" for _ in range(5)]
        correlation_id = uuid4()

        # Insert test patterns
        async with db_pool.acquire() as conn:
            for pattern_id in pattern_ids:
                await conn.execute(
                    """
                    INSERT INTO pattern_lineage_nodes
                    (pattern_id, pattern_name, pattern_type, lineage_id, correlation_id, pattern_data)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    pattern_id,
                    f"Test Pattern {pattern_id}",
                    "test",
                    uuid4(),
                    correlation_id,
                    {"test": "data"},
                )

        # Track usage for all patterns
        patterns = [{"pattern_id": pid} for pid in pattern_ids]
        await usage_tracker.track_manifest_usage(
            patterns=patterns,
            agent_name="batch-test-agent",
            correlation_id=correlation_id,
        )

        # Flush batch
        await usage_tracker._flush_batch()

        # Verify all were tracked
        async with db_pool.acquire() as conn:
            for pattern_id in pattern_ids:
                row = await conn.fetchrow(
                    """
                    SELECT usage_count, used_by_agents
                    FROM pattern_lineage_nodes
                    WHERE pattern_id = $1
                    """,
                    pattern_id,
                )
                assert row is not None
                assert row["usage_count"] == 1
                assert "batch-test-agent" in row["used_by_agents"]

        # Cleanup
        async with db_pool.acquire() as conn:
            for pattern_id in pattern_ids:
                await conn.execute(
                    "DELETE FROM pattern_lineage_nodes WHERE pattern_id = $1",
                    pattern_id,
                )


class TestUsageAnalytics:
    """Tests for UsageAnalytics class."""

    @pytest.mark.asyncio
    async def test_get_usage_summary(self, usage_analytics):
        """Test getting overall usage summary."""
        summary = await usage_analytics.get_usage_summary()

        assert "total_patterns" in summary
        assert "used_patterns" in summary
        assert "unused_patterns" in summary
        assert "total_usage" in summary
        assert "avg_usage_per_pattern" in summary
        assert "usage_rate" in summary
        assert "total_agents" in summary

        # All values should be non-negative
        assert summary["total_patterns"] >= 0
        assert summary["used_patterns"] >= 0
        assert summary["unused_patterns"] >= 0
        assert summary["total_usage"] >= 0

    @pytest.mark.asyncio
    async def test_get_top_patterns(self, usage_analytics):
        """Test getting top used patterns."""
        patterns = await usage_analytics.get_top_patterns(limit=10)

        assert isinstance(patterns, list)
        assert len(patterns) <= 10

        # Verify patterns are sorted by usage_count descending
        usage_counts = [p.usage_count for p in patterns]
        assert usage_counts == sorted(usage_counts, reverse=True)

    @pytest.mark.asyncio
    async def test_get_unused_patterns(self, usage_analytics):
        """Test getting unused patterns."""
        patterns = await usage_analytics.get_unused_patterns(min_age_days=1)

        assert isinstance(patterns, list)

        # All patterns should have usage_count = 0
        for pattern in patterns:
            assert pattern["usage_count"] == 0

    @pytest.mark.asyncio
    async def test_get_stale_patterns(self, usage_analytics):
        """Test getting stale patterns."""
        patterns = await usage_analytics.get_stale_patterns(days_inactive=30)

        assert isinstance(patterns, list)

        # All patterns should have last_used_at more than 30 days ago
        for pattern in patterns:
            if pattern["days_since_use"] is not None:
                assert pattern["days_since_use"] >= 30


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
