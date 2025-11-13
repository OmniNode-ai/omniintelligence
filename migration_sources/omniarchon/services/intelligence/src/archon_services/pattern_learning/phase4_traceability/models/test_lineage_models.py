#!/usr/bin/env python3
"""
Comprehensive Tests for Phase 4 Lineage Models

Tests all data models for pattern lineage tracking, ensuring
correct validation, relationships, and lifecycle management.

Author: Archon Intelligence Team
Date: 2025-10-02
"""

from uuid import UUID, uuid4

import pytest

from .model_lineage_edge import (
    EnumEdgeStrength,
    EnumLineageRelationshipType,
    ModelLineageEdge,
)
from .model_lineage_event import (
    EnumEventSeverity,
    EnumLineageEventType,
    ModelLineageEvent,
)
from .model_pattern_feedback import (
    FeedbackSentiment,
    ImprovementStatus,
    ModelPatternFeedback,
    ModelPatternImprovement,
)

# Import all models
from .model_pattern_lineage_node import (
    EnumPatternEvolutionType,
    EnumPatternLineageStatus,
    ModelPatternLineageNode,
)
from .model_pattern_metrics import (
    ModelPatternPerformanceMetrics,
    ModelPatternTrendAnalysis,
    ModelPatternUsageMetrics,
)

# ============================================================================
# ModelPatternLineageNode Tests
# ============================================================================


# NOTE: correlation_id support enabled for tracing
class TestModelPatternLineageNode:
    """Test suite for pattern lineage node model."""

    def test_create_root_node(self):
        """Test creating a root pattern node."""
        node = ModelPatternLineageNode(pattern_id=uuid4(), created_by="test_system")

        assert node.is_root()
        assert not node.is_leaf()
        assert node.status == EnumPatternLineageStatus.DRAFT
        assert node.version == 1
        assert node.usage_count == 0

    def test_create_child_node(self):
        """Test creating a child pattern node."""
        parent_id = uuid4()
        node = ModelPatternLineageNode(
            pattern_id=uuid4(),
            created_by="test_system",
            parent_ids=[parent_id],
            evolution_type=EnumPatternEvolutionType.REFINEMENT,
        )

        assert not node.is_root()
        assert parent_id in node.parent_ids
        assert node.evolution_type == EnumPatternEvolutionType.REFINEMENT

    def test_lifecycle_transitions(self):
        """Test pattern lifecycle transitions."""
        node = ModelPatternLineageNode(pattern_id=uuid4(), created_by="test_system")

        # Activate pattern
        node.activate()
        assert node.is_active()
        assert node.status == EnumPatternLineageStatus.ACTIVE

        # Deprecate pattern
        node.deprecate("Replaced by v2", uuid4())
        assert node.is_deprecated()
        assert node.has_replacement()
        assert node.deprecated_reason == "Replaced by v2"

        # Archive pattern
        node.archive()
        assert node.status == EnumPatternLineageStatus.ARCHIVED

    def test_usage_tracking(self):
        """Test usage tracking with running averages."""
        node = ModelPatternLineageNode(pattern_id=uuid4(), created_by="test_system")

        # Record first usage
        node.record_usage(100.0, True)
        assert node.usage_count == 1
        assert node.avg_execution_time_ms == 100.0
        assert node.success_rate == 1.0

        # Record second usage
        node.record_usage(200.0, False)
        assert node.usage_count == 2
        assert node.avg_execution_time_ms == 150.0  # (100 + 200) / 2
        assert node.success_rate == 0.5  # 1/2

        # Record third usage
        node.record_usage(150.0, True)
        assert node.usage_count == 3
        assert abs(node.avg_execution_time_ms - 150.0) < 0.01
        assert abs(node.success_rate - 0.6667) < 0.01

    def test_relationship_management(self):
        """Test parent-child relationship management."""
        node = ModelPatternLineageNode(pattern_id=uuid4(), created_by="test_system")

        parent_id = uuid4()
        child_id = uuid4()

        # Add parent
        node.add_parent(parent_id)
        assert parent_id in node.parent_ids
        assert not node.is_root()

        # Add child
        node.add_child(child_id)
        assert child_id in node.child_ids
        assert not node.is_leaf()

        # Remove child
        node.remove_child(child_id)
        assert child_id not in node.child_ids
        assert node.is_leaf()

    def test_validation(self):
        """Test model validation."""
        # Test success_rate validation
        with pytest.raises(ValueError):
            ModelPatternLineageNode(
                pattern_id=uuid4(),
                created_by="test",
                success_rate=1.5,  # Invalid: > 1.0
            )

        # Test avg_execution_time_ms validation
        with pytest.raises(ValueError):
            ModelPatternLineageNode(
                pattern_id=uuid4(),
                created_by="test",
                avg_execution_time_ms=-10.0,  # Invalid: negative
            )


# ============================================================================
# ModelLineageEdge Tests
# ============================================================================


class TestModelLineageEdge:
    """Test suite for lineage edge model."""

    def test_create_edge(self):
        """Test creating a lineage edge."""
        source_id = uuid4()
        target_id = uuid4()

        edge = ModelLineageEdge(
            source_node_id=source_id,
            target_node_id=target_id,
            source_pattern_id=uuid4(),
            target_pattern_id=uuid4(),
            relationship_type=EnumLineageRelationshipType.DERIVED_FROM,
            created_by="test_system",
        )

        assert edge.source_node_id == source_id
        assert edge.target_node_id == target_id
        assert edge.is_active
        assert edge.is_evolution_edge()
        assert not edge.is_merge_edge()

    def test_edge_weight_calculation(self):
        """Test edge weight calculation."""
        edge = ModelLineageEdge(
            source_node_id=uuid4(),
            target_node_id=uuid4(),
            source_pattern_id=uuid4(),
            target_pattern_id=uuid4(),
            relationship_type=EnumLineageRelationshipType.REFINED_FROM,
            edge_strength=EnumEdgeStrength.STRONG,
            similarity_score=0.95,
            confidence_score=0.90,
            created_by="test_system",
        )

        weight = edge.get_weight()
        # Weight = 0.5 * 0.9 (strong) + 0.25 * 0.95 + 0.25 * 0.90
        expected = 0.5 * 0.9 + 0.25 * 0.95 + 0.25 * 0.90
        assert abs(weight - expected) < 0.01

    def test_edge_deactivation(self):
        """Test edge lifecycle management."""
        edge = ModelLineageEdge(
            source_node_id=uuid4(),
            target_node_id=uuid4(),
            source_pattern_id=uuid4(),
            target_pattern_id=uuid4(),
            relationship_type=EnumLineageRelationshipType.MERGED_WITH,
            created_by="test_system",
        )

        edge.deactivate("Pattern was split")
        assert not edge.is_active
        assert edge.deactivation_reason == "Pattern was split"

        edge.reactivate()
        assert edge.is_active
        assert edge.deactivation_reason is None

    def test_self_loop_prevention(self):
        """Test that self-loops are prevented."""
        node_id = uuid4()

        with pytest.raises(
            ValueError, match="source_node_id and target_node_id must be different"
        ):
            ModelLineageEdge(
                source_node_id=node_id,
                target_node_id=node_id,  # Same as source
                source_pattern_id=uuid4(),
                target_pattern_id=uuid4(),
                relationship_type=EnumLineageRelationshipType.DERIVED_FROM,
                created_by="test_system",
            )


# ============================================================================
# ModelPatternMetrics Tests
# ============================================================================


class TestModelPatternMetrics:
    """Test suite for pattern metrics models."""

    def test_usage_metrics(self):
        """Test pattern usage metrics model."""
        from datetime import date

        metrics = ModelPatternUsageMetrics(
            pattern_id=uuid4(),
            pattern_name="test_pattern",
            metrics_date=date.today(),
            execution_count=100,
            success_count=95,
            failure_count=5,
        )

        assert metrics.execution_count == 100
        assert metrics.success_count == 95
        assert metrics.failure_count == 5

    def test_performance_metrics(self):
        """Test pattern performance metrics model."""
        metrics = ModelPatternPerformanceMetrics(
            pattern_id=uuid4(),
            pattern_name="test_pattern",
            execution_time_ms=450.5,
            http_calls=3,
            database_queries=5,
        )

        assert metrics.execution_time_ms == 450.5
        assert metrics.http_calls == 3
        assert metrics.database_queries == 5

    def test_trend_analysis(self):
        """Test pattern trend analysis model."""
        trend = ModelPatternTrendAnalysis(
            pattern_id=uuid4(),
            pattern_name="test_pattern",
            daily_executions=[10, 12, 15, 18, 20],
            weekly_growth_rate=0.15,
            trend_direction="growing",
        )

        assert len(trend.daily_executions) == 5
        assert trend.weekly_growth_rate == 0.15
        assert trend.trend_direction == "growing"


# ============================================================================
# ModelPatternFeedback Tests
# ============================================================================


class TestModelPatternFeedback:
    """Test suite for pattern feedback models."""

    def test_feedback_creation(self):
        """Test feedback model creation."""
        feedback = ModelPatternFeedback(
            pattern_id=uuid4(),
            execution_id=uuid4(),
            sentiment=FeedbackSentiment.POSITIVE,
            explicit_rating=0.95,
            success=True,
        )

        assert feedback.sentiment == FeedbackSentiment.POSITIVE
        assert feedback.explicit_rating == 0.95
        assert feedback.success

    def test_improvement_lifecycle(self):
        """Test improvement status transitions."""
        improvement = ModelPatternImprovement(
            pattern_id=uuid4(),
            improvement_type="performance",
            description="Add caching",
            status=ImprovementStatus.PROPOSED,
        )

        assert improvement.status == ImprovementStatus.PROPOSED
        assert improvement.confidence_score == 0.0


# ============================================================================
# ModelLineageEvent Tests
# ============================================================================


class TestModelLineageEvent:
    """Test suite for lineage event model."""

    def test_create_pattern_created_event(self):
        """Test pattern created event factory."""
        pattern_id = uuid4()
        node_id = uuid4()

        event = ModelLineageEvent.create_pattern_created_event(
            pattern_id=pattern_id, node_id=node_id, actor_id="test_system"
        )

        assert event.event_type == EnumLineageEventType.PATTERN_CREATED
        assert event.pattern_id == pattern_id
        assert event.node_id == node_id
        assert event.is_lifecycle_event()

    def test_create_execution_event(self):
        """Test execution event factory."""
        event = ModelLineageEvent.create_execution_event(
            pattern_id=uuid4(),
            node_id=uuid4(),
            execution_id=uuid4(),
            success=True,
            actor_id="agent-test",
            execution_time_ms=450.5,
        )

        assert event.event_type == EnumLineageEventType.EXECUTION_SUCCEEDED
        assert event.is_usage_event()
        assert event.event_severity == EnumEventSeverity.INFO

    def test_error_event(self):
        """Test error event handling."""
        event = ModelLineageEvent.create_execution_event(
            pattern_id=uuid4(),
            node_id=uuid4(),
            execution_id=uuid4(),
            success=False,
            actor_id="agent-test",
            execution_time_ms=100.0,
            error_message="Test error",
        )

        assert event.event_type == EnumLineageEventType.EXECUTION_FAILED
        assert event.is_error_event()
        assert event.error_message == "Test error"

    def test_event_serialization(self):
        """Test event serialization methods."""
        event = ModelLineageEvent(
            event_type=EnumLineageEventType.PATTERN_APPLIED,
            pattern_id=uuid4(),
            actor_id="test_system",
        )

        # Test audit log entry
        audit_entry = event.to_audit_log_entry()
        assert "event_id" in audit_entry
        assert "event_type" in audit_entry
        assert "actor" in audit_entry

        # Test time series entry
        ts_entry = event.to_time_series_entry()
        assert "timestamp" in ts_entry
        assert "event_type" in ts_entry
        assert isinstance(ts_entry["timestamp"], int)


# ============================================================================
# Integration Tests
# ============================================================================


class TestModelIntegration:
    """Integration tests for model relationships."""

    def test_complete_pattern_lifecycle(self):
        """Test complete pattern lifecycle with multiple models."""
        # Create pattern node
        pattern_id = uuid4()
        node = ModelPatternLineageNode(pattern_id=pattern_id, created_by="test_system")
        node.activate()

        # Create creation event
        ModelLineageEvent.create_pattern_created_event(
            pattern_id=pattern_id, node_id=node.node_id, actor_id="test_system"
        )

        # Record usage
        node.record_usage(450.5, True)

        # Create usage event
        usage_event = ModelLineageEvent.create_execution_event(
            pattern_id=pattern_id,
            node_id=node.node_id,
            execution_id=uuid4(),
            success=True,
            actor_id="agent-test",
            execution_time_ms=450.5,
        )

        # Create feedback
        feedback = ModelPatternFeedback(
            pattern_id=pattern_id,
            execution_id=usage_event.execution_id,
            sentiment=FeedbackSentiment.POSITIVE,
            success=True,
        )

        # Verify relationships
        assert node.is_active()
        assert node.usage_count == 1
        assert usage_event.pattern_id == pattern_id
        assert feedback.pattern_id == pattern_id

    def test_pattern_evolution_chain(self):
        """Test pattern evolution with nodes and edges."""
        # Create parent node
        parent_id = uuid4()
        parent_node = ModelPatternLineageNode(
            pattern_id=parent_id, created_by="test_system"
        )
        parent_node.activate()

        # Create child node
        child_id = uuid4()
        child_node = ModelPatternLineageNode(
            pattern_id=child_id,
            created_by="test_system",
            version=2,
            parent_ids=[parent_node.node_id],
            evolution_type=EnumPatternEvolutionType.REFINEMENT,
        )

        # Create evolution edge
        edge = ModelLineageEdge(
            source_node_id=parent_node.node_id,
            target_node_id=child_node.node_id,
            source_pattern_id=parent_id,
            target_pattern_id=child_id,
            relationship_type=EnumLineageRelationshipType.REFINED_FROM,
            edge_strength=EnumEdgeStrength.STRONG,
            created_by="test_system",
        )

        # Verify evolution chain
        assert child_node.version == 2
        assert parent_node.node_id in child_node.parent_ids
        assert edge.is_evolution_edge()
        assert edge.is_strong_relationship()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
