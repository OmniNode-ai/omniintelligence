#!/usr/bin/env python3
"""
Usage Examples for Phase 4 Lineage Models

Demonstrates practical usage patterns for pattern lineage tracking,
metrics collection, feedback processing, and event auditing.

Author: Archon Intelligence Team
Date: 2025-10-02
"""

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from src.archon_services.pattern_learning.phase4_traceability.models.model_lineage_edge import (
    EnumEdgeStrength,
    EnumLineageRelationshipType,
    ModelLineageEdge,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_lineage_event import (
    ModelLineageEvent,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_pattern_feedback import (
    FeedbackSentiment,
    ImprovementStatus,
    ModelPatternFeedback,
    ModelPatternImprovement,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_pattern_lineage_node import (
    EnumPatternEvolutionType,
    ModelPatternLineageNode,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_pattern_metrics import (
    ModelPatternPerformanceMetrics,
    ModelPatternTrendAnalysis,
    ModelPatternUsageMetrics,
)

# ============================================================================
# Example 1: Creating a Pattern Evolution Chain
# ============================================================================


# NOTE: correlation_id support enabled for tracing
def example_pattern_evolution():
    """
    Example: Create a pattern evolution chain from v1 to v2.

    Demonstrates:
    - Creating root and child pattern nodes
    - Establishing evolution relationships
    - Recording usage metrics
    - Deprecating old versions
    """
    print("=" * 80)
    print("Example 1: Pattern Evolution Chain")
    print("=" * 80)

    # Create v1 pattern (root node)
    pattern_id_v1 = uuid4()
    node_v1 = ModelPatternLineageNode(
        pattern_id=pattern_id_v1,
        version=1,
        version_label="v1.0-stable",
        created_by="pattern_learning_engine",
        tags=["api", "debugging"],
    )
    node_v1.activate()
    print(f"\n✓ Created pattern v1: {node_v1.node_id}")
    print(f"  - Status: {node_v1.status.value}")
    print(f"  - Is root: {node_v1.is_root()}")

    # Record some usage for v1
    for _ in range(10):
        node_v1.record_usage(execution_time_ms=450.0, success=True)

    print(f"  - Usage count: {node_v1.usage_count}")
    print(f"  - Success rate: {node_v1.success_rate:.2%}")

    # Create v2 pattern (refined version)
    pattern_id_v2 = uuid4()
    node_v2 = ModelPatternLineageNode(
        pattern_id=pattern_id_v2,
        version=2,
        version_label="v2.0-optimized",
        created_by="pattern_learning_engine",
        parent_ids=[node_v1.node_id],
        evolution_type=EnumPatternEvolutionType.REFINEMENT,
        tags=["api", "debugging", "optimized"],
    )
    node_v2.activate()
    print(f"\n✓ Created pattern v2: {node_v2.node_id}")
    print(f"  - Parent: {node_v1.node_id}")
    print(f"  - Evolution type: {node_v2.evolution_type.value}")

    # Create evolution edge
    edge = ModelLineageEdge(
        source_node_id=node_v1.node_id,
        target_node_id=node_v2.node_id,
        source_pattern_id=pattern_id_v1,
        target_pattern_id=pattern_id_v2,
        relationship_type=EnumLineageRelationshipType.REFINED_FROM,
        edge_strength=EnumEdgeStrength.STRONG,
        similarity_score=0.85,
        confidence_score=0.95,
        change_summary="Improved performance by 40%",
        breaking_changes=False,
        created_by="pattern_learning_engine",
    )
    print(f"\n✓ Created evolution edge: {edge.edge_id}")
    print(f"  - Relationship: {edge.relationship_type.value}")
    print(f"  - Strength: {edge.edge_strength.value}")
    print(f"  - Weight: {edge.get_weight():.2f}")

    # Deprecate v1
    node_v1.deprecate(
        reason="Replaced by v2 with performance improvements",
        replaced_by=node_v2.node_id,
    )
    print("\n✓ Deprecated pattern v1")
    print(f"  - Reason: {node_v1.deprecated_reason}")
    print(f"  - Replaced by: {node_v1.replaced_by_node_id}")


# ============================================================================
# Example 2: Tracking Pattern Usage and Performance
# ============================================================================


def example_usage_tracking():
    """
    Example: Track pattern usage and performance metrics.

    Demonstrates:
    - Recording daily usage metrics
    - Capturing performance data
    - Analyzing trends
    """
    print("\n" + "=" * 80)
    print("Example 2: Usage and Performance Tracking")
    print("=" * 80)

    pattern_id = uuid4()

    # Daily usage metrics
    usage = ModelPatternUsageMetrics(
        pattern_id=pattern_id,
        pattern_name="api_debug_pattern",
        metrics_date=date.today(),
        execution_count=142,
        success_count=135,
        failure_count=7,
        success_rate=0.951,
        context_breakdown={
            "api_development": 89,
            "debugging": 42,
            "performance_testing": 11,
        },
        avg_execution_time_ms=450.5,
    )
    print(f"\n✓ Daily usage metrics for {usage.metrics_date}")
    print(f"  - Total executions: {usage.execution_count}")
    print(f"  - Success rate: {usage.success_rate:.1%}")
    print(f"  - Avg execution time: {usage.avg_execution_time_ms}ms")
    print(f"  - Context breakdown: {usage.context_breakdown}")

    # Performance metrics
    perf = ModelPatternPerformanceMetrics(
        pattern_id=pattern_id,
        pattern_name="api_debug_pattern",
        execution_time_ms=450.5,
        memory_usage_mb=125.3,
        cpu_usage_percent=45.2,
        http_calls=3,
        database_queries=5,
        cache_hits=8,
        cache_misses=2,
        quality_score=0.92,
    )
    print("\n✓ Performance metrics")
    print(f"  - Execution time: {perf.execution_time_ms}ms")
    print(f"  - Memory usage: {perf.memory_usage_mb}MB")
    print(
        f"  - Cache hit rate: {perf.cache_hits/(perf.cache_hits+perf.cache_misses):.1%}"
    )
    print(f"  - Quality score: {perf.quality_score:.2%}")

    # Trend analysis
    trend = ModelPatternTrendAnalysis(
        pattern_id=pattern_id,
        pattern_name="api_debug_pattern",
        analysis_period_days=30,
        daily_executions=[10, 12, 15, 18, 20, 22, 25, 28, 30, 32],
        weekly_growth_rate=0.15,
        monthly_retention_rate=0.85,
        adoption_velocity=0.78,
        trend_direction="growing",
        seasonality_detected=True,
        peak_usage_days=["monday", "wednesday", "friday"],
        forecast_next_week=35.5,
        forecast_confidence=0.82,
    )
    print("\n✓ Trend analysis (30 days)")
    print(f"  - Weekly growth: {trend.weekly_growth_rate:.1%}")
    print(f"  - Retention rate: {trend.monthly_retention_rate:.1%}")
    print(f"  - Trend direction: {trend.trend_direction}")
    print(f"  - Peak days: {', '.join(trend.peak_usage_days)}")
    print(f"  - Forecast (next week): {trend.forecast_next_week:.1f} executions")


# ============================================================================
# Example 3: Collecting and Processing Feedback
# ============================================================================


def example_feedback_loop():
    """
    Example: Collect feedback and propose improvements.

    Demonstrates:
    - Recording user feedback
    - Proposing improvements
    - Tracking improvement lifecycle
    """
    print("\n" + "=" * 80)
    print("Example 3: Feedback Collection and Processing")
    print("=" * 80)

    pattern_id = uuid4()
    execution_id = uuid4()

    # Collect positive feedback
    feedback = ModelPatternFeedback(
        pattern_id=pattern_id,
        execution_id=execution_id,
        sentiment=FeedbackSentiment.POSITIVE,
        explicit_rating=0.95,
        implicit_signals={
            "retry_count": 0,
            "time_to_complete": 150,
            "modifications_count": 1,
        },
        user_comments="Pattern worked perfectly for debugging API issues",
        success=True,
        quality_score=0.92,
        performance_score=0.88,
    )
    print(f"\n✓ Feedback received: {feedback.feedback_id}")
    print(f"  - Sentiment: {feedback.sentiment.value}")
    print(f"  - Rating: {feedback.explicit_rating:.2%}")
    print(f"  - Comments: {feedback.user_comments}")

    # Propose improvement based on feedback
    improvement = ModelPatternImprovement(
        pattern_id=pattern_id,
        improvement_type="performance",
        description="Add caching layer to reduce API calls",
        status=ImprovementStatus.PROPOSED,
        proposed_changes={
            "add_caching": True,
            "cache_ttl_seconds": 300,
            "cache_key_pattern": "api_{endpoint}_{params}",
        },
        baseline_metrics={"avg_execution_time_ms": 450.5, "success_rate": 0.92},
        feedback_references=[feedback.feedback_id],
    )
    print(f"\n✓ Improvement proposed: {improvement.improvement_id}")
    print(f"  - Type: {improvement.improvement_type}")
    print(f"  - Description: {improvement.description}")
    print(f"  - Status: {improvement.status.value}")

    # Simulate A/B testing validation
    improvement.status = ImprovementStatus.VALIDATED
    improvement.improved_metrics = {
        "avg_execution_time_ms": 180.2,
        "success_rate": 0.95,
    }
    improvement.performance_delta = 0.60  # 60% improvement
    improvement.confidence_score = 0.98
    improvement.p_value = 0.003
    improvement.sample_size = 150
    improvement.validated_at = datetime.now(timezone.utc)

    print("\n✓ Improvement validated")
    print(f"  - Performance improvement: {improvement.performance_delta:.1%}")
    print(f"  - Confidence: {improvement.confidence_score:.1%}")
    print(f"  - Statistical significance: p={improvement.p_value:.4f}")


# ============================================================================
# Example 4: Event Auditing and Tracking
# ============================================================================


def example_event_auditing():
    """
    Example: Track pattern lifecycle events.

    Demonstrates:
    - Creating lifecycle events
    - Recording execution events
    - Building audit trail
    """
    print("\n" + "=" * 80)
    print("Example 4: Event Auditing and Tracking")
    print("=" * 80)

    pattern_id = uuid4()
    node_id = uuid4()

    # Pattern creation event
    creation_event = ModelLineageEvent.create_pattern_created_event(
        pattern_id=pattern_id,
        node_id=node_id,
        actor_id="pattern_learning_engine",
        metadata={"source": "intelligence_hook", "quality_score": 0.92},
    )
    print(f"\n✓ Pattern created event: {creation_event.event_id}")
    print(f"  - Type: {creation_event.event_type.value}")
    print(f"  - Timestamp: {creation_event.timestamp.isoformat()}")

    # Successful execution event
    exec_event = ModelLineageEvent.create_execution_event(
        pattern_id=pattern_id,
        node_id=node_id,
        execution_id=uuid4(),
        success=True,
        actor_id="agent-debug-intelligence",
        execution_time_ms=450.5,
    )
    print(f"\n✓ Execution event: {exec_event.event_id}")
    print(f"  - Success: {exec_event.event_data.get('success')}")
    print(f"  - Execution time: {exec_event.event_data.get('execution_time_ms')}ms")

    # Pattern deprecation event
    deprecation_event = ModelLineageEvent.create_deprecation_event(
        pattern_id=pattern_id,
        node_id=node_id,
        actor_id="pattern_lifecycle_manager",
        reason="Replaced by optimized version",
        replaced_by_node_id=uuid4(),
    )
    print(f"\n✓ Deprecation event: {deprecation_event.event_id}")
    print(f"  - Severity: {deprecation_event.event_severity.value}")
    print(f"  - Reason: {deprecation_event.event_data.get('reason')}")

    # Generate audit log entry
    audit_entry = exec_event.to_audit_log_entry()
    print("\n✓ Audit log entry:")
    print(f"  - Event ID: {audit_entry['event_id']}")
    print(f"  - Event type: {audit_entry['event_type']}")
    print(f"  - Actor: {audit_entry['actor']['type']} / {audit_entry['actor']['id']}")


# ============================================================================
# Main Example Runner
# ============================================================================


def run_all_examples():
    """Run all usage examples."""
    print("\n" + "=" * 80)
    print("Phase 4 Lineage Models - Usage Examples")
    print("=" * 80)

    example_pattern_evolution()
    example_usage_tracking()
    example_feedback_loop()
    example_event_auditing()

    print("\n" + "=" * 80)
    print("All examples completed successfully!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_all_examples()
