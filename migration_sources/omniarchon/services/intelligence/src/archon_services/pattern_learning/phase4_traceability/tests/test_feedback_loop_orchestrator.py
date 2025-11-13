"""
Test Suite: NodeFeedbackLoopOrchestrator

Comprehensive tests for feedback loop orchestration with >85% coverage.

Author: Archon Intelligence Team
Date: 2025-10-02
Track: Track 3 Phase 4
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from ..models.model_pattern_feedback import (
    FeedbackSentiment,
    ImprovementStatus,
    ModelPatternFeedback,
    ModelPatternImprovement,
)
from ..node_feedback_loop_orchestrator import (
    ModelFeedbackLoopInput,
    NodeFeedbackLoopOrchestrator,
)


@pytest.fixture
def orchestrator():
    """Create orchestrator instance for testing."""
    return NodeFeedbackLoopOrchestrator()


@pytest.fixture
def sample_contract():
    """Create sample contract for testing."""
    return ModelFeedbackLoopInput(
        pattern_id="test_pattern_001",
        feedback_type="performance",
        time_window_days=7,
        auto_apply_threshold=0.95,
        min_sample_size=30,
        significance_level=0.05,
        enable_ab_testing=True,
    )


# ============================================================================
# Test: Orchestration Workflow
# ============================================================================


@pytest.mark.asyncio
async def test_execute_orchestration_success(orchestrator, sample_contract):
    """Test successful feedback loop orchestration."""
    result = await orchestrator.execute_orchestration(sample_contract)

    assert result.success is True
    assert result.data is not None
    assert "pattern_id" in result.data
    assert result.data["pattern_id"] == "test_pattern_001"
    assert result.data["feedback_collected"] > 0
    assert result.data["executions_analyzed"] > 0
    assert "workflow_stages" in result.data


@pytest.mark.asyncio
async def test_execute_orchestration_all_stages(orchestrator, sample_contract):
    """Test that all workflow stages are executed."""
    result = await orchestrator.execute_orchestration(sample_contract)

    workflow_stages = result.data["workflow_stages"]

    # All stages should be present
    assert "collect" in workflow_stages
    assert "analyze" in workflow_stages
    assert "validate" in workflow_stages or workflow_stages["validate"] == "skipped"
    assert "apply" in workflow_stages or workflow_stages["apply"] == "skipped"

    # Collect should always complete
    assert workflow_stages["collect"] == "completed"


@pytest.mark.asyncio
async def test_execute_orchestration_insufficient_feedback(orchestrator):
    """Test handling of insufficient feedback samples."""
    contract = ModelFeedbackLoopInput(
        pattern_id="pattern_no_data",
        feedback_type="performance",
        time_window_days=1,  # Very short window
        min_sample_size=1000,  # Impossibly high
    )

    result = await orchestrator.execute_orchestration(contract)

    # Should succeed but skip analysis
    assert result.success is True
    assert len(result.data.get("warnings", [])) > 0
    assert "Insufficient feedback items" in result.data["warnings"][0]


# ============================================================================
# Test: Feedback Collection
# ============================================================================


@pytest.mark.asyncio
async def test_collect_feedback(orchestrator):
    """Test feedback collection from Track 2 hooks."""
    feedback_items, executions = await orchestrator._collect_feedback(
        pattern_id="test_pattern",
        time_window_days=7,
        feedback_type="performance",
    )

    assert len(feedback_items) > 0
    assert len(executions) > 0
    assert len(feedback_items) == len(executions)

    # Check feedback structure
    for fb in feedback_items:
        assert isinstance(fb, ModelPatternFeedback)
        assert fb.sentiment in [
            FeedbackSentiment.POSITIVE,
            FeedbackSentiment.NEUTRAL,
            FeedbackSentiment.NEGATIVE,
        ]


@pytest.mark.asyncio
async def test_determine_sentiment(orchestrator):
    """Test sentiment determination from execution data."""
    # High quality/performance -> POSITIVE
    exec_high = {
        "status": "success",
        "quality_score": 0.95,
        "performance_score": 0.92,
    }
    sentiment = orchestrator._determine_sentiment(exec_high)
    assert sentiment == FeedbackSentiment.POSITIVE

    # Medium quality/performance -> NEUTRAL
    exec_medium = {
        "status": "success",
        "quality_score": 0.80,
        "performance_score": 0.75,
    }
    sentiment = orchestrator._determine_sentiment(exec_medium)
    assert sentiment == FeedbackSentiment.NEUTRAL

    # Failed execution -> NEGATIVE
    exec_failed = {"status": "failed", "quality_score": 0.5, "performance_score": 0.5}
    sentiment = orchestrator._determine_sentiment(exec_failed)
    assert sentiment == FeedbackSentiment.NEGATIVE


# ============================================================================
# Test: Analysis and Improvement Generation
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_and_generate_improvements(orchestrator):
    """Test improvement generation from feedback analysis."""
    # Create feedback with performance issues
    feedback_items = []
    for i in range(50):
        fb = ModelPatternFeedback(
            pattern_id=uuid4(),
            execution_id=uuid4(),
            sentiment=FeedbackSentiment.NEUTRAL,
            implicit_signals={"execution_time_ms": 500 + i * 10},  # Slow execution
            success=True,
            quality_score=0.80,
        )
        feedback_items.append(fb)

    improvements = await orchestrator._analyze_and_generate_improvements(
        pattern_id="test_pattern",
        feedback_items=feedback_items,
        executions=[],
    )

    # Should identify performance improvement opportunity
    assert len(improvements) > 0
    assert any(imp.improvement_type == "performance" for imp in improvements)


@pytest.mark.asyncio
async def test_improvement_generation_quality_issues(orchestrator):
    """Test improvement generation for quality issues."""
    # Create feedback with quality issues
    feedback_items = []
    for i in range(50):
        fb = ModelPatternFeedback(
            pattern_id=uuid4(),
            execution_id=uuid4(),
            sentiment=FeedbackSentiment.NEUTRAL,
            implicit_signals={"execution_time_ms": 300},
            success=True,
            quality_score=0.70,  # Low quality
        )
        feedback_items.append(fb)

    improvements = await orchestrator._analyze_and_generate_improvements(
        pattern_id="test_pattern",
        feedback_items=feedback_items,
        executions=[],
    )

    # Should identify quality improvement opportunity
    assert len(improvements) > 0
    assert any(imp.improvement_type == "quality" for imp in improvements)


# ============================================================================
# Test: A/B Testing Validation
# ============================================================================


@pytest.mark.asyncio
async def test_validate_improvements_ab_testing(orchestrator):
    """Test A/B testing validation."""
    improvement = ModelPatternImprovement(
        pattern_id=uuid4(),
        improvement_type="performance",
        description="Add caching",
        baseline_metrics={
            "avg_execution_time_ms": 450.0,
            "std_execution_time_ms": 50.0,
        },
        performance_delta=0.60,
    )

    validated = await orchestrator._validate_improvements(
        pattern_id="test_pattern",
        improvements=[improvement],
        significance_level=0.05,
        min_sample_size=30,
    )

    assert len(validated) > 0
    imp = validated[0]

    # Should have statistical results
    assert imp.p_value is not None
    assert imp.confidence_score > 0
    assert imp.sample_size >= 30
    assert imp.status in [ImprovementStatus.VALIDATED, ImprovementStatus.REJECTED]


@pytest.mark.asyncio
async def test_run_ab_test(orchestrator):
    """Test A/B test execution."""
    improvement = ModelPatternImprovement(
        pattern_id=uuid4(),
        improvement_type="performance",
        description="Test improvement",
        baseline_metrics={
            "avg_execution_time_ms": 500.0,
            "std_execution_time_ms": 50.0,
        },
        performance_delta=0.50,
    )

    control, treatment = await orchestrator._run_ab_test(
        pattern_id="test_pattern",
        improvement=improvement,
        sample_size=50,
    )

    assert len(control) == 50
    assert len(treatment) == 50

    # Treatment should be faster on average (due to 50% improvement)
    from statistics import mean

    assert mean(treatment) < mean(control)


@pytest.mark.asyncio
async def test_statistical_significance(orchestrator):
    """Test statistical significance calculation."""
    improvement = ModelPatternImprovement(
        pattern_id=uuid4(),
        improvement_type="performance",
        description="Significant improvement",
        baseline_metrics={
            "avg_execution_time_ms": 500.0,
            "std_execution_time_ms": 50.0,
        },
        performance_delta=0.70,  # Large improvement
    )

    validated = await orchestrator._validate_improvements(
        pattern_id="test_pattern",
        improvements=[improvement],
        significance_level=0.05,
        min_sample_size=30,
    )

    # Large improvement should be statistically significant
    assert len(validated) > 0
    imp = validated[0]
    assert imp.p_value < 0.05
    assert imp.status == ImprovementStatus.VALIDATED


# ============================================================================
# Test: Apply Improvements
# ============================================================================


@pytest.mark.asyncio
async def test_apply_improvements_high_confidence(orchestrator):
    """Test applying improvements with high confidence."""
    improvement = ModelPatternImprovement(
        pattern_id=uuid4(),
        improvement_type="performance",
        description="High confidence improvement",
        confidence_score=0.98,  # Very high confidence
        p_value=0.001,
        status=ImprovementStatus.VALIDATED,
    )

    applied, rejected = await orchestrator._apply_improvements(
        pattern_id="test_pattern",
        improvements=[improvement],
        auto_apply_threshold=0.95,
    )

    assert len(applied) == 1
    assert len(rejected) == 0
    assert applied[0].status == ImprovementStatus.APPLIED
    assert applied[0].applied_at is not None


@pytest.mark.asyncio
async def test_apply_improvements_low_confidence(orchestrator):
    """Test rejecting improvements with low confidence."""
    improvement = ModelPatternImprovement(
        pattern_id=uuid4(),
        improvement_type="performance",
        description="Low confidence improvement",
        confidence_score=0.85,  # Below threshold
        p_value=0.15,
        status=ImprovementStatus.VALIDATED,
    )

    applied, rejected = await orchestrator._apply_improvements(
        pattern_id="test_pattern",
        improvements=[improvement],
        auto_apply_threshold=0.95,
    )

    assert len(applied) == 0
    assert len(rejected) == 1
    assert rejected[0].status == ImprovementStatus.REJECTED


# ============================================================================
# Test: Lineage Tracking
# ============================================================================


@pytest.mark.asyncio
async def test_update_lineage(orchestrator):
    """Test lineage graph update."""
    improvement = ModelPatternImprovement(
        pattern_id=uuid4(),
        improvement_type="performance",
        description="Test improvement",
        applied_at=datetime.now(timezone.utc),
    )

    # Initial graph should be empty
    initial_node_count = len(orchestrator.lineage_graph.nodes)
    initial_edge_count = len(orchestrator.lineage_graph.edges)

    await orchestrator._update_lineage(
        pattern_id="test_pattern",
        improvement=improvement,
    )

    # Should add one node and one edge
    assert len(orchestrator.lineage_graph.nodes) == initial_node_count + 1
    assert len(orchestrator.lineage_graph.edges) == initial_edge_count + 1


# ============================================================================
# Test: Metrics Calculation
# ============================================================================


def test_calculate_baseline_metrics(orchestrator):
    """Test baseline metrics calculation."""
    feedback_items = [
        ModelPatternFeedback(
            pattern_id=uuid4(),
            execution_id=uuid4(),
            sentiment=FeedbackSentiment.POSITIVE,
            implicit_signals={"execution_time_ms": 400},
            success=True,
            quality_score=0.90,
        )
        for _ in range(10)
    ]

    metrics = orchestrator._calculate_baseline_metrics(feedback_items)

    assert "avg_execution_time_ms" in metrics
    assert "median_execution_time_ms" in metrics
    assert "avg_quality_score" in metrics
    assert "success_rate" in metrics
    assert metrics["success_rate"] == 1.0  # All successful


def test_calculate_improved_metrics(orchestrator):
    """Test improved metrics calculation."""
    baseline = {
        "avg_execution_time_ms": 500.0,
        "avg_quality_score": 0.80,
        "success_rate": 0.85,
    }

    improvements = [
        ModelPatternImprovement(
            pattern_id=uuid4(),
            improvement_type="performance",
            description="Performance boost",
            performance_delta=0.60,  # 60% faster
        )
    ]

    improved = orchestrator._calculate_improved_metrics(improvements, baseline)

    # Performance should improve
    assert improved["avg_execution_time_ms"] < baseline["avg_execution_time_ms"]
    assert improved["avg_execution_time_ms"] == 500.0 * (1 - 0.60)


# ============================================================================
# Test: Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_orchestration_error_handling(orchestrator):
    """Test error handling in orchestration."""
    # Test with invalid pattern_id
    contract = ModelFeedbackLoopInput(
        pattern_id="",  # Empty pattern ID
        feedback_type="performance",
    )

    # Should handle gracefully (may succeed or fail depending on validation)
    result = await orchestrator.execute_orchestration(contract)
    assert result is not None


# ============================================================================
# Test: Performance
# ============================================================================


@pytest.mark.asyncio
async def test_orchestration_performance(orchestrator, sample_contract):
    """Test that orchestration completes within performance targets."""
    import time

    start = time.time()
    result = await orchestrator.execute_orchestration(sample_contract)
    duration_s = time.time() - start

    # Should complete within 60 seconds (excluding A/B test wait time)
    assert duration_s < 60
    assert result.success is True


# ============================================================================
# Test: Integration
# ============================================================================


@pytest.mark.asyncio
async def test_full_workflow_integration(orchestrator):
    """Test complete end-to-end workflow."""
    contract = ModelFeedbackLoopInput(
        pattern_id="integration_test_pattern",
        feedback_type="all",
        time_window_days=7,
        auto_apply_threshold=0.90,  # Lower threshold for testing
        min_sample_size=30,
        enable_ab_testing=True,
    )

    result = await orchestrator.execute_orchestration(contract)

    # Should complete successfully
    assert result.success is True
    assert result.data["feedback_collected"] > 0

    # Workflow should progress through stages
    workflow_stages = result.data["workflow_stages"]
    assert workflow_stages["collect"] == "completed"

    # If sufficient feedback, should analyze
    if result.data["feedback_collected"] >= contract.min_sample_size:
        assert workflow_stages["analyze"] == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
