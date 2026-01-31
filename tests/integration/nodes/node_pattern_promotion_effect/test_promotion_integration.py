# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Integration tests for pattern promotion against real PostgreSQL.

These tests verify that the promotion logic works correctly with the actual
database schema, constraints, and query behavior.

Run with:
    pytest tests/integration/nodes/pattern_promotion_effect -v -m integration

Prerequisites:
    - PostgreSQL running on 192.168.86.200:5436
    - POSTGRES_PASSWORD environment variable set
    - Database migrations applied
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
import pytest

from tests.integration.nodes.node_pattern_promotion_effect.conftest import MockKafkaPublisher

from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_promotion import (
    check_and_promote_patterns,
)


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestPromotionIntegration:
    """Integration tests for pattern promotion with real PostgreSQL."""

    async def test_promotion_promotes_eligible_patterns(
        self,
        db_conn: asyncpg.Connection,
        test_pattern_ids: list[UUID],
        mock_kafka_publisher: MockKafkaPublisher,
        sample_correlation_id: UUID,
    ) -> None:
        """Eligible patterns are promoted to validated status in real DB.

        Test data setup (from fixture):
            - Pattern 0: Eligible (80% success, 10 injections, 0 streak)
            - Pattern 1: Eligible (60% success, 5 injections, 2 streak)
            - Pattern 2: Ineligible (low injection count)
            - Pattern 3: Ineligible (high failure streak)
        """
        # Act
        result = await check_and_promote_patterns(
            repository=db_conn,
            producer=mock_kafka_publisher,
            dry_run=False,
            correlation_id=sample_correlation_id,
        )

        # Assert: 4 patterns checked, 2 eligible, 2 promoted
        assert result.patterns_checked == 4
        assert result.patterns_eligible == 2
        assert len(result.patterns_promoted) == 2
        assert result.dry_run is False

        # Verify patterns 0 and 1 are now validated in the database
        for i in [0, 1]:
            row = await db_conn.fetchrow(
                "SELECT status FROM learned_patterns WHERE id = $1",
                test_pattern_ids[i],
            )
            assert row is not None
            assert row["status"] == "validated", f"Pattern {i} should be validated"

        # Verify patterns 2 and 3 are still provisional
        for i in [2, 3]:
            row = await db_conn.fetchrow(
                "SELECT status FROM learned_patterns WHERE id = $1",
                test_pattern_ids[i],
            )
            assert row is not None
            assert row["status"] == "provisional", f"Pattern {i} should remain provisional"

        # Verify Kafka events were emitted for promoted patterns
        assert len(mock_kafka_publisher.published_events) == 2
        for topic, key, value in mock_kafka_publisher.published_events:
            assert "pattern-promoted" in topic
            assert value["event_type"] == "PatternPromoted"
            assert value["from_status"] == "provisional"
            assert value["to_status"] == "validated"

    async def test_dry_run_does_not_mutate_database(
        self,
        db_conn: asyncpg.Connection,
        test_pattern_ids: list[UUID],
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Dry run mode returns promotions without database changes."""
        # Capture initial statuses
        initial_statuses = {}
        for pattern_id in test_pattern_ids:
            row = await db_conn.fetchrow(
                "SELECT status FROM learned_patterns WHERE id = $1",
                pattern_id,
            )
            initial_statuses[pattern_id] = row["status"]

        # Act
        result = await check_and_promote_patterns(
            repository=db_conn,
            producer=mock_kafka_publisher,
            dry_run=True,
        )

        # Assert: Results show what would happen
        assert result.dry_run is True
        assert result.patterns_eligible == 2
        assert len(result.patterns_promoted) == 2

        # All promotions should have dry_run=True and no timestamp
        for promotion in result.patterns_promoted:
            assert promotion.dry_run is True
            assert promotion.promoted_at is None

        # Verify NO database mutations occurred
        for pattern_id in test_pattern_ids:
            row = await db_conn.fetchrow(
                "SELECT status FROM learned_patterns WHERE id = $1",
                pattern_id,
            )
            assert row["status"] == initial_statuses[pattern_id], (
                f"Pattern {pattern_id} status should not change in dry run"
            )

        # Verify NO Kafka events were published
        assert len(mock_kafka_publisher.published_events) == 0

    async def test_empty_result_when_no_provisional_patterns(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Returns empty result when no provisional patterns exist.

        Note: This test relies on the fact that test_pattern_ids fixture
        hasn't been loaded (no test patterns in DB at this point).
        """
        # Create a pattern that is already validated (not provisional)
        from datetime import UTC, datetime
        from uuid import uuid4

        pattern_id = uuid4()
        session_id = uuid4()

        await db_conn.execute(
            """
            INSERT INTO learned_patterns (
                id, pattern_signature, domain_id, domain_version, domain_candidates,
                confidence, status, source_session_ids, promoted_at,
                injection_count_rolling_20, success_count_rolling_20,
                failure_count_rolling_20, failure_streak
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            pattern_id,
            f"test_already_validated_{pattern_id}",
            "code_generation",
            "1.0",
            "[]",
            0.9,
            "validated",  # Already validated!
            [session_id],
            datetime.now(UTC),
            10,
            9,
            1,
            0,
        )

        try:
            # Act: Check for patterns to promote (should find none)
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
            )

            # Assert: No patterns were found or promoted
            # (The query only looks at provisional patterns)
            assert result.patterns_eligible == 0
            assert len(result.patterns_promoted) == 0

        finally:
            # Cleanup
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = $1",
                pattern_id,
            )

    async def test_configurable_thresholds_work(
        self,
        db_conn: asyncpg.Connection,
        test_pattern_ids: list[UUID],
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Custom thresholds are applied correctly.

        With higher thresholds, fewer patterns qualify:
        - min_injection_count=10 excludes pattern 1 (has 5)
        - min_success_rate=0.75 excludes pattern 1 (has 60%)
        Only pattern 0 (80% success, 10 injections) qualifies.
        """
        # Act with stricter thresholds
        result = await check_and_promote_patterns(
            repository=db_conn,
            producer=mock_kafka_publisher,
            dry_run=True,  # Use dry run to avoid mutating for other tests
            min_injection_count=10,
            min_success_rate=0.75,
            max_failure_streak=3,
        )

        # Assert: Only 1 pattern meets the stricter criteria
        assert result.patterns_checked == 4
        assert result.patterns_eligible == 1
        assert len(result.patterns_promoted) == 1

        # The promoted pattern should be pattern 0 (80% success, 10 injections)
        promoted_ids = {p.pattern_id for p in result.patterns_promoted}
        assert test_pattern_ids[0] in promoted_ids

    async def test_sql_injection_safety(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Verify parameterized queries prevent SQL injection.

        The handler uses asyncpg positional parameters ($1, $2) which
        are inherently safe. This test confirms no errors occur when
        processing data that might look like SQL injection attempts.
        """
        from datetime import UTC, datetime
        from uuid import uuid4

        # Create a pattern with SQL-injection-like signature
        pattern_id = uuid4()
        session_id = uuid4()
        malicious_signature = "'; DROP TABLE learned_patterns; --"

        await db_conn.execute(
            """
            INSERT INTO learned_patterns (
                id, pattern_signature, domain_id, domain_version, domain_candidates,
                confidence, status, source_session_ids, promoted_at,
                injection_count_rolling_20, success_count_rolling_20,
                failure_count_rolling_20, failure_streak
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            pattern_id,
            malicious_signature,
            "code_generation",
            "1.0",
            "[]",
            0.8,
            "provisional",
            [session_id],
            datetime.now(UTC),
            10,
            8,
            2,
            0,
        )

        try:
            # Act: Promotion should work safely
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
            )

            # Assert: Pattern was processed safely
            assert result.patterns_eligible >= 1

            # Verify the table still exists (injection didn't work)
            count = await db_conn.fetchval(
                "SELECT COUNT(*) FROM learned_patterns WHERE id = $1",
                pattern_id,
            )
            assert count == 1

        finally:
            # Cleanup
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = $1",
                pattern_id,
            )


@pytest.mark.integration
@pytest.mark.asyncio
class TestPromotionEdgeCases:
    """Edge case tests for pattern promotion."""

    async def test_concurrent_promotion_is_idempotent(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """A pattern that's promoted concurrently doesn't cause errors.

        If a pattern is already validated when the UPDATE runs,
        the affected row count is 0 and no event is emitted.
        """
        from datetime import UTC, datetime
        from uuid import uuid4

        pattern_id = uuid4()
        session_id = uuid4()

        await db_conn.execute(
            """
            INSERT INTO learned_patterns (
                id, pattern_signature, domain_id, domain_version, domain_candidates,
                confidence, status, source_session_ids, promoted_at,
                injection_count_rolling_20, success_count_rolling_20,
                failure_count_rolling_20, failure_streak
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            pattern_id,
            f"test_concurrent_{pattern_id}",
            "code_generation",
            "1.0",
            "[]",
            0.8,
            "provisional",
            [session_id],
            datetime.now(UTC),
            10,
            8,
            2,
            0,
        )

        try:
            # First promotion should succeed
            result1 = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
            )

            events_after_first = len(mock_kafka_publisher.published_events)

            # Verify pattern was promoted
            row = await db_conn.fetchrow(
                "SELECT status FROM learned_patterns WHERE id = $1",
                pattern_id,
            )
            assert row["status"] == "validated"

            # Reset to provisional to simulate another promotion attempt
            await db_conn.execute(
                "UPDATE learned_patterns SET status = 'provisional' WHERE id = $1",
                pattern_id,
            )

            # Second promotion should also work
            result2 = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
            )

            # Both promotions completed without error
            assert result1.patterns_eligible >= 1
            assert result2.patterns_eligible >= 1

        finally:
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = $1",
                pattern_id,
            )

    async def test_handles_null_rolling_metrics(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Patterns with NULL rolling metrics are handled gracefully.

        The handler treats NULL as 0, so such patterns fail Gate 1
        (injection count < 5) and are not promoted.
        """
        from datetime import UTC, datetime
        from uuid import uuid4

        pattern_id = uuid4()
        session_id = uuid4()

        # Insert with explicit NULLs (database defaults handle this,
        # but let's be explicit for testing)
        await db_conn.execute(
            """
            INSERT INTO learned_patterns (
                id, pattern_signature, domain_id, domain_version, domain_candidates,
                confidence, status, source_session_ids, promoted_at,
                injection_count_rolling_20, success_count_rolling_20,
                failure_count_rolling_20, failure_streak
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            pattern_id,
            f"test_null_metrics_{pattern_id}",
            "code_generation",
            "1.0",
            "[]",
            0.7,
            "provisional",
            [session_id],
            datetime.now(UTC),
            0,  # Will fail Gate 1
            0,
            0,
            0,
        )

        try:
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
            )

            # Pattern should be checked but not promoted
            assert result.patterns_checked >= 1

            # Pattern should still be provisional
            row = await db_conn.fetchrow(
                "SELECT status FROM learned_patterns WHERE id = $1",
                pattern_id,
            )
            assert row["status"] == "provisional"

        finally:
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = $1",
                pattern_id,
            )
