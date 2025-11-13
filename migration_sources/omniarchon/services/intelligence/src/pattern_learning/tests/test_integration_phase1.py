"""
Integration Tests for Pattern Learning Phase 1 Foundation

End-to-end integration tests covering:
- Full pattern lifecycle (insert → usage → analytics)
- Pattern relationships
- Trigger behavior (auto-update stats)
- Multi-node workflows

Target coverage: >85% integration scenarios

Track: Track 3-1.5 - Comprehensive Test Suite Generation
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from ..node_pattern_analytics_effect import ModelContractEffect as AnalyticsContract
from ..node_pattern_query_effect import ModelContractEffect as QueryContract
from ..node_pattern_storage_effect import ModelContractEffect as StorageContract
from ..node_pattern_update_effect import ModelContractEffect as UpdateContract

# ============================================================================
# Integration Test: Full Pattern Lifecycle
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
# NOTE: correlation_id support enabled for tracing
async def test_full_pattern_lifecycle_with_analytics(
    storage_node, query_node, update_node, analytics_node, initialized_db
):
    """
    Integration test for complete pattern lifecycle:
    1. Insert pattern
    2. Record usage events
    3. Verify trigger updates stats
    4. Compute analytics
    5. Query pattern and trends
    """

    # Step 1: Insert a pattern
    pattern_data = {
        "pattern_name": f"LifecyclePattern_{uuid4().hex[:8]}",
        "pattern_type": "code",
        "language": "python",
        "category": "database",
        "template_code": "async def execute_effect(self, contract): pass",
        "description": "ONEX Effect pattern for lifecycle testing",
        "confidence_score": 0.90,
        "tags": ["onex", "effect", "integration"],
    }

    insert_contract = StorageContract(operation="insert", data=pattern_data)
    insert_result = await storage_node.execute_effect(insert_contract)

    assert insert_result.success is True
    pattern_id = UUID(insert_result.data["pattern_id"])

    # Step 2: Record multiple usage events
    usage_events = [
        {
            "success": True,
            "quality_before": 0.5,
            "quality_after": 0.7,
            "execution_time_ms": 100,
        },
        {
            "success": True,
            "quality_before": 0.6,
            "quality_after": 0.8,
            "execution_time_ms": 95,
        },
        {
            "success": False,
            "quality_before": 0.55,
            "quality_after": 0.5,
            "execution_time_ms": 120,
            "error_message": "Test error",
        },
        {
            "success": True,
            "quality_before": 0.7,
            "quality_after": 0.9,
            "execution_time_ms": 85,
        },
        {
            "success": True,
            "quality_before": 0.65,
            "quality_after": 0.85,
            "execution_time_ms": 90,
        },
    ]

    for i, event_data in enumerate(usage_events):
        usage_contract = UpdateContract(
            operation="record_usage",
            pattern_id=pattern_id,
            usage_data={
                "file_path": f"/project/module_{i}.py",
                "project_id": str(uuid4()),
                "success": event_data["success"],
                "execution_time_ms": event_data["execution_time_ms"],
                "error_message": event_data.get("error_message"),
                "quality_before": event_data["quality_before"],
                "quality_after": event_data["quality_after"],
                "tags": ["integration_test"],
            },
        )

        usage_result = await update_node.execute_effect(usage_contract)
        assert usage_result.success is True
        assert "event_id" in usage_result.data

    # Step 3: Verify trigger updated pattern stats
    async with initialized_db as conn:
        pattern_stats = await conn.fetchrow(
            "SELECT usage_count, success_rate, last_used_at FROM pattern_templates WHERE id = $1",
            pattern_id,
        )

    assert pattern_stats["usage_count"] == 5
    assert float(pattern_stats["success_rate"]) == 0.8  # 4 successes out of 5
    assert pattern_stats["last_used_at"] is not None

    # Step 4: Compute analytics
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=1)

    analytics_contract = AnalyticsContract(
        operation="compute_analytics",
        pattern_id=pattern_id,
        period_start=period_start,
        period_end=period_end,
    )

    analytics_result = await analytics_node.execute_effect(analytics_contract)

    assert analytics_result.success is True
    assert analytics_result.data["total_usage_count"] == 5
    assert analytics_result.data["success_count"] == 4
    assert analytics_result.data["failure_count"] == 1
    assert analytics_result.data["success_rate"] == 0.8

    # Step 5: Query pattern and verify usage trends
    query_contract = QueryContract(operation="get_by_id", pattern_id=pattern_id)

    query_result = await query_node.execute_effect(query_contract)

    assert query_result.success is True
    assert query_result.data["id"] == pattern_id
    assert query_result.data["pattern_name"] == pattern_data["pattern_name"]
    assert float(query_result.data["success_rate"]) == 0.8

    # Get usage trends
    trends_contract = AnalyticsContract(
        operation="get_usage_trends",
        pattern_id=pattern_id,
        period_start=period_start,
        aggregate_by="day",
    )

    trends_result = await analytics_node.execute_effect(trends_contract)

    assert trends_result.success is True
    assert len(trends_result.data) > 0


# ============================================================================
# Integration Test: Pattern Relationships
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pattern_relationship_workflow(
    storage_node, query_node, update_node, initialized_db
):
    """
    Integration test for pattern relationships:
    1. Insert two patterns
    2. Create relationship between them
    3. Query related patterns
    """

    # Step 1: Insert two patterns
    pattern1_data = {
        "pattern_name": f"RelPattern1_{uuid4().hex[:8]}",
        "pattern_type": "code",
        "language": "python",
        "template_code": "async def pattern1(): pass",
        "confidence_score": 0.85,
    }

    pattern2_data = {
        "pattern_name": f"RelPattern2_{uuid4().hex[:8]}",
        "pattern_type": "code",
        "language": "python",
        "template_code": "async def pattern2(): pass",
        "confidence_score": 0.90,
    }

    result1 = await storage_node.execute_effect(
        StorageContract(operation="insert", data=pattern1_data)
    )
    result2 = await storage_node.execute_effect(
        StorageContract(operation="insert", data=pattern2_data)
    )

    assert result1.success and result2.success
    pattern1_id = UUID(result1.data["pattern_id"])
    pattern2_id = UUID(result2.data["pattern_id"])

    # Step 2: Create relationship
    relationship_contract = UpdateContract(
        operation="create_relationship",
        relationship_data={
            "source_pattern_id": str(pattern1_id),
            "target_pattern_id": str(pattern2_id),
            "relationship_type": "similar",
            "strength": 0.75,
            "description": "Integration test relationship",
            "context": {"test": True},
        },
    )

    rel_result = await update_node.execute_effect(relationship_contract)

    assert rel_result.success is True
    assert "relationship_id" in rel_result.data
    assert rel_result.data["relationship_type"] == "similar"

    # Step 3: Query related patterns
    related_contract = QueryContract(
        operation="get_related", pattern_id=pattern1_id, limit=10
    )

    related_result = await query_node.execute_effect(related_contract)

    assert related_result.success is True
    assert len(related_result.data) == 1
    assert UUID(related_result.data[0]["id"]) == pattern2_id
    assert related_result.data[0]["relationship_type"] == "similar"
    assert float(related_result.data[0]["strength"]) == 0.75


# ============================================================================
# Integration Test: Deprecation Impact
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pattern_deprecation_workflow(
    storage_node, query_node, update_node, analytics_node, initialized_db
):
    """
    Integration test for pattern deprecation:
    1. Insert pattern and record usage
    2. Deprecate the pattern
    3. Verify it doesn't appear in top patterns view
    4. Verify historical analytics still available
    """

    # Step 1: Insert pattern and record usage
    pattern_data = {
        "pattern_name": f"DeprecationPattern_{uuid4().hex[:8]}",
        "pattern_type": "code",
        "language": "python",
        "template_code": "def old_pattern(): pass",
        "confidence_score": 0.95,
    }

    insert_result = await storage_node.execute_effect(
        StorageContract(operation="insert", data=pattern_data)
    )

    pattern_id = UUID(insert_result.data["pattern_id"])

    # Record usage
    for _ in range(3):
        await update_node.execute_effect(
            UpdateContract(
                operation="record_usage",
                pattern_id=pattern_id,
                usage_data={
                    "success": True,
                    "execution_time_ms": 100,
                    "quality_before": 0.5,
                    "quality_after": 0.8,
                },
            )
        )

    # Step 2: Deprecate the pattern
    deprecate_result = await storage_node.execute_effect(
        StorageContract(
            operation="update", pattern_id=pattern_id, data={"is_deprecated": True}
        )
    )

    assert deprecate_result.success is True

    # Step 3: Verify not in top patterns
    async with initialized_db as conn:
        top_patterns = await conn.fetch(
            "SELECT * FROM v_top_patterns WHERE id = $1", pattern_id
        )
        assert len(top_patterns) == 0  # Deprecated patterns excluded from view

    # Step 4: Verify historical analytics still available
    effectiveness_result = await analytics_node.execute_effect(
        AnalyticsContract(operation="get_effectiveness", pattern_id=pattern_id)
    )

    assert effectiveness_result.success is True
    assert effectiveness_result.data["total_usage"] == 3


# ============================================================================
# Integration Test: Global Statistics
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_global_statistics_workflow(
    storage_node, update_node, analytics_node, initialized_db
):
    """
    Integration test for global statistics:
    1. Insert multiple patterns
    2. Record usage for some patterns
    3. Get global stats and verify aggregations
    """

    # Step 1: Insert patterns
    pattern_ids = []
    for i in range(5):
        data = {
            "pattern_name": f"GlobalStatsPattern_{i}_{uuid4().hex[:8]}",
            "pattern_type": "code",
            "language": "python",
            "template_code": f"def global_{i}(): pass",
            "confidence_score": 0.7 + (i * 0.05),
        }

        result = await storage_node.execute_effect(
            StorageContract(operation="insert", data=data)
        )
        pattern_ids.append(UUID(result.data["pattern_id"]))

    # Step 2: Record usage for first 3 patterns
    for pattern_id in pattern_ids[:3]:
        for _ in range(2):  # 2 events each
            await update_node.execute_effect(
                UpdateContract(
                    operation="record_usage",
                    pattern_id=pattern_id,
                    usage_data={
                        "success": True,
                        "execution_time_ms": 100,
                        "quality_before": 0.6,
                        "quality_after": 0.8,
                    },
                )
            )

    # Step 3: Get global stats
    global_stats_result = await analytics_node.execute_effect(
        AnalyticsContract(operation="get_global_stats")
    )

    assert global_stats_result.success is True
    assert global_stats_result.data["total_patterns"] >= 5
    assert global_stats_result.data["active_patterns"] >= 5
    assert global_stats_result.data["total_usage_events"] >= 6  # 3 patterns * 2 events
    assert global_stats_result.data["patterns_used"] >= 3
    assert "top_patterns" in global_stats_result.data


# ============================================================================
# Integration Test: Search and Filter
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_and_filter_workflow(storage_node, query_node, initialized_db):
    """
    Integration test for search and filter operations:
    1. Insert patterns with various tags and properties
    2. Search by text
    3. Filter by criteria
    4. Verify results match expectations
    """

    # Step 1: Insert patterns with specific tags
    base_tag = f"search_test_{uuid4().hex[:8]}"

    patterns_data = [
        {
            "pattern_name": f"SearchPattern_A_{uuid4().hex[:8]}",
            "pattern_type": "code",
            "language": "python",
            "category": "async",
            "template_code": "async def search_a(): pass",
            "confidence_score": 0.9,
            "tags": [base_tag, "async", "database"],
        },
        {
            "pattern_name": f"SearchPattern_B_{uuid4().hex[:8]}",
            "pattern_type": "code",
            "language": "python",
            "category": "sync",
            "template_code": "def search_b(): pass",
            "confidence_score": 0.7,
            "tags": [base_tag, "sync"],
        },
        {
            "pattern_name": f"SearchPattern_C_{uuid4().hex[:8]}",
            "pattern_type": "architecture",
            "language": "python",
            "category": "async",
            "template_code": "class SearchPatternC: pass",
            "confidence_score": 0.85,
            "tags": [base_tag, "async", "architecture"],
        },
    ]

    for data in patterns_data:
        result = await storage_node.execute_effect(
            StorageContract(operation="insert", data=data)
        )
        assert result.success is True

    # Step 2: Search by text
    search_result = await query_node.execute_effect(
        QueryContract(
            operation="search",
            search_query="SearchPattern",
            filters={"language": "python"},
            limit=10,
        )
    )

    assert search_result.success is True
    assert len(search_result.data) >= 3

    # Step 3: Filter by tags and confidence
    filter_result = await query_node.execute_effect(
        QueryContract(
            operation="filter",
            filters={
                "tags": [base_tag],
                "min_confidence_score": 0.8,
                "category": "async",
            },
            limit=10,
        )
    )

    assert filter_result.success is True
    assert len(filter_result.data) >= 2  # SearchPattern_A and SearchPattern_C


# ============================================================================
# Integration Test: Batch Operations
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_batch_insert_with_analytics(
    storage_node, analytics_node, initialized_db
):
    """
    Integration test for batch operations:
    1. Batch insert multiple patterns
    2. Verify all inserted correctly
    3. Verify global stats reflect the new patterns
    """

    # Step 1: Batch insert
    patterns = [
        {
            "pattern_name": f"BatchIntegration_{i}_{uuid4().hex[:8]}",
            "pattern_type": "code",
            "language": "typescript",
            "template_code": f"export function batch{i}() {{}}",
            "confidence_score": 0.75 + (i * 0.05),
            "tags": ["batch", "integration"],
        }
        for i in range(10)
    ]

    batch_result = await storage_node.execute_effect(
        StorageContract(operation="batch_insert", patterns=patterns)
    )

    assert batch_result.success is True
    assert batch_result.data["count"] == 10

    # Step 2: Verify all patterns in database
    async with initialized_db as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM pattern_templates WHERE language = $1", "typescript"
        )
        assert count >= 10

    # Step 3: Get global stats
    stats_result = await analytics_node.execute_effect(
        AnalyticsContract(operation="get_global_stats")
    )

    assert stats_result.success is True
    assert stats_result.data["total_patterns"] >= 10


# ============================================================================
# Coverage Summary Target: >85% integration scenarios
# ============================================================================
# Covered:
# - Full pattern lifecycle with analytics
# - Pattern relationships (create and query)
# - Deprecation workflow
# - Global statistics aggregation
# - Search and filter operations
# - Batch operations with verification
# - Trigger behavior (auto-update stats)
# - Multi-node workflows
# ============================================================================
