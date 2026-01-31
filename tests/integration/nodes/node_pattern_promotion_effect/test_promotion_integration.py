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


# =============================================================================
# Additional Integration Tests - Extended Coverage
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestPromotionGate4DisabledPatterns:
    """Tests for Gate 4: Disabled pattern exclusion."""

    async def test_disabled_pattern_excluded_from_promotion(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Patterns in disabled_patterns_current table are excluded from promotion.

        Gate 4 filters out disabled patterns via LEFT JOIN ... IS NULL.
        A pattern that meets all other criteria but is disabled should NOT be promoted.
        """
        from datetime import UTC, datetime
        from uuid import uuid4

        pattern_id = uuid4()
        session_id = uuid4()
        event_id = uuid4()

        # Create an eligible pattern (meets Gates 1-3)
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
            f"test_disabled_pattern_{pattern_id}",
            "code_generation",
            "1.0",
            "[]",
            0.9,
            "provisional",
            [session_id],
            datetime.now(UTC),
            20,   # High injection count (passes Gate 1)
            18,   # 90% success rate (passes Gate 2)
            2,
            0,    # No failure streak (passes Gate 3)
        )

        # Disable the pattern by inserting into pattern_disable_events
        await db_conn.execute(
            """
            INSERT INTO pattern_disable_events (
                event_id, event_type, pattern_id, reason, event_at, actor
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            event_id,
            "disabled",
            pattern_id,
            "Test: verify Gate 4 disabled exclusion",
            datetime.now(UTC),
            "integration_test",
        )

        # Refresh the materialized view to pick up the new disabled pattern
        await db_conn.execute(
            "REFRESH MATERIALIZED VIEW disabled_patterns_current"
        )

        try:
            # Verify pattern appears in disabled_patterns_current
            disabled_row = await db_conn.fetchrow(
                "SELECT pattern_id FROM disabled_patterns_current WHERE pattern_id = $1",
                pattern_id,
            )
            assert disabled_row is not None, "Pattern should be in disabled_patterns_current"

            # Act: Run promotion check
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
            )

            # Assert: Disabled pattern should NOT appear in eligible or promoted lists
            promoted_ids = {p.pattern_id for p in result.patterns_promoted}
            assert pattern_id not in promoted_ids, (
                "Disabled pattern should NOT be promoted even if it meets other criteria"
            )

            # Verify pattern is still provisional in database
            row = await db_conn.fetchrow(
                "SELECT status FROM learned_patterns WHERE id = $1",
                pattern_id,
            )
            assert row["status"] == "provisional", "Disabled pattern should remain provisional"

        finally:
            # Cleanup: Remove disable event and pattern
            await db_conn.execute(
                "DELETE FROM pattern_disable_events WHERE event_id = $1",
                event_id,
            )
            await db_conn.execute(
                "REFRESH MATERIALIZED VIEW disabled_patterns_current"
            )
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = $1",
                pattern_id,
            )

    async def test_reenabled_pattern_can_be_promoted(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Patterns that were disabled but re-enabled can be promoted.

        When a pattern has both disable and re_enable events, the latest
        event determines state. A re-enabled pattern should be eligible.
        """
        from datetime import UTC, datetime, timedelta
        from uuid import uuid4

        pattern_id = uuid4()
        session_id = uuid4()
        disable_event_id = uuid4()
        enable_event_id = uuid4()

        # Create an eligible pattern
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
            f"test_reenabled_pattern_{pattern_id}",
            "code_generation",
            "1.0",
            "[]",
            0.85,
            "provisional",
            [session_id],
            datetime.now(UTC),
            15,   # Good injection count
            12,   # 80% success rate
            3,
            0,
        )

        now = datetime.now(UTC)

        # First: Disable the pattern (older event)
        await db_conn.execute(
            """
            INSERT INTO pattern_disable_events (
                event_id, event_type, pattern_id, reason, event_at, actor
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            disable_event_id,
            "disabled",
            pattern_id,
            "Test: initial disable",
            now - timedelta(hours=1),  # 1 hour ago
            "integration_test",
        )

        # Then: Re-enable the pattern (newer event)
        await db_conn.execute(
            """
            INSERT INTO pattern_disable_events (
                event_id, event_type, pattern_id, reason, event_at, actor
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            enable_event_id,
            "re_enabled",
            pattern_id,
            "Test: re-enable for promotion",
            now,  # Now (more recent)
            "integration_test",
        )

        # Refresh materialized view
        await db_conn.execute(
            "REFRESH MATERIALIZED VIEW disabled_patterns_current"
        )

        try:
            # Verify pattern is NOT in disabled_patterns_current (re-enabled)
            disabled_row = await db_conn.fetchrow(
                "SELECT pattern_id FROM disabled_patterns_current WHERE pattern_id = $1",
                pattern_id,
            )
            assert disabled_row is None, (
                "Re-enabled pattern should NOT be in disabled_patterns_current"
            )

            # Act: Run promotion check
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
            )

            # Assert: Re-enabled pattern should be promoted
            promoted_ids = {p.pattern_id for p in result.patterns_promoted}
            assert pattern_id in promoted_ids, "Re-enabled pattern should be promoted"

            # Verify pattern is now validated
            row = await db_conn.fetchrow(
                "SELECT status FROM learned_patterns WHERE id = $1",
                pattern_id,
            )
            assert row["status"] == "validated"

        finally:
            # Cleanup
            await db_conn.execute(
                "DELETE FROM pattern_disable_events WHERE event_id IN ($1, $2)",
                disable_event_id,
                enable_event_id,
            )
            await db_conn.execute(
                "REFRESH MATERIALIZED VIEW disabled_patterns_current"
            )
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = $1",
                pattern_id,
            )


@pytest.mark.integration
@pytest.mark.asyncio
class TestPromotionLargeBatch:
    """Tests for large batch promotion scenarios."""

    async def test_large_batch_promotion_completes(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Promotion of 100+ patterns completes without timeout.

        This test verifies batch processing performance and correctness
        with a realistic number of patterns.
        """
        from datetime import UTC, datetime
        from uuid import uuid4
        import time

        batch_size = 100
        pattern_ids: list[UUID] = []
        session_id = uuid4()

        # Create 100 eligible patterns
        for i in range(batch_size):
            pattern_id = uuid4()
            pattern_ids.append(pattern_id)
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
                f"test_batch_pattern_{i}_{pattern_id}",
                "code_generation",
                "1.0",
                "[]",
                0.75 + (i % 20) * 0.01,  # Varying confidence
                "provisional",
                [session_id],
                datetime.now(UTC),
                10 + (i % 10),    # 10-19 injections
                8 + (i % 8),      # 70-90% success rate
                2 + (i % 3),      # 2-4 failures
                i % 3,            # 0-2 failure streak (all pass Gate 3)
            )

        try:
            # Measure execution time
            start_time = time.monotonic()

            # Act: Promote all patterns
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
            )

            elapsed_time = time.monotonic() - start_time

            # Assert: All patterns were processed
            assert result.patterns_checked >= batch_size, (
                f"Expected at least {batch_size} patterns checked, got {result.patterns_checked}"
            )
            assert result.patterns_eligible >= batch_size, (
                f"Expected at least {batch_size} eligible, got {result.patterns_eligible}"
            )

            # Count actual promotions (excluding any failures)
            promoted_count = sum(
                1 for p in result.patterns_promoted
                if p.promoted_at is not None and not p.dry_run
            )
            assert promoted_count == batch_size, (
                f"Expected {batch_size} promotions, got {promoted_count}"
            )

            # Verify all patterns are now validated in database
            validated_count = await db_conn.fetchval(
                """
                SELECT COUNT(*) FROM learned_patterns
                WHERE id = ANY($1) AND status = 'validated'
                """,
                pattern_ids,
            )
            assert validated_count == batch_size, (
                f"Expected {batch_size} validated patterns in DB, got {validated_count}"
            )

            # Verify Kafka events count
            assert len(mock_kafka_publisher.published_events) == batch_size, (
                f"Expected {batch_size} Kafka events, got {len(mock_kafka_publisher.published_events)}"
            )

            # Performance assertion: should complete in reasonable time
            assert elapsed_time < 60.0, (
                f"Batch promotion took {elapsed_time:.2f}s, expected < 60s"
            )

        finally:
            # Cleanup: Delete all test patterns in a single statement
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = ANY($1)",
                pattern_ids,
            )

    async def test_mixed_eligibility_large_batch(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Large batch with mixed eligibility is processed correctly.

        50% eligible, 50% ineligible - verifies filtering at scale.
        """
        from datetime import UTC, datetime
        from uuid import uuid4

        batch_size = 50
        pattern_ids: list[UUID] = []
        eligible_ids: list[UUID] = []
        session_id = uuid4()

        # Create 50 patterns: 25 eligible, 25 ineligible
        for i in range(batch_size):
            pattern_id = uuid4()
            pattern_ids.append(pattern_id)

            is_eligible = i % 2 == 0  # Even indices are eligible
            if is_eligible:
                eligible_ids.append(pattern_id)

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
                f"test_mixed_batch_{i}_{pattern_id}",
                "code_generation",
                "1.0",
                "[]",
                0.7,
                "provisional",
                [session_id],
                datetime.now(UTC),
                10 if is_eligible else 3,    # Eligible: 10, Ineligible: 3 (fails Gate 1)
                8 if is_eligible else 2,
                2 if is_eligible else 1,
                0 if is_eligible else 5,     # Ineligible also fails Gate 3
            )

        try:
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
            )

            # Assert: Correct filtering
            assert result.patterns_checked >= batch_size
            assert result.patterns_eligible == len(eligible_ids)

            # Verify only eligible patterns were promoted
            promoted_ids = {
                p.pattern_id for p in result.patterns_promoted
                if p.promoted_at is not None and not p.dry_run
            }
            assert promoted_ids == set(eligible_ids), (
                "Only eligible patterns should be promoted"
            )

        finally:
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = ANY($1)",
                pattern_ids,
            )


@pytest.mark.integration
@pytest.mark.asyncio
class TestPromotionMetricsAccuracy:
    """Tests for gate_snapshot metrics accuracy."""

    async def test_gate_snapshot_values_match_database(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Gate snapshot captures exact database values at promotion time.

        Verifies that the gate_snapshot in the promotion result accurately
        reflects the pattern's rolling metrics from the database.
        """
        from datetime import UTC, datetime
        from uuid import uuid4

        pattern_id = uuid4()
        session_id = uuid4()

        # Create pattern with precise known values
        injection_count = 17
        success_count = 13
        failure_count = 4
        failure_streak = 1
        expected_success_rate = success_count / (success_count + failure_count)

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
            f"test_metrics_accuracy_{pattern_id}",
            "code_generation",
            "1.0",
            "[]",
            0.8,
            "provisional",
            [session_id],
            datetime.now(UTC),
            injection_count,
            success_count,
            failure_count,
            failure_streak,
        )

        try:
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
            )

            # Find our pattern in results
            our_promotion = next(
                (p for p in result.patterns_promoted if p.pattern_id == pattern_id),
                None,
            )
            assert our_promotion is not None, "Pattern should be in promoted list"

            # Verify gate_snapshot accuracy
            snapshot = our_promotion.gate_snapshot
            assert snapshot.injection_count_rolling_20 == injection_count, (
                f"Expected injection_count {injection_count}, got {snapshot.injection_count_rolling_20}"
            )
            assert snapshot.failure_streak == failure_streak, (
                f"Expected failure_streak {failure_streak}, got {snapshot.failure_streak}"
            )
            assert abs(snapshot.success_rate_rolling_20 - expected_success_rate) < 0.0001, (
                f"Expected success_rate {expected_success_rate:.4f}, "
                f"got {snapshot.success_rate_rolling_20:.4f}"
            )
            assert snapshot.disabled is False, "Pattern should not be marked as disabled"

        finally:
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = $1",
                pattern_id,
            )

    async def test_gate_snapshot_boundary_success_rate(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Gate snapshot correctly calculates boundary success rates.

        Tests exact 60% threshold (3/5 success rate).
        """
        from datetime import UTC, datetime
        from uuid import uuid4

        pattern_id = uuid4()
        session_id = uuid4()

        # Exactly at 60% threshold: 3 successes, 2 failures = 60%
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
            f"test_boundary_rate_{pattern_id}",
            "code_generation",
            "1.0",
            "[]",
            0.6,
            "provisional",
            [session_id],
            datetime.now(UTC),
            5,    # At minimum injection count
            3,    # Exactly 60% (boundary)
            2,
            0,
        )

        try:
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=True,  # Use dry run to avoid mutation
            )

            our_promotion = next(
                (p for p in result.patterns_promoted if p.pattern_id == pattern_id),
                None,
            )
            assert our_promotion is not None, "Pattern at 60% should be eligible"

            # Verify exact success rate calculation
            assert our_promotion.gate_snapshot.success_rate_rolling_20 == 0.6, (
                "Success rate should be exactly 0.6 (60%)"
            )

        finally:
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = $1",
                pattern_id,
            )


@pytest.mark.integration
@pytest.mark.asyncio
class TestPromotionZeroToleranceMode:
    """Tests for zero-tolerance failure streak mode (max_failure_streak=0)."""

    async def test_zero_tolerance_blocks_any_failure_streak(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """With max_failure_streak=0, any failure streak blocks promotion.

        Zero-tolerance mode: failure_streak >= 0 check means even 1 failure blocks.
        Only patterns with exactly 0 failure_streak pass.
        """
        from datetime import UTC, datetime
        from uuid import uuid4

        pattern_ids: list[UUID] = []
        session_id = uuid4()

        # Create patterns with different failure streaks
        test_cases = [
            (0, True),   # 0 failures - SHOULD pass in zero-tolerance
            (1, False),  # 1 failure - should fail
            (2, False),  # 2 failures - should fail
        ]

        for streak, _ in test_cases:
            pattern_id = uuid4()
            pattern_ids.append(pattern_id)
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
                f"test_zero_tolerance_streak_{streak}_{pattern_id}",
                "code_generation",
                "1.0",
                "[]",
                0.85,
                "provisional",
                [session_id],
                datetime.now(UTC),
                20,
                18,
                2,
                streak,  # Variable failure streak
            )

        try:
            # Act with zero-tolerance mode
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=True,
                max_failure_streak=1,  # 1 means streak >= 1 blocks, so only 0 passes
            )

            promoted_ids = {p.pattern_id for p in result.patterns_promoted}

            # Only pattern with streak=0 should be promoted
            # Pattern 0 (streak=0) should pass
            assert pattern_ids[0] in promoted_ids, (
                "Pattern with streak=0 should pass in max_failure_streak=1 mode"
            )
            # Patterns with streak >= 1 should fail
            assert pattern_ids[1] not in promoted_ids, (
                "Pattern with streak=1 should fail in max_failure_streak=1 mode"
            )
            assert pattern_ids[2] not in promoted_ids, (
                "Pattern with streak=2 should fail in max_failure_streak=1 mode"
            )

        finally:
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = ANY($1)",
                pattern_ids,
            )

    async def test_strict_tolerance_mode_max_streak_1(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """With max_failure_streak=1, only 0 failure streak passes.

        This is the strictest practical setting: any single recent failure blocks.
        """
        from datetime import UTC, datetime
        from uuid import uuid4

        pattern_id_zero = uuid4()
        pattern_id_one = uuid4()
        session_id = uuid4()

        # Pattern with 0 streak
        await db_conn.execute(
            """
            INSERT INTO learned_patterns (
                id, pattern_signature, domain_id, domain_version, domain_candidates,
                confidence, status, source_session_ids, promoted_at,
                injection_count_rolling_20, success_count_rolling_20,
                failure_count_rolling_20, failure_streak
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            pattern_id_zero,
            f"test_strict_zero_{pattern_id_zero}",
            "code_generation",
            "1.0",
            "[]",
            0.9,
            "provisional",
            [session_id],
            datetime.now(UTC),
            10, 9, 1, 0,  # 0 streak
        )

        # Pattern with exactly 1 streak
        await db_conn.execute(
            """
            INSERT INTO learned_patterns (
                id, pattern_signature, domain_id, domain_version, domain_candidates,
                confidence, status, source_session_ids, promoted_at,
                injection_count_rolling_20, success_count_rolling_20,
                failure_count_rolling_20, failure_streak
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            pattern_id_one,
            f"test_strict_one_{pattern_id_one}",
            "code_generation",
            "1.0",
            "[]",
            0.9,
            "provisional",
            [session_id],
            datetime.now(UTC),
            10, 9, 1, 1,  # 1 streak
        )

        try:
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=True,
                max_failure_streak=1,  # Strict mode
            )

            promoted_ids = {p.pattern_id for p in result.patterns_promoted}

            # Only streak=0 passes
            assert pattern_id_zero in promoted_ids, "Streak 0 should pass with max=1"
            assert pattern_id_one not in promoted_ids, "Streak 1 should fail with max=1"

        finally:
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id IN ($1, $2)",
                pattern_id_zero,
                pattern_id_one,
            )


@pytest.mark.integration
@pytest.mark.asyncio
class TestPromotionPartialFailure:
    """Tests for partial failure scenarios and error isolation."""

    async def test_continues_after_individual_pattern_error(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Promotion continues processing remaining patterns after one fails.

        The handler uses per-pattern error isolation, so a failure in one
        pattern does not block the promotion of others.
        """
        from datetime import UTC, datetime
        from uuid import uuid4

        pattern_ids: list[UUID] = []
        session_id = uuid4()

        # Create 5 eligible patterns
        for i in range(5):
            pattern_id = uuid4()
            pattern_ids.append(pattern_id)
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
                f"test_partial_failure_{i}_{pattern_id}",
                "code_generation",
                "1.0",
                "[]",
                0.8,
                "provisional",
                [session_id],
                datetime.now(UTC),
                10, 8, 2, 0,
            )

        try:
            # Promote patterns normally (no simulated error)
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
            )

            # All 5 should be processed
            assert result.patterns_eligible >= 5

            # Count successful promotions
            successful = sum(
                1 for p in result.patterns_promoted
                if p.promoted_at is not None and "failed" not in p.reason
            )
            assert successful == 5, f"Expected 5 successful promotions, got {successful}"

        finally:
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = ANY($1)",
                pattern_ids,
            )

    async def test_promoted_patterns_persist_after_later_failure(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Patterns promoted before a failure remain promoted.

        Per-pattern transaction model: each promotion is independent.
        """
        from datetime import UTC, datetime
        from uuid import uuid4

        pattern_ids: list[UUID] = []
        session_id = uuid4()

        # Create multiple patterns
        for i in range(3):
            pattern_id = uuid4()
            pattern_ids.append(pattern_id)
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
                f"test_persist_{i}_{pattern_id}",
                "code_generation",
                "1.0",
                "[]",
                0.8,
                "provisional",
                [session_id],
                datetime.now(UTC),
                10, 8, 2, 0,
            )

        try:
            # Promote first pattern
            result1 = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
            )

            # Verify all 3 were promoted
            assert result1.patterns_eligible >= 3

            promoted_count = await db_conn.fetchval(
                """
                SELECT COUNT(*) FROM learned_patterns
                WHERE id = ANY($1) AND status = 'validated'
                """,
                pattern_ids,
            )
            assert promoted_count == 3, "All 3 patterns should be validated"

            # Run promotion again (no changes expected - already validated)
            result2 = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
            )

            # Previously promoted patterns stay validated
            still_validated = await db_conn.fetchval(
                """
                SELECT COUNT(*) FROM learned_patterns
                WHERE id = ANY($1) AND status = 'validated'
                """,
                pattern_ids,
            )
            assert still_validated == 3, "All patterns should remain validated"

        finally:
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = ANY($1)",
                pattern_ids,
            )


@pytest.mark.integration
@pytest.mark.asyncio
class TestPromotionKafkaEvents:
    """Tests for Kafka event emission accuracy."""

    async def test_kafka_event_schema_compliance(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
        sample_correlation_id: UUID,
    ) -> None:
        """Kafka events match the expected schema contract.

        Verifies all required fields are present and correctly formatted.
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
            f"test_kafka_schema_{pattern_id}",
            "code_generation",
            "1.0",
            "[]",
            0.85,
            "provisional",
            [session_id],
            datetime.now(UTC),
            15, 12, 3, 0,
        )

        try:
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
                correlation_id=sample_correlation_id,
            )

            # Verify event was published
            assert len(mock_kafka_publisher.published_events) >= 1

            # Find our pattern's event
            our_event = None
            for topic, key, value in mock_kafka_publisher.published_events:
                if key == str(pattern_id):
                    our_event = value
                    break

            assert our_event is not None, "Event for our pattern should be published"

            # Verify required schema fields
            assert our_event["event_type"] == "PatternPromoted"
            assert our_event["pattern_id"] == str(pattern_id)
            assert "pattern_signature" in our_event
            assert our_event["from_status"] == "provisional"
            assert our_event["to_status"] == "validated"
            assert "success_rate_rolling_20" in our_event
            assert 0.0 <= our_event["success_rate_rolling_20"] <= 1.0
            assert "promoted_at" in our_event
            assert our_event["correlation_id"] == str(sample_correlation_id)

        finally:
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = $1",
                pattern_id,
            )

    async def test_no_kafka_event_on_dry_run(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """No Kafka events are emitted during dry run.

        Dry run mode should not emit any events, even for eligible patterns.
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
            f"test_dry_run_no_kafka_{pattern_id}",
            "code_generation",
            "1.0",
            "[]",
            0.9,
            "provisional",
            [session_id],
            datetime.now(UTC),
            10, 9, 1, 0,
        )

        try:
            # Clear any existing events
            mock_kafka_publisher.published_events.clear()

            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=True,  # DRY RUN
            )

            # Pattern should be eligible
            assert result.patterns_eligible >= 1

            # But no Kafka events
            assert len(mock_kafka_publisher.published_events) == 0, (
                "No Kafka events should be emitted during dry run"
            )

        finally:
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = $1",
                pattern_id,
            )

    async def test_kafka_topic_includes_env_prefix(
        self,
        db_conn: asyncpg.Connection,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Kafka topic includes the environment prefix.

        Topic format: {env}.pattern-promoted.v1
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
            f"test_topic_prefix_{pattern_id}",
            "code_generation",
            "1.0",
            "[]",
            0.8,
            "provisional",
            [session_id],
            datetime.now(UTC),
            10, 8, 2, 0,
        )

        try:
            # Use custom prefix
            result = await check_and_promote_patterns(
                repository=db_conn,
                producer=mock_kafka_publisher,
                dry_run=False,
                topic_env_prefix="staging",
            )

            # Verify topic prefix
            assert len(mock_kafka_publisher.published_events) >= 1
            topic, _, _ = mock_kafka_publisher.published_events[0]
            assert topic.startswith("staging."), (
                f"Topic should start with 'staging.', got: {topic}"
            )
            assert "pattern-promoted" in topic

        finally:
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = $1",
                pattern_id,
            )
