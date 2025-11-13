"""
Shared test fixtures for Pattern Learning Phase 1 Foundation.

Provides reusable fixtures for:
- Database connection and pool management
- Effect node instances
- Sample pattern data
- Test cleanup and isolation

Track: Track 3-1.5 - Comprehensive Test Suite Generation
"""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from pattern_learning.node_pattern_analytics_effect import NodePatternAnalyticsEffect
from pattern_learning.node_pattern_query_effect import NodePatternQueryEffect
from pattern_learning.node_pattern_storage_effect import (
    ModelContractEffect as StorageContract,
)
from pattern_learning.node_pattern_storage_effect import (
    NodePatternStorageEffect,
)
from pattern_learning.node_pattern_update_effect import NodePatternUpdateEffect
from pattern_learning.pattern_database import PatternDatabaseManager

# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def db_url():
    """Provides the database connection URL from environment variables."""
    # Test-only credential - use TRACEABILITY_DB_URL_EXTERNAL env var in production
    url = os.getenv(
        "TRACEABILITY_DB_URL_EXTERNAL",
        "postgresql://postgres:test_password_for_local_dev_only@localhost:5436/omninode_bridge",
    )
    return url


@pytest_asyncio.fixture(scope="function")
async def asyncpg_pool(db_url):
    """Provides an asyncpg connection pool for each test function."""
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def db_manager(db_url, asyncpg_pool):
    """Provides an initialized PatternDatabaseManager."""
    manager = PatternDatabaseManager(connection_url=db_url)
    # Override the internal pool with our test pool
    manager.pool = asyncpg_pool
    manager._initialized = True  # Mark as initialized since we control the pool
    yield manager
    # Pool is closed by asyncpg_pool fixture


@pytest_asyncio.fixture
async def initialized_db(asyncpg_pool):
    """
    Ensures a clean database state for each test function.
    Cleans up test data after each test while preserving schema.
    """
    async with asyncpg_pool.acquire() as conn:
        # Clean up test data (preserve schema)
        await conn.execute("TRUNCATE TABLE pattern_usage_events CASCADE")
        await conn.execute("TRUNCATE TABLE pattern_relationships CASCADE")
        await conn.execute("TRUNCATE TABLE pattern_analytics CASCADE")
        await conn.execute("TRUNCATE TABLE pattern_templates CASCADE")

        yield conn


# ============================================================================
# Effect Node Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def storage_node(asyncpg_pool, initialized_db):
    """Provides an instance of NodePatternStorageEffect."""
    return NodePatternStorageEffect(asyncpg_pool)


@pytest_asyncio.fixture
async def query_node(asyncpg_pool, initialized_db):
    """Provides an instance of NodePatternQueryEffect."""
    return NodePatternQueryEffect(asyncpg_pool)


@pytest_asyncio.fixture
async def update_node(asyncpg_pool, initialized_db):
    """Provides an instance of NodePatternUpdateEffect."""
    return NodePatternUpdateEffect(asyncpg_pool)


@pytest_asyncio.fixture
async def analytics_node(asyncpg_pool, initialized_db):
    """Provides an instance of NodePatternAnalyticsEffect."""
    return NodePatternAnalyticsEffect(asyncpg_pool)


# ============================================================================
# Sample Data Fixtures
# ============================================================================


@pytest.fixture
def sample_pattern_data():
    """Provides a dictionary of valid pattern data."""
    return {
        "pattern_name": f"TestPattern_{uuid4().hex[:8]}",
        "pattern_type": "code",
        "language": "python",
        "category": "testing",
        "template_code": "async def test_func(): pass",
        "description": "A sample pattern for testing purposes",
        "example_usage": "await test_func()",
        "source": "test_fixture",
        "confidence_score": 0.85,
        "usage_count": 0,
        "success_rate": 1.0,
        "complexity_score": 5,
        "maintainability_score": 0.9,
        "performance_score": 0.7,
        "is_deprecated": False,
        "created_by": "test_user",
        "tags": ["test", "sample", "fixture"],
        "context": {"test_env": True, "version": "1.0"},
    }


@pytest_asyncio.fixture
async def inserted_pattern(storage_node, sample_pattern_data):
    """Inserts a sample pattern and returns its ID and data."""
    contract = StorageContract(operation="insert", data=sample_pattern_data)
    result = await storage_node.execute_effect(contract)
    assert result.success
    pattern_id = UUID(result.data["pattern_id"])
    yield pattern_id, sample_pattern_data


@pytest_asyncio.fixture
async def inserted_patterns(storage_node):
    """Inserts multiple sample patterns and returns their IDs and data."""
    patterns_data = []
    inserted_ids = []

    for i in range(3):
        data = {
            "pattern_name": f"BatchPattern_{i}_{uuid4().hex[:8]}",
            "pattern_type": "code",
            "language": "python",
            "template_code": f"async def batch_func_{i}(): pass",
            "confidence_score": 0.7 + (i * 0.1),
            "tags": [f"batch_{i}", "test"],
        }
        patterns_data.append(data)

        contract = StorageContract(operation="insert", data=data)
        result = await storage_node.execute_effect(contract)
        assert result.success
        inserted_ids.append(UUID(result.data["pattern_id"]))

    yield inserted_ids, patterns_data


@pytest_asyncio.fixture
async def pattern_with_usage(storage_node, initialized_db):
    """Inserts a pattern and records usage events for it."""
    # Insert pattern
    pattern_data = {
        "pattern_name": f"UsagePattern_{uuid4().hex[:8]}",
        "pattern_type": "code",
        "language": "python",
        "template_code": "async def usage_func(): pass",
        "confidence_score": 0.9,
    }

    insert_contract = StorageContract(operation="insert", data=pattern_data)
    insert_result = await storage_node.execute_effect(insert_contract)
    assert insert_result.success
    pattern_id = UUID(insert_result.data["pattern_id"])

    # Record usage events
    for i in range(5):
        success = i % 2 == 0
        quality_before = Decimal("0.5")
        quality_after = Decimal(str(0.5 + (0.1 if success else -0.05)))

        await initialized_db.execute(
            """
            INSERT INTO pattern_usage_events (
                pattern_id, correlation_id, file_path, project_id,
                success, execution_time_ms, error_message,
                quality_before, quality_after, used_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            pattern_id,
            uuid4(),
            f"/project/file_{i}.py",
            uuid4(),
            success,
            100 + i * 10,
            None if success else "Test error",
            quality_before,
            quality_after,
            datetime.now(timezone.utc) - timedelta(days=i),
        )

    # Trigger stats update
    await initialized_db.fetchval("SELECT update_pattern_stats($1)", pattern_id)

    yield pattern_id, pattern_data


@pytest.fixture
def sample_usage_data():
    """Provides sample usage event data."""
    return {
        "file_path": "/test/path/file.py",
        "project_id": str(uuid4()),
        "success": True,
        "execution_time_ms": 150,
        "quality_before": 0.6,
        "quality_after": 0.85,
        "tags": ["test_usage"],
        "context": {"test": True},
    }


@pytest.fixture
def sample_relationship_data(inserted_patterns):
    """Provides sample relationship data between two patterns."""
    pattern_ids, _ = inserted_patterns
    return {
        "source_pattern_id": str(pattern_ids[0]),
        "target_pattern_id": str(pattern_ids[1]),
        "relationship_type": "similar",
        "strength": 0.75,
        "description": "Test relationship",
        "context": {"test": True},
    }
