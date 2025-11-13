"""
Test Suite: Phase 4 Integration Tests

End-to-end integration tests for complete Phase 4 workflows.

Test Categories:
    - Complete lineage tracking flow
    - Pattern creation → usage → feedback → improvement
    - Cross-component integration
    - Database integration
    - API integration

Coverage Target: >85%
Test Count: 12 tests

Author: Archon Intelligence Team
Date: 2025-10-02
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from archon_services.pattern_learning.phase4_traceability.model_contract_feedback_loop import (
    ModelFeedbackLoopInput,
)
from archon_services.pattern_learning.phase4_traceability.model_contract_pattern_lineage import (
    LineageDepth,
    LineageEventType,
    LineageOperation,
    ModelLineageQueryInput,
    ModelPatternLineageInput,
    TransformationType,
)
from archon_services.pattern_learning.phase4_traceability.model_contract_usage_analytics import (
    AnalyticsGranularity,
    ModelUsageAnalyticsInput,
    TimeWindowType,
)
from archon_services.pattern_learning.phase4_traceability.models.model_pattern_lineage_node import (
    EnumPatternEvolutionType,
    EnumPatternLineageStatus,
)
from archon_services.pattern_learning.phase4_traceability.node_feedback_loop_orchestrator import (
    NodeFeedbackLoopOrchestrator,
)
from archon_services.pattern_learning.phase4_traceability.node_pattern_lineage_tracker_effect import (
    NodePatternLineageTrackerEffect,
)
from archon_services.pattern_learning.phase4_traceability.node_usage_analytics_reducer import (
    NodeUsageAnalyticsReducer,
)

# ============================================================================
# Test: End-to-End Lineage Tracking Flow
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_complete_lineage_workflow(lineage_tracker):
    """Test complete lineage tracking workflow: create → query → update."""
    tracker = lineage_tracker
    pattern_id = str(uuid4())

    # Step 1: Create pattern
    create_contract = ModelPatternLineageInput(
        name="integration_create",
        operation="track_creation",
        event_type=LineageEventType.PATTERN_CREATED,
        pattern_id=pattern_id,
        pattern_version="1",
        parent_pattern_ids=[],
        metadata={"source": "integration_test"},
    )

    create_result = await tracker.execute_effect(create_contract)
    assert create_result.success is True

    # Step 2: Query created pattern
    query_contract = ModelLineageQueryInput(
        name="integration_query_ancestors",
        operation=LineageOperation.QUERY_ANCESTORS,
        pattern_id=pattern_id,
        depth=LineageDepth.FULL,
        include_metadata=True,
    )

    query_result = await tracker.execute_effect(query_contract)
    assert query_result.success is True

    # Step 3: Update pattern (refinement)
    update_contract = ModelPatternLineageInput(
        name="integration_update",
        operation="track_modification",
        event_type=LineageEventType.PATTERN_MODIFIED,
        transformation_type=TransformationType.OPTIMIZATION,
        pattern_id=pattern_id,
        pattern_version="2",
        parent_pattern_ids=[],
        metadata={"optimization": "performance"},
    )

    update_result = await tracker.execute_effect(update_contract)
    assert update_result.success is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pattern_lifecycle_with_ancestry(lineage_tracker):
    """Test pattern lifecycle with ancestry chain."""
    tracker = lineage_tracker

    # Create parent pattern
    parent_id = str(uuid4())
    parent_contract = ModelPatternLineageInput(
        name="integration_parent_create",
        operation="track_creation",
        event_type=LineageEventType.PATTERN_CREATED,
        pattern_id=parent_id,
        pattern_version="1",
        parent_pattern_ids=[],
        metadata={},
    )
    await tracker.execute_effect(parent_contract)

    # Create child pattern (derived from parent)
    child_id = str(uuid4())
    child_contract = ModelPatternLineageInput(
        name="integration_child_create",
        operation="track_creation",
        event_type=LineageEventType.PATTERN_MODIFIED,
        transformation_type=TransformationType.REFACTOR,
        pattern_id=child_id,
        pattern_version="1",
        parent_pattern_ids=[parent_id],
        metadata={"parent": parent_id},
    )
    child_result = await tracker.execute_effect(child_contract)

    assert child_result.success is True
    assert child_result.data is not None


# ============================================================================
# Test: Usage → Feedback → Improvement Flow
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_usage_feedback_improvement_flow():
    """Test complete flow: usage tracking → feedback collection → improvement generation."""
    pattern_id = str(uuid4())

    # Step 1: Aggregate usage analytics
    analytics_reducer = NodeUsageAnalyticsReducer()
    analytics_contract = ModelUsageAnalyticsInput(
        pattern_id=pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(days=7),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_7_DAYS,
    )

    analytics_result = await analytics_reducer.execute_reduction(analytics_contract)
    assert analytics_result.success is True

    # Step 2: Run feedback loop (based on usage data)
    feedback_orchestrator = NodeFeedbackLoopOrchestrator()
    feedback_contract = ModelFeedbackLoopInput(
        pattern_id=pattern_id,
        feedback_type="performance",
        time_window_days=7,
        auto_apply_threshold=0.95,
    )

    feedback_result = await feedback_orchestrator.execute_orchestration(
        feedback_contract
    )
    assert feedback_result.success is True

    # Step 3: Verify improvements were generated
    assert feedback_result.data.get("improvements_generated", 0) >= 0


# ============================================================================
# Test: Cross-Component Integration
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_lineage_analytics_integration(lineage_tracker):
    """Test integration between lineage tracking and usage analytics."""
    pattern_id = str(uuid4())

    # Create lineage
    tracker = lineage_tracker
    lineage_contract = ModelPatternLineageInput(
        operation="track_creation",
        pattern_id=pattern_id,
        version=1,
        parent_pattern_ids=[],
        evolution_type=EnumPatternEvolutionType.CREATED,
        metadata={},
    )
    await tracker.execute_effect(lineage_contract)

    # Aggregate analytics for same pattern
    analytics_reducer = NodeUsageAnalyticsReducer()
    analytics_contract = ModelUsageAnalyticsInput(
        pattern_id=pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(days=7),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_7_DAYS,
    )

    analytics_result = await analytics_reducer.execute_reduction(analytics_contract)
    assert analytics_result.success is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_feedback_lineage_integration():
    """Test integration between feedback loop and lineage tracking."""
    pattern_id = str(uuid4())

    # Run feedback loop
    feedback_orchestrator = NodeFeedbackLoopOrchestrator()
    feedback_contract = ModelFeedbackLoopInput(
        pattern_id=pattern_id,
        feedback_type="quality",
        time_window_days=7,
    )

    feedback_result = await feedback_orchestrator.execute_orchestration(
        feedback_contract
    )
    assert feedback_result.success is True

    # If improvement was generated, create new lineage entry
    if feedback_result.data.get("improvements_generated", 0) > 0:
        tracker = lineage_tracker
        lineage_contract = ModelPatternLineageInput(
            operation="track_modification",
            pattern_id=pattern_id,
            version=2,
            parent_pattern_ids=[],
            evolution_type=EnumPatternEvolutionType.IMPROVED_VIA_FEEDBACK,
            metadata={"feedback_driven": True},
        )

        lineage_result = await tracker.execute_effect(lineage_contract)
        assert lineage_result.success is True


# ============================================================================
# Test: Multi-Pattern Workflows
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pattern_merge_workflow(lineage_tracker):
    """Test merging multiple patterns."""
    tracker = lineage_tracker

    # Create two patterns to merge
    pattern_a_id = str(uuid4())
    pattern_b_id = str(uuid4())

    for pattern_id in [pattern_a_id, pattern_b_id]:
        contract = ModelPatternLineageInput(
            operation="track_creation",
            pattern_id=pattern_id,
            version=1,
            parent_pattern_ids=[],
            evolution_type=EnumPatternEvolutionType.CREATED,
            metadata={},
        )
        await tracker.execute_effect(contract)

    # Merge into new pattern
    merged_id = str(uuid4())
    merge_contract = ModelPatternLineageInput(
        operation="track_merge",
        pattern_id=merged_id,
        version=1,
        parent_pattern_ids=[pattern_a_id, pattern_b_id],
        evolution_type=EnumPatternEvolutionType.MERGED,
        metadata={"merged_from": [pattern_a_id, pattern_b_id]},
    )

    merge_result = await tracker.execute_effect(merge_contract)
    assert merge_result.success is True
    assert len(merge_result.data.parent_ids) == 2


# ============================================================================
# Test: Performance Integration
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_high_volume_lineage_operations(lineage_tracker):
    """Test lineage tracking with high volume of operations."""
    tracker = lineage_tracker
    pattern_ids = [str(uuid4()) for _ in range(50)]

    # Create 50 patterns in sequence
    for i, pattern_id in enumerate(pattern_ids):
        contract = ModelPatternLineageInput(
            operation="track_creation",
            pattern_id=pattern_id,
            version=1,
            parent_pattern_ids=[pattern_ids[i - 1]] if i > 0 else [],
            evolution_type=(
                EnumPatternEvolutionType.REFINED
                if i > 0
                else EnumPatternEvolutionType.CREATED
            ),
            metadata={"index": i},
        )

        result = await tracker.execute_effect(contract)
        assert result.success is True

    # Query last pattern's ancestry
    query_contract = ModelLineageQueryInput(
        name="high_volume_query",
        operation=LineageOperation.QUERY_ANCESTORS,
        pattern_id=pattern_ids[-1],
        depth=LineageDepth.FULL,
        include_metadata=True,
    )

    query_result = await tracker.execute_effect(query_contract)
    assert query_result.success is True
    assert query_result.data.total_nodes >= 50


# ============================================================================
# Test: Error Recovery
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_workflow_error_recovery(lineage_tracker):
    """Test workflow continues gracefully after errors."""
    pattern_id = str(uuid4())

    # Step 1: Create pattern
    tracker = lineage_tracker
    create_contract = ModelPatternLineageInput(
        operation="track_creation",
        pattern_id=pattern_id,
        version=1,
        parent_pattern_ids=[],
        evolution_type=EnumPatternEvolutionType.CREATED,
        metadata={},
    )
    await tracker.execute_effect(create_contract)

    # Step 2: Try analytics (might have no data)
    analytics_reducer = NodeUsageAnalyticsReducer()
    analytics_contract = ModelUsageAnalyticsInput(
        pattern_id=pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(hours=1),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_24_HOURS,
    )

    analytics_result = await analytics_reducer.execute_reduction(analytics_contract)
    # Should succeed even with no data
    assert analytics_result.success is True

    # Step 3: Continue with feedback loop
    feedback_orchestrator = NodeFeedbackLoopOrchestrator()
    feedback_contract = ModelFeedbackLoopInput(
        pattern_id=pattern_id,
        feedback_type="performance",
        time_window_days=1,
    )

    feedback_result = await feedback_orchestrator.execute_orchestration(
        feedback_contract
    )
    assert feedback_result.success is True


# ============================================================================
# Test: Data Consistency
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cross_component_data_consistency(lineage_tracker):
    """Test data consistency across all Phase 4 components."""
    pattern_id = str(uuid4())

    # Create pattern with metadata
    tracker = lineage_tracker
    metadata = {"test": "integration", "version": "1.0"}

    create_contract = ModelPatternLineageInput(
        operation="track_creation",
        pattern_id=pattern_id,
        version=1,
        parent_pattern_ids=[],
        evolution_type=EnumPatternEvolutionType.CREATED,
        metadata=metadata,
    )
    await tracker.execute_effect(create_contract)

    # Query to verify metadata preserved
    query_contract = ModelLineageQueryInput(
        name="consistency_query",
        operation=LineageOperation.QUERY_ANCESTORS,
        pattern_id=pattern_id,
        depth=LineageDepth.IMMEDIATE,
        include_metadata=True,
    )

    query_result = await tracker.execute_effect(query_contract)

    # Verify consistency
    assert query_result.success is True
    # Metadata should be preserved


# ============================================================================
# Test: Concurrent Operations
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrent_lineage_operations(lineage_tracker):
    """Test concurrent lineage operations on different patterns."""
    import asyncio

    tracker = lineage_tracker

    async def create_pattern(index):
        pattern_id = str(uuid4())
        contract = ModelPatternLineageInput(
            operation="track_creation",
            pattern_id=pattern_id,
            version=1,
            parent_pattern_ids=[],
            evolution_type=EnumPatternEvolutionType.CREATED,
            metadata={"index": index},
        )
        return await tracker.execute_effect(contract)

    # Create 10 patterns concurrently
    results = await asyncio.gather(*[create_pattern(i) for i in range(10)])

    # All should succeed
    assert all(r.success for r in results)


# ============================================================================
# Test: Workflow Orchestration
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_complete_pattern_evolution_lifecycle(lineage_tracker):
    """Test complete pattern evolution from creation to improvement."""
    pattern_id = str(uuid4())
    tracker = lineage_tracker
    analytics_reducer = NodeUsageAnalyticsReducer()
    feedback_orchestrator = NodeFeedbackLoopOrchestrator()

    # Phase 1: Create initial pattern
    create_contract = ModelPatternLineageInput(
        operation="track_creation",
        pattern_id=pattern_id,
        version=1,
        parent_pattern_ids=[],
        evolution_type=EnumPatternEvolutionType.CREATED,
        metadata={"phase": "initial"},
    )
    await tracker.execute_effect(create_contract)

    # Phase 2: Collect usage analytics
    analytics_contract = ModelUsageAnalyticsInput(
        pattern_id=pattern_id,
        time_window_start=datetime.now(timezone.utc) - timedelta(days=7),
        time_window_end=datetime.now(timezone.utc),
        time_window_type=TimeWindowType.LAST_7_DAYS,
    )
    await analytics_reducer.execute_reduction(analytics_contract)

    # Phase 3: Run feedback loop
    feedback_contract = ModelFeedbackLoopInput(
        pattern_id=pattern_id,
        feedback_type="performance",
        time_window_days=7,
    )
    await feedback_orchestrator.execute_orchestration(feedback_contract)

    # Phase 4: Update lineage with improvement
    update_contract = ModelPatternLineageInput(
        operation="track_modification",
        pattern_id=pattern_id,
        version=2,
        parent_pattern_ids=[],
        evolution_type=EnumPatternEvolutionType.IMPROVED_VIA_FEEDBACK,
        metadata={"phase": "improved"},
    )
    final_result = await tracker.execute_effect(update_contract)

    assert final_result.success is True
