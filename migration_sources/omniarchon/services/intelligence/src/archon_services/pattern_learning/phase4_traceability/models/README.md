# Phase 4 Traceability - Data Models

Comprehensive data models for pattern lineage tracking, metrics collection, feedback processing, and event auditing in the Pattern Learning Engine.

**Author**: Archon Intelligence Team
**Date**: 2025-10-02
**Version**: 1.0.0

## Overview

This module provides the complete data model infrastructure for Track 3 Phase 4: Pattern Traceability & Continuous Learning. The models support:

- **Pattern Evolution Tracking**: Complete lineage graphs with parent-child relationships
- **Metrics Collection**: Usage, performance, and trend analytics
- **Feedback Processing**: User feedback and improvement proposals
- **Event Auditing**: Complete audit trail for all pattern lifecycle events

## Architecture

```
PostgreSQL (Primary Storage)
    ├─> ModelPatternLineageNode (Pattern versions)
    ├─> ModelLineageEdge (Relationships)
    ├─> ModelPatternMetrics (Usage/Performance/Trends)
    ├─> ModelPatternFeedback (User feedback)
    └─> ModelLineageEvent (Audit events)

Memgraph (Graph Queries)
    └─> Lineage traversal, path finding, relationship queries

Qdrant (Semantic Search)
    └─> Pattern similarity search across lineage

Time-Series DB
    └─> Event stream and metrics aggregation
```

## Models

### Core Lineage Models

#### ModelPatternLineageNode

Represents a pattern instance in the lineage graph.

**Key Features**:
- Version tracking with human-readable labels
- Parent-child relationships for evolution tracking
- Lifecycle management (draft → active → deprecated → archived)
- Usage tracking with running averages
- Memgraph node serialization

**Usage**:
```python
from models import ModelPatternLineageNode, EnumPatternEvolutionType

# Create root pattern
node_v1 = ModelPatternLineageNode(
    pattern_id=uuid4(),
    version=1,
    created_by="pattern_learning_engine"
)
node_v1.activate()

# Create refined version
node_v2 = ModelPatternLineageNode(
    pattern_id=uuid4(),
    version=2,
    parent_ids=[node_v1.node_id],
    evolution_type=EnumPatternEvolutionType.REFINEMENT,
    created_by="pattern_learning_engine"
)

# Track usage
node_v2.record_usage(execution_time_ms=450.5, success=True)

# Deprecate old version
node_v1.deprecate("Replaced by v2", replaced_by=node_v2.node_id)
```

**Key Methods**:
- `record_usage(execution_time_ms, success)` - Track pattern usage
- `deprecate(reason, replaced_by)` - Mark as deprecated
- `activate()` - Activate pattern version
- `is_root()` - Check if root node
- `is_leaf()` - Check if leaf node
- `to_graph_node()` - Convert to Memgraph node properties

#### ModelLineageEdge

Represents relationships between patterns in the lineage graph.

**Key Features**:
- Multiple relationship types (derived, merged, replaced, forked)
- Edge strength and confidence scoring
- Change tracking (breaking changes flag)
- Weight calculation for graph algorithms
- Lifecycle management (active/deactivated)

**Usage**:
```python
from models import ModelLineageEdge, EnumLineageRelationshipType, EnumEdgeStrength

edge = ModelLineageEdge(
    source_node_id=parent_node.node_id,
    target_node_id=child_node.node_id,
    source_pattern_id=parent_pattern_id,
    target_pattern_id=child_pattern_id,
    relationship_type=EnumLineageRelationshipType.REFINED_FROM,
    edge_strength=EnumEdgeStrength.STRONG,
    similarity_score=0.92,
    confidence_score=0.95,
    change_summary="Improved performance by 40%",
    breaking_changes=False,
    created_by="pattern_learning_engine"
)

# Get edge weight for algorithms
weight = edge.get_weight()  # Weighted by strength, similarity, confidence
```

**Key Methods**:
- `get_weight()` - Calculate edge weight for graph algorithms
- `deactivate(reason)` - Deactivate relationship
- `is_evolution_edge()` - Check if evolution relationship
- `is_merge_edge()` - Check if merge relationship
- `to_graph_edge()` - Convert to Memgraph edge properties

### Analytics Models

#### ModelPatternUsageMetrics

Daily usage metrics for pattern analytics.

**Fields**:
- `execution_count`, `success_count`, `failure_count`
- `success_rate` (0.0-1.0)
- `context_breakdown` (usage by context)
- `avg_execution_time_ms`

#### ModelPatternPerformanceMetrics

Detailed performance statistics for pattern execution.

**Fields**:
- `execution_time_ms`, `memory_usage_mb`, `cpu_usage_percent`
- `http_calls`, `database_queries`
- `cache_hits`, `cache_misses`
- `quality_score` (from intelligence system)

#### ModelPatternTrendAnalysis

Trend analysis for pattern adoption and growth.

**Key Features**:
- Growth rate tracking (weekly, monthly)
- Retention rate analysis
- Seasonality detection
- Forecasting with confidence scores
- Anomaly detection

**Usage**:
```python
from models import ModelPatternTrendAnalysis

trend = ModelPatternTrendAnalysis(
    pattern_id=pattern_id,
    pattern_name="api_debug_pattern",
    analysis_period_days=30,
    daily_executions=[10, 12, 15, 18, 20, 22, 25],
    weekly_growth_rate=0.15,
    monthly_retention_rate=0.85,
    trend_direction="growing",
    forecast_next_week=35.5,
    forecast_confidence=0.82
)
```

### Feedback Models

#### ModelPatternFeedback

User feedback for pattern execution.

**Key Features**:
- Explicit rating (0.0-1.0)
- Sentiment classification (positive/neutral/negative)
- Implicit signals (retry count, time to complete)
- Quality and performance scores
- User comments

#### ModelPatternImprovement

Proposed or implemented pattern improvement.

**Key Features**:
- Improvement type (performance, quality, accuracy)
- Status tracking (proposed → testing → validated → applied)
- Baseline vs improved metrics
- Statistical validation (p-value, confidence score)
- A/B test results tracking

**Usage**:
```python
from models import ModelPatternImprovement, ImprovementStatus

improvement = ModelPatternImprovement(
    pattern_id=pattern_id,
    improvement_type="performance",
    description="Add caching layer to reduce API calls",
    status=ImprovementStatus.PROPOSED,
    baseline_metrics={"avg_execution_time_ms": 450.5},
    proposed_changes={"add_caching": True, "cache_ttl_seconds": 300}
)

# After validation
improvement.status = ImprovementStatus.VALIDATED
improvement.improved_metrics = {"avg_execution_time_ms": 180.2}
improvement.performance_delta = 0.60  # 60% improvement
improvement.confidence_score = 0.98
improvement.p_value = 0.003
```

### Event Models

#### ModelLineageEvent

Event in pattern lineage history for complete audit trail.

**Key Features**:
- 20+ event types covering all lifecycle stages
- Severity levels (debug, info, warning, error, critical)
- Actor tracking (system, user, agent, automation)
- Correlation IDs for distributed tracing
- Before/after state tracking
- Multiple serialization formats (audit log, time-series)

**Factory Methods**:
```python
from models import ModelLineageEvent

# Pattern creation
event = ModelLineageEvent.create_pattern_created_event(
    pattern_id=pattern_id,
    node_id=node_id,
    actor_id="pattern_learning_engine"
)

# Execution tracking
event = ModelLineageEvent.create_execution_event(
    pattern_id=pattern_id,
    node_id=node_id,
    execution_id=uuid4(),
    success=True,
    actor_id="agent-debug-intelligence",
    execution_time_ms=450.5
)

# Deprecation tracking
event = ModelLineageEvent.create_deprecation_event(
    pattern_id=pattern_id,
    node_id=node_id,
    actor_id="lifecycle_manager",
    reason="Replaced by optimized version",
    replaced_by_node_id=replacement_id
)
```

**Serialization Methods**:
```python
# Audit log format
audit_entry = event.to_audit_log_entry()
# Returns: {"event_id", "event_type", "severity", "actor", ...}

# Time-series format
ts_entry = event.to_time_series_entry()
# Returns: {"timestamp" (unix), "event_type", "pattern_id", ...}
```

## Usage Examples

See `model_examples.py` for comprehensive usage examples covering:

1. **Pattern Evolution Chain**: Creating v1 → v2 evolution with edges
2. **Usage and Performance Tracking**: Daily metrics and trend analysis
3. **Feedback Loop**: Collecting feedback and proposing improvements
4. **Event Auditing**: Building complete audit trail

Run examples:
```bash
python model_examples.py
```

## Testing

Comprehensive test suite in `test_lineage_models.py`:

```bash
# Run all tests
pytest test_lineage_models.py -v

# Run specific test class
pytest test_lineage_models.py::TestModelPatternLineageNode -v

# Run with coverage
pytest test_lineage_models.py --cov=. --cov-report=html
```

**Test Coverage**:
- ✓ Model validation and constraints
- ✓ Lifecycle transitions
- ✓ Usage tracking with running averages
- ✓ Relationship management
- ✓ Edge weight calculation
- ✓ Event serialization
- ✓ Integration scenarios

## Validation Rules

### ModelPatternLineageNode
- `success_rate`: 0.0 ≤ value ≤ 1.0
- `avg_execution_time_ms`: value ≥ 0.0
- `version`: value ≥ 1
- `usage_count`: value ≥ 0

### ModelLineageEdge
- `source_node_id` ≠ `target_node_id` (no self-loops)
- `similarity_score`: 0.0 ≤ value ≤ 1.0
- `confidence_score`: 0.0 ≤ value ≤ 1.0

### ModelPatternMetrics
- All scores: 0.0 ≤ value ≤ 1.0
- All counts: value ≥ 0
- `cpu_usage_percent`: 0.0 ≤ value ≤ 100.0

## Integration Points

### PostgreSQL Schema

```sql
-- Pattern lineage nodes
CREATE TABLE pattern_lineage_nodes (
    node_id UUID PRIMARY KEY,
    pattern_id UUID NOT NULL,
    version INTEGER NOT NULL,
    status VARCHAR(50),
    created_by VARCHAR(255),
    metadata JSONB,
    -- ... other fields
);

-- Lineage edges
CREATE TABLE lineage_edges (
    edge_id UUID PRIMARY KEY,
    source_node_id UUID REFERENCES pattern_lineage_nodes(node_id),
    target_node_id UUID REFERENCES pattern_lineage_nodes(node_id),
    relationship_type VARCHAR(50),
    -- ... other fields
);
```

### Memgraph Integration

```python
# Create node in Memgraph
node_props = node.to_graph_node()
query = """
CREATE (n:PatternNode {
    node_id: $node_id,
    pattern_id: $pattern_id,
    version: $version,
    status: $status
})
"""
```

### Event Stream Integration

```python
# Publish to event stream
event_data = event.to_time_series_entry()
await event_publisher.publish("pattern.events", event_data)
```

## Migration Guide

### From Simple Models (Backward Compatibility)

```python
# Old (simple models)
from models import ModelLineageNode, ModelLineageEdge

# New (comprehensive models)
from models import ModelPatternLineageNode, ModelLineageEdge

# Legacy imports still work via aliases
from models import ModelLineageNodeSimple  # Old ModelLineageNode
```

## Best Practices

### 1. Pattern Lifecycle Management

```python
# Always use lifecycle methods
node.activate()  # Not: node.status = EnumPatternLineageStatus.ACTIVE
node.deprecate("reason", replacement_id)  # Handles timestamps automatically
```

### 2. Usage Tracking

```python
# Record every usage for accurate metrics
node.record_usage(execution_time_ms=450.5, success=True)
# This updates: usage_count, avg_execution_time_ms, success_rate, timestamps
```

### 3. Event Correlation

```python
# Use correlation IDs for distributed tracing
correlation_id = uuid4()

event1 = ModelLineageEvent(correlation_id=correlation_id, ...)
event2 = ModelLineageEvent(correlation_id=correlation_id, ...)
# Both events can be linked in analysis
```

### 4. Edge Weights

```python
# Set similarity and confidence for better graph algorithms
edge = ModelLineageEdge(
    similarity_score=0.92,  # How similar the patterns are
    confidence_score=0.95,  # How confident in the relationship
    edge_strength=EnumEdgeStrength.STRONG
)
# get_weight() will use all three for optimal pathfinding
```

## Future Enhancements

- [ ] Graph visualization helpers
- [ ] Advanced query builders for complex graph traversal
- [ ] Machine learning model for automatic improvement detection
- [ ] Real-time event streaming integration
- [ ] Pattern similarity computation utilities

## License

Copyright © 2025 Archon Intelligence Team. All rights reserved.

## Support

For questions or issues, contact the Pattern Learning Engine team or file an issue in the project repository.
