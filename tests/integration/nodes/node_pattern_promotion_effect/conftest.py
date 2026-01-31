# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Fixtures for pattern_promotion_effect integration tests.

Provides asyncpg connections and test data management for
testing against real PostgreSQL (192.168.86.200:5436).
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio

# =============================================================================
# Database Configuration
# =============================================================================

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "192.168.86.200")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5436"))
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "omninode_bridge")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# Test data constants
TEST_DOMAIN_ID = "code_generation"  # Pre-seeded domain from migrations
TEST_DOMAIN_VERSION = "1.0"


# =============================================================================
# Database Connection Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def db_conn() -> AsyncGenerator[asyncpg.Connection, None]:
    """Create a connection for integration tests.

    Yields:
        asyncpg.Connection connected to the test database.

    Raises:
        pytest.skip: If database is not available or password not set.
    """
    if not POSTGRES_PASSWORD:
        pytest.skip("POSTGRES_PASSWORD not set - skipping integration tests")

    try:
        conn = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DATABASE,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            timeout=30,
        )
    except (OSError, asyncpg.PostgresError) as e:
        pytest.skip(f"Database not available: {e}")

    try:
        yield conn
    finally:
        await conn.close()


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
            id, pattern_signature, domain_id, domain_version, domain_candidates,
            confidence, status, source_session_ids, promoted_at,
            injection_count_rolling_20, success_count_rolling_20,
            failure_count_rolling_20, failure_streak
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """,
        id1,
        f"test_pattern_eligible_high_{id1}",
        TEST_DOMAIN_ID,
        TEST_DOMAIN_VERSION,
        "[]",
        0.8,
        "provisional",
        [session_id],
        datetime.now(UTC),  # provisional requires promoted_at
        10,  # injection_count
        8,   # success_count (80%)
        2,   # failure_count
        0,   # failure_streak
    )

    # Pattern 2: Eligible - At exact thresholds
    id2 = uuid4()
    pattern_ids.append(id2)
    await db_conn.execute(
        """
        INSERT INTO learned_patterns (
            id, pattern_signature, domain_id, domain_version, domain_candidates,
            confidence, status, source_session_ids, promoted_at,
            injection_count_rolling_20, success_count_rolling_20,
            failure_count_rolling_20, failure_streak
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """,
        id2,
        f"test_pattern_eligible_threshold_{id2}",
        TEST_DOMAIN_ID,
        TEST_DOMAIN_VERSION,
        "[]",
        0.6,
        "provisional",
        [session_id],
        datetime.now(UTC),
        5,   # injection_count (at minimum)
        3,   # success_count (60%)
        2,   # failure_count
        2,   # failure_streak (below max)
    )

    # Pattern 3: Not eligible - Low injection count
    id3 = uuid4()
    pattern_ids.append(id3)
    await db_conn.execute(
        """
        INSERT INTO learned_patterns (
            id, pattern_signature, domain_id, domain_version, domain_candidates,
            confidence, status, source_session_ids, promoted_at,
            injection_count_rolling_20, success_count_rolling_20,
            failure_count_rolling_20, failure_streak
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """,
        id3,
        f"test_pattern_ineligible_low_count_{id3}",
        TEST_DOMAIN_ID,
        TEST_DOMAIN_VERSION,
        "[]",
        0.9,
        "provisional",
        [session_id],
        datetime.now(UTC),
        4,   # injection_count (BELOW minimum)
        4,   # success_count (100%)
        0,   # failure_count
        0,   # failure_streak
    )

    # Pattern 4: Not eligible - High failure streak
    id4 = uuid4()
    pattern_ids.append(id4)
    await db_conn.execute(
        """
        INSERT INTO learned_patterns (
            id, pattern_signature, domain_id, domain_version, domain_candidates,
            confidence, status, source_session_ids, promoted_at,
            injection_count_rolling_20, success_count_rolling_20,
            failure_count_rolling_20, failure_streak
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """,
        id4,
        f"test_pattern_ineligible_high_streak_{id4}",
        TEST_DOMAIN_ID,
        TEST_DOMAIN_VERSION,
        "[]",
        0.7,
        "provisional",
        [session_id],
        datetime.now(UTC),
        10,  # injection_count
        7,   # success_count (70%)
        3,   # failure_count
        3,   # failure_streak (AT maximum - blocks promotion)
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


@pytest.fixture
def sample_correlation_id() -> UUID:
    """Fixed correlation ID for tracing tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


# =============================================================================
# Mock Kafka Publisher (for tests that don't need real Kafka)
# =============================================================================


class MockKafkaPublisher:
    """Mock Kafka publisher that records events without publishing."""

    def __init__(self) -> None:
        self.published_events: list[tuple[str, str, dict[str, Any]]] = []

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Record the event instead of publishing."""
        self.published_events.append((topic, key, value))


@pytest.fixture
def mock_kafka_publisher() -> MockKafkaPublisher:
    """Create a mock Kafka publisher."""
    return MockKafkaPublisher()
