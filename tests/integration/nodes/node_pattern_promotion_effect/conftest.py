# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Fixtures for pattern_promotion_effect integration tests.

Provides test data management for testing pattern promotion against real
PostgreSQL (192.168.86.200:5436).

Inherits from tests/integration/conftest.py:
    - db_conn, db_pool: Database connection fixtures
    - kafka_producer, kafka_consumer: Kafka fixtures
    - MockKafkaPublisher, mock_kafka_publisher: Mock publisher for testing
    - TEST_DOMAIN_ID, TEST_DOMAIN_VERSION: Test data constants
    - requires_postgres, requires_kafka, requires_password: Skip markers

This module adds test-specific data fixtures for pattern promotion testing.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest_asyncio

# Import shared fixtures and constants from parent conftest
# These are automatically available via pytest's conftest discovery,
# but explicit import makes the dependencies clear.
from tests.integration.conftest import (
    TEST_DOMAIN_ID,
    TEST_DOMAIN_VERSION,
    MockKafkaPublisher,
)

# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def test_pattern_ids(
    db_conn: asyncpg.Connection,
) -> AsyncGenerator[list[UUID], None]:
    """Create test patterns and clean them up after the test.

    Creates 4 patterns with different rolling metrics:
    1. Eligible for promotion (high success rate, no failure streak)
    2. Eligible for promotion (at thresholds)
    3. Not eligible (low injection count)
    4. Not eligible (high failure streak)

    Args:
        db_conn: Database connection from shared conftest.

    Yields:
        List of created pattern UUIDs.
    """
    pattern_ids: list[UUID] = []
    session_id = uuid4()

    # Pattern 1: Eligible - High success rate
    id1 = uuid4()
    pattern_ids.append(id1)
    await db_conn.execute(
        """
        INSERT INTO learned_patterns (
            id, pattern_signature, signature_hash, domain_id, domain_version, domain_candidates,
            confidence, status, source_session_ids, promoted_at,
            injection_count_rolling_20, success_count_rolling_20,
            failure_count_rolling_20, failure_streak
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """,
        id1,
        f"test_pattern_eligible_high_{id1}",
        str(id1),  # signature_hash
        TEST_DOMAIN_ID,
        TEST_DOMAIN_VERSION,
        "[]",
        0.8,
        "provisional",
        [session_id],
        datetime.now(UTC),  # provisional requires promoted_at
        10,  # injection_count
        8,  # success_count (80%)
        2,  # failure_count
        0,  # failure_streak
    )

    # Pattern 2: Eligible - At exact thresholds
    id2 = uuid4()
    pattern_ids.append(id2)
    await db_conn.execute(
        """
        INSERT INTO learned_patterns (
            id, pattern_signature, signature_hash, domain_id, domain_version, domain_candidates,
            confidence, status, source_session_ids, promoted_at,
            injection_count_rolling_20, success_count_rolling_20,
            failure_count_rolling_20, failure_streak
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """,
        id2,
        f"test_pattern_eligible_threshold_{id2}",
        str(id2),  # signature_hash
        TEST_DOMAIN_ID,
        TEST_DOMAIN_VERSION,
        "[]",
        0.6,
        "provisional",
        [session_id],
        datetime.now(UTC),
        5,  # injection_count (at minimum)
        3,  # success_count (60%)
        2,  # failure_count
        2,  # failure_streak (below max)
    )

    # Pattern 3: Not eligible - Low injection count
    id3 = uuid4()
    pattern_ids.append(id3)
    await db_conn.execute(
        """
        INSERT INTO learned_patterns (
            id, pattern_signature, signature_hash, domain_id, domain_version, domain_candidates,
            confidence, status, source_session_ids, promoted_at,
            injection_count_rolling_20, success_count_rolling_20,
            failure_count_rolling_20, failure_streak
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """,
        id3,
        f"test_pattern_ineligible_low_count_{id3}",
        str(id3),  # signature_hash
        TEST_DOMAIN_ID,
        TEST_DOMAIN_VERSION,
        "[]",
        0.9,
        "provisional",
        [session_id],
        datetime.now(UTC),
        4,  # injection_count (BELOW minimum)
        4,  # success_count (100%)
        0,  # failure_count
        0,  # failure_streak
    )

    # Pattern 4: Not eligible - High failure streak
    id4 = uuid4()
    pattern_ids.append(id4)
    await db_conn.execute(
        """
        INSERT INTO learned_patterns (
            id, pattern_signature, signature_hash, domain_id, domain_version, domain_candidates,
            confidence, status, source_session_ids, promoted_at,
            injection_count_rolling_20, success_count_rolling_20,
            failure_count_rolling_20, failure_streak
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """,
        id4,
        f"test_pattern_ineligible_high_streak_{id4}",
        str(id4),  # signature_hash
        TEST_DOMAIN_ID,
        TEST_DOMAIN_VERSION,
        "[]",
        0.7,
        "provisional",
        [session_id],
        datetime.now(UTC),
        10,  # injection_count
        7,  # success_count (70%)
        3,  # failure_count
        3,  # failure_streak (AT maximum - blocks promotion)
    )

    try:
        yield pattern_ids
    finally:
        # Cleanup: Delete test patterns
        for pattern_id in pattern_ids:
            await db_conn.execute(
                "DELETE FROM learned_patterns WHERE id = $1",
                pattern_id,
            )


# =============================================================================
# Exports
# =============================================================================

# Note: sample_correlation_id and mock_kafka_publisher fixtures are inherited
# from tests/integration/conftest.py and automatically available via pytest.

__all__ = [
    "TEST_DOMAIN_ID",
    "TEST_DOMAIN_VERSION",
    "MockKafkaPublisher",
    "test_pattern_ids",
]
