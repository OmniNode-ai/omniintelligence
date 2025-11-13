"""
Test Suite: Pattern Lineage Tracker Effect Node

Tests for NodePatternLineageTrackerEffect ONEX Effect node.

Coverage Target: >90%

Test Categories:
- Unit tests for each operation handler
- Integration tests with PostgreSQL
- Performance tests (< targets)
- Error handling tests
- Edge case tests

Performance Targets:
- Event tracking: <50ms
- Ancestry query: <200ms
- Graph traversal: <300ms
"""

import os
from uuid import UUID, uuid4

import pytest

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

from .model_contract_pattern_lineage import (
    EdgeType,
    LineageEventType,
    ModelPatternLineageInput,
    TransformationType,
)
from .node_pattern_lineage_tracker_effect import NodePatternLineageTrackerEffect

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture(scope="module")
# NOTE: correlation_id support enabled for tracing
async def db_pool():
    """Create database connection pool for testing."""
    if not ASYNCPG_AVAILABLE:
        pytest.skip("asyncpg not available")

    # Test-only credential - use TRACEABILITY_DB_URL_EXTERNAL env var in production
    db_url = os.getenv(
        "TRACEABILITY_DB_URL_EXTERNAL",
        "postgresql://postgres:test_password_for_local_dev_only@localhost:5436/omninode_bridge",
    )

    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)

    # Verify schema exists
    async with pool.acquire() as conn:
        # Check if tables exist
        tables_query = """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN (
                'pattern_lineage_nodes',
                'pattern_lineage_edges',
                'pattern_lineage_events',
                'pattern_ancestry_cache'
            )
        """
        tables = await conn.fetch(tables_query)

        if len(tables) < 4:
            pytest.skip(
                "Pattern lineage schema not initialized. Run schema_pattern_lineage.sql first."
            )

    yield pool

    await pool.close()


@pytest.fixture(scope="function")
async def lineage_tracker(db_pool):
    """Create NodePatternLineageTrackerEffect instance."""
    return NodePatternLineageTrackerEffect(db_pool)


@pytest.fixture(scope="function")
async def cleanup_test_data(db_pool):
    """Clean up test data after each test."""
    yield

    # Clean up test patterns
    async with db_pool.acquire() as conn:
        # Delete test patterns (cascade will clean up edges and events)
        await conn.execute(
            """
            DELETE FROM pattern_lineage_nodes
            WHERE pattern_id LIKE 'test_%'
        """
        )

        await conn.execute(
            """
            DELETE FROM pattern_lineage_events
            WHERE pattern_id LIKE 'test_%'
        """
        )

        await conn.execute(
            """
            DELETE FROM pattern_ancestry_cache
            WHERE pattern_id LIKE 'test_%'
        """
        )


# ============================================================================
# Unit Tests - Track Creation
# ============================================================================


@pytest.mark.asyncio
async def test_track_creation_success(lineage_tracker, cleanup_test_data):
    """Test successful pattern creation tracking."""
    contract = ModelPatternLineageInput(
        name="test_track_creation",
        operation="track_creation",
        event_type=LineageEventType.PATTERN_CREATED,
        pattern_id=f"test_pattern_{uuid4().hex[:8]}",
        pattern_name="TestAsyncPattern",
        pattern_type="code",
        pattern_version="1.0.0",
        pattern_data={"template_code": "async def test(): pass", "language": "python"},
        triggered_by="test_suite",
    )

    result = await lineage_tracker.execute_effect(contract)

    assert result.success is True
    assert result.data is not None
    assert "lineage_id" in result.data
    assert "pattern_node_id" in result.data
    assert "event_id" in result.data
    assert result.data["pattern_id"] == contract.pattern_id
    assert result.metadata["duration_ms"] < 50  # Performance target


@pytest.mark.asyncio
async def test_track_creation_duplicate(lineage_tracker, cleanup_test_data):
    """Test tracking duplicate pattern creation (should fail)."""
    pattern_id = f"test_pattern_{uuid4().hex[:8]}"

    contract = ModelPatternLineageInput(
        name="test_track_creation",
        operation="track_creation",
        pattern_id=pattern_id,
        pattern_name="TestPattern",
        pattern_version="1.0.0",
        pattern_data={"code": "test"},
    )

    # First creation should succeed
    result1 = await lineage_tracker.execute_effect(contract)
    assert result1.success is True

    # Second creation with same ID and version should fail (unique violation)
    result2 = await lineage_tracker.execute_effect(contract)
    assert result2.success is False
    assert (
        "already exists" in result2.error.lower() or "unique" in result2.error.lower()
    )


@pytest.mark.asyncio
async def test_track_creation_missing_data(lineage_tracker):
    """Test tracking creation without pattern data (should fail validation)."""
    # This should fail during contract initialization due to __post_init__ validation
    with pytest.raises(ValueError, match="track_creation requires pattern_data"):
        ModelPatternLineageInput(
            name="test_invalid_creation",
            operation="track_creation",
            pattern_id=f"test_pattern_{uuid4().hex[:8]}",
            pattern_name="TestPattern",
            pattern_data={},  # Empty data
        )


# ============================================================================
# Unit Tests - Track Modification
# ============================================================================


@pytest.mark.asyncio
async def test_track_modification_success(lineage_tracker, cleanup_test_data):
    """Test successful pattern modification tracking."""
    parent_id = f"test_pattern_{uuid4().hex[:8]}"

    # Create parent pattern first
    create_contract = ModelPatternLineageInput(
        name="test_create_parent",
        operation="track_creation",
        pattern_id=parent_id,
        pattern_name="ParentPattern",
        pattern_version="1.0.0",
        pattern_data={"code": "original"},
    )

    create_result = await lineage_tracker.execute_effect(create_contract)
    assert create_result.success is True

    # Now track modification
    child_id = f"test_pattern_{uuid4().hex[:8]}"
    modify_contract = ModelPatternLineageInput(
        operation="track_modification",
        event_type=LineageEventType.PATTERN_MODIFIED,
        pattern_id=child_id,
        pattern_name="ModifiedPattern",
        pattern_version="2.0.0",
        pattern_data={"code": "modified"},
        parent_pattern_ids=[parent_id],
        edge_type=EdgeType.MODIFIED_FROM,
        transformation_type=TransformationType.ENHANCEMENT,
        reason="Added new features",
    )

    result = await lineage_tracker.execute_effect(modify_contract)

    assert result.success is True
    assert result.data["pattern_id"] == child_id
    assert len(result.data["parent_node_ids"]) == 1
    assert result.data["generation"] == 2  # Parent was generation 1


@pytest.mark.asyncio
async def test_track_modification_nonexistent_parent(
    lineage_tracker, cleanup_test_data
):
    """Test tracking modification with non-existent parent (should fail)."""
    modify_contract = ModelPatternLineageInput(
        name="test_orphan_modification",
        operation="track_modification",
        pattern_id=f"test_pattern_{uuid4().hex[:8]}",
        pattern_name="OrphanPattern",
        pattern_version="2.0.0",
        pattern_data={"code": "orphan"},
        parent_pattern_ids=["nonexistent_parent"],
        edge_type=EdgeType.MODIFIED_FROM,
    )

    result = await lineage_tracker.execute_effect(modify_contract)

    assert result.success is False
    assert "not found" in result.error.lower()


# ============================================================================
# Unit Tests - Track Merge
# ============================================================================


@pytest.mark.asyncio
async def test_track_merge_success(lineage_tracker, cleanup_test_data):
    """Test successful pattern merge tracking."""
    # Create two parent patterns
    parent1_id = f"test_pattern_{uuid4().hex[:8]}"
    parent2_id = f"test_pattern_{uuid4().hex[:8]}"

    for parent_id in [parent1_id, parent2_id]:
        create_contract = ModelPatternLineageInput(
            name=f"test_create_{parent_id}",
            operation="track_creation",
            pattern_id=parent_id,
            pattern_name=f"Parent{parent_id}",
            pattern_version="1.0.0",
            pattern_data={"code": f"parent_{parent_id}"},
        )
        result = await lineage_tracker.execute_effect(create_contract)
        assert result.success is True

    # Track merge
    merged_id = f"test_pattern_{uuid4().hex[:8]}"
    merge_contract = ModelPatternLineageInput(
        operation="track_merge",
        event_type=LineageEventType.PATTERN_MERGED,
        pattern_id=merged_id,
        pattern_name="MergedPattern",
        pattern_version="1.0.0",
        pattern_data={"code": "merged"},
        parent_pattern_ids=[parent1_id, parent2_id],
        edge_type=EdgeType.MERGED_FROM,
        transformation_type=TransformationType.MERGE,
        reason="Combined both patterns",
    )

    result = await lineage_tracker.execute_effect(merge_contract)

    assert result.success is True
    assert result.data["pattern_id"] == merged_id
    assert result.data["parent_count"] == 2
    assert len(result.data["parent_node_ids"]) == 2


@pytest.mark.asyncio
async def test_track_merge_single_parent(lineage_tracker, cleanup_test_data):
    """Test tracking merge with only one parent (should fail validation)."""
    parent_id = f"test_pattern_{uuid4().hex[:8]}"

    # Create parent
    create_contract = ModelPatternLineageInput(
        name="test_create_parent_for_merge",
        operation="track_creation",
        pattern_id=parent_id,
        pattern_name="Parent",
        pattern_version="1.0.0",
        pattern_data={"code": "parent"},
    )
    await lineage_tracker.execute_effect(create_contract)

    # Try to merge with only one parent - should fail during contract initialization
    with pytest.raises(ValueError, match="at least 2"):
        ModelPatternLineageInput(
            name="test_invalid_merge",
            operation="track_merge",
            pattern_id=f"test_pattern_{uuid4().hex[:8]}",
            pattern_name="InvalidMerge",
            pattern_version="1.0.0",
            pattern_data={"code": "merged"},
            parent_pattern_ids=[parent_id],  # Only one parent
        )


# ============================================================================
# Unit Tests - Track Application
# ============================================================================


@pytest.mark.asyncio
async def test_track_application_success(lineage_tracker, cleanup_test_data):
    """Test successful pattern application tracking."""
    # Create pattern first
    pattern_id = f"test_pattern_{uuid4().hex[:8]}"
    create_contract = ModelPatternLineageInput(
        name="test_create_for_application",
        operation="track_creation",
        pattern_id=pattern_id,
        pattern_name="AppliedPattern",
        pattern_version="1.0.0",
        pattern_data={"code": "pattern"},
    )
    await lineage_tracker.execute_effect(create_contract)

    # Track application
    apply_contract = ModelPatternLineageInput(
        operation="track_application",
        event_type=LineageEventType.PATTERN_APPLIED,
        pattern_id=pattern_id,
        pattern_data={"usage_context": "test_execution"},
        metadata={"execution_time_ms": 42},
        reason="Applied in test scenario",
    )

    result = await lineage_tracker.execute_effect(apply_contract)

    assert result.success is True
    assert result.data["pattern_id"] == pattern_id
    assert "event_id" in result.data


# ============================================================================
# Unit Tests - Track Deprecation
# ============================================================================


@pytest.mark.asyncio
async def test_track_deprecation_success(lineage_tracker, cleanup_test_data):
    """Test successful pattern deprecation tracking."""
    # Create pattern first
    pattern_id = f"test_pattern_{uuid4().hex[:8]}"
    create_contract = ModelPatternLineageInput(
        name="test_create_for_deprecation",
        operation="track_creation",
        pattern_id=pattern_id,
        pattern_name="DeprecatedPattern",
        pattern_version="1.0.0",
        pattern_data={"code": "old_pattern"},
    )
    await lineage_tracker.execute_effect(create_contract)

    # Track deprecation
    deprecate_contract = ModelPatternLineageInput(
        operation="track_deprecation",
        event_type=LineageEventType.PATTERN_DEPRECATED,
        pattern_id=pattern_id,
        reason="Replaced by newer version",
    )

    result = await lineage_tracker.execute_effect(deprecate_contract)

    assert result.success is True
    assert result.data["deprecated"] is True
    assert result.data["pattern_id"] == pattern_id


# ============================================================================
# Unit Tests - Query Ancestry
# ============================================================================


@pytest.mark.asyncio
async def test_query_ancestry_single_generation(lineage_tracker, cleanup_test_data):
    """Test querying ancestry for root pattern (no ancestors)."""
    # Create root pattern
    pattern_id = f"test_pattern_{uuid4().hex[:8]}"
    create_contract = ModelPatternLineageInput(
        name="test_create_root_pattern",
        operation="track_creation",
        pattern_id=pattern_id,
        pattern_name="RootPattern",
        pattern_version="1.0.0",
        pattern_data={"code": "root"},
    )
    await lineage_tracker.execute_effect(create_contract)

    # Query ancestry
    query_contract = ModelPatternLineageInput(
        operation="query_ancestry", pattern_id=pattern_id
    )

    result = await lineage_tracker.execute_effect(query_contract)

    assert result.success is True
    assert result.data["pattern_id"] == pattern_id
    # Root pattern only has itself in ancestry
    assert result.data["ancestry_depth"] == 0
    assert result.data["total_ancestors"] == 0
    assert result.metadata["duration_ms"] < 200  # Performance target


@pytest.mark.asyncio
async def test_query_ancestry_multi_generation(lineage_tracker, cleanup_test_data):
    """Test querying ancestry across multiple generations."""
    # Create lineage chain: gen1 -> gen2 -> gen3
    gen1_id = f"test_pattern_{uuid4().hex[:8]}"
    gen2_id = f"test_pattern_{uuid4().hex[:8]}"
    gen3_id = f"test_pattern_{uuid4().hex[:8]}"

    # Create gen1 (root)
    await lineage_tracker.execute_effect(
        ModelPatternLineageInput(
            name="test_gen1",
            operation="track_creation",
            pattern_id=gen1_id,
            pattern_name="Gen1",
            pattern_version="1.0.0",
            pattern_data={"gen": 1},
        )
    )

    # Create gen2 (derived from gen1)
    await lineage_tracker.execute_effect(
        ModelPatternLineageInput(
            name="test_gen2",
            operation="track_modification",
            pattern_id=gen2_id,
            pattern_name="Gen2",
            pattern_version="2.0.0",
            pattern_data={"gen": 2},
            parent_pattern_ids=[gen1_id],
            edge_type=EdgeType.MODIFIED_FROM,
        )
    )

    # Create gen3 (derived from gen2)
    await lineage_tracker.execute_effect(
        ModelPatternLineageInput(
            name="test_gen3",
            operation="track_modification",
            pattern_id=gen3_id,
            pattern_name="Gen3",
            pattern_version="3.0.0",
            pattern_data={"gen": 3},
            parent_pattern_ids=[gen2_id],
            edge_type=EdgeType.MODIFIED_FROM,
        )
    )

    # Query ancestry of gen3
    query_contract = ModelPatternLineageInput(
        operation="query_ancestry", pattern_id=gen3_id
    )

    result = await lineage_tracker.execute_effect(query_contract)

    assert result.success is True
    assert result.data["ancestry_depth"] == 2  # gen2 and gen1
    assert result.data["total_ancestors"] == 2
    # Should include gen3, gen2, gen1 in ancestry
    assert len(result.data["ancestors"]) == 3


# ============================================================================
# Unit Tests - Query Descendants
# ============================================================================


@pytest.mark.asyncio
async def test_query_descendants_success(lineage_tracker, cleanup_test_data):
    """Test querying descendants of a pattern."""
    # Create parent and children
    parent_id = f"test_pattern_{uuid4().hex[:8]}"
    child1_id = f"test_pattern_{uuid4().hex[:8]}"
    child2_id = f"test_pattern_{uuid4().hex[:8]}"

    # Create parent
    await lineage_tracker.execute_effect(
        ModelPatternLineageInput(
            name="test_parent_for_descendants",
            operation="track_creation",
            pattern_id=parent_id,
            pattern_name="Parent",
            pattern_version="1.0.0",
            pattern_data={"code": "parent"},
        )
    )

    # Create children
    for child_id in [child1_id, child2_id]:
        await lineage_tracker.execute_effect(
            ModelPatternLineageInput(
                name=f"test_child_{child_id}",
                operation="track_modification",
                pattern_id=child_id,
                pattern_name=f"Child{child_id}",
                pattern_version="2.0.0",
                pattern_data={"code": f"child_{child_id}"},
                parent_pattern_ids=[parent_id],
                edge_type=EdgeType.MODIFIED_FROM,
            )
        )

    # Query descendants
    query_contract = ModelPatternLineageInput(
        operation="query_descendants", pattern_id=parent_id
    )

    result = await lineage_tracker.execute_effect(query_contract)

    assert result.success is True
    assert result.data["total_descendants"] == 2
    assert len(result.data["descendants"]) == 2


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_performance_track_creation(lineage_tracker, cleanup_test_data):
    """Test creation tracking meets <50ms performance target."""
    contract = ModelPatternLineageInput(
        name="test_perf_creation",
        operation="track_creation",
        pattern_id=f"test_perf_{uuid4().hex[:8]}",
        pattern_name="PerfTest",
        pattern_version="1.0.0",
        pattern_data={"code": "perf_test"},
    )

    result = await lineage_tracker.execute_effect(contract)

    assert result.success is True
    assert result.metadata["duration_ms"] < 50


@pytest.mark.asyncio
async def test_performance_query_ancestry(lineage_tracker, cleanup_test_data):
    """Test ancestry query meets <200ms performance target."""
    # Create multi-generation lineage
    pattern_ids = [f"test_perf_{uuid4().hex[:8]}" for _ in range(5)]

    # Create root
    await lineage_tracker.execute_effect(
        ModelPatternLineageInput(
            name="test_perf_root",
            operation="track_creation",
            pattern_id=pattern_ids[0],
            pattern_name="Root",
            pattern_version="1.0.0",
            pattern_data={"gen": 0},
        )
    )

    # Create chain
    for i in range(1, 5):
        await lineage_tracker.execute_effect(
            ModelPatternLineageInput(
                name=f"test_perf_gen{i}",
                operation="track_modification",
                pattern_id=pattern_ids[i],
                pattern_name=f"Gen{i}",
                pattern_version=f"{i+1}.0.0",
                pattern_data={"gen": i},
                parent_pattern_ids=[pattern_ids[i - 1]],
                edge_type=EdgeType.MODIFIED_FROM,
            )
        )

    # Query ancestry of last pattern
    query_contract = ModelPatternLineageInput(
        operation="query_ancestry", pattern_id=pattern_ids[-1]
    )

    result = await lineage_tracker.execute_effect(query_contract)

    assert result.success is True
    assert result.metadata["duration_ms"] < 200


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
async def test_error_handling_unsupported_operation(lineage_tracker):
    """Test error handling for unsupported operation."""
    contract = ModelPatternLineageInput(
        name="test_invalid_op", operation="invalid_operation", pattern_id="test_pattern"
    )

    result = await lineage_tracker.execute_effect(contract)

    assert result.success is False
    assert "unsupported operation" in result.error.lower()


@pytest.mark.asyncio
async def test_error_handling_missing_pattern_id(lineage_tracker):
    """Test error handling for missing pattern_id in query."""
    contract = ModelPatternLineageInput(
        operation="query_ancestry", pattern_id="nonexistent_pattern_id"
    )

    result = await lineage_tracker.execute_effect(contract)

    assert result.success is False
    assert "not found" in result.error.lower()


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_full_lineage_lifecycle(lineage_tracker, cleanup_test_data):
    """Test complete lineage lifecycle from creation to query."""
    base_id = uuid4().hex[:8]

    # 1. Create root pattern
    root_id = f"test_{base_id}_root"
    create_result = await lineage_tracker.execute_effect(
        ModelPatternLineageInput(
            name="test_lifecycle_root",
            operation="track_creation",
            pattern_id=root_id,
            pattern_name="RootPattern",
            pattern_version="1.0.0",
            pattern_data={"code": "root"},
        )
    )
    assert create_result.success is True

    # 2. Modify pattern
    mod_id = f"test_{base_id}_mod"
    mod_result = await lineage_tracker.execute_effect(
        ModelPatternLineageInput(
            name="test_lifecycle_modification",
            operation="track_modification",
            pattern_id=mod_id,
            pattern_name="ModifiedPattern",
            pattern_version="2.0.0",
            pattern_data={"code": "modified"},
            parent_pattern_ids=[root_id],
            edge_type=EdgeType.MODIFIED_FROM,
            transformation_type=TransformationType.ENHANCEMENT,
        )
    )
    assert mod_result.success is True

    # 3. Apply pattern
    apply_result = await lineage_tracker.execute_effect(
        ModelPatternLineageInput(
            name="test_lifecycle_application",
            operation="track_application",
            pattern_id=mod_id,
            metadata={"context": "production"},
        )
    )
    assert apply_result.success is True

    # 4. Query ancestry
    ancestry_result = await lineage_tracker.execute_effect(
        ModelPatternLineageInput(
            name="test_lifecycle_ancestry_query",
            operation="query_ancestry",
            pattern_id=mod_id,
        )
    )
    assert ancestry_result.success is True
    assert ancestry_result.data["ancestry_depth"] == 1
    assert ancestry_result.data["total_ancestors"] == 1

    # 5. Query descendants of root
    descendants_result = await lineage_tracker.execute_effect(
        ModelPatternLineageInput(
            name="test_lifecycle_descendants_query",
            operation="query_descendants",
            pattern_id=root_id,
        )
    )
    assert descendants_result.success is True
    assert descendants_result.data["total_descendants"] == 1

    # 6. Deprecate pattern
    deprecate_result = await lineage_tracker.execute_effect(
        ModelPatternLineageInput(
            name="test_lifecycle_deprecation",
            operation="track_deprecation",
            pattern_id=mod_id,
            reason="Replaced by newer version",
        )
    )
    assert deprecate_result.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
