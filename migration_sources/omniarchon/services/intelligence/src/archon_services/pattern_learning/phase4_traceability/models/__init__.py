"""
Phase 4 Traceability - Data Models

Comprehensive data models for pattern lineage tracking, metrics collection,
feedback processing, and event auditing.

Architecture:
    - PostgreSQL: Primary storage for all models
    - Memgraph: Graph representation for lineage traversal
    - Qdrant: Semantic search across pattern lineage
    - Time-series DB: Event and metrics storage

Author: Archon Intelligence Team
Date: 2025-10-02
"""

from src.archon_services.pattern_learning.phase4_traceability.models.model_lineage_edge import (
    EnumEdgeStrength,
    EnumLineageRelationshipType,
    ModelLineageEdge,
)

# Event models
from src.archon_services.pattern_learning.phase4_traceability.models.model_lineage_event import (
    EnumEventActor,
    EnumEventSeverity,
    EnumLineageEventType,
    ModelLineageEvent,
)

# Legacy simpler models (for backward compatibility)
from src.archon_services.pattern_learning.phase4_traceability.models.model_lineage_graph import (
    LineageRelationType,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_lineage_graph import (
    ModelLineageEdge as ModelLineageEdgeSimple,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_lineage_graph import (
    ModelLineageGraph as ModelLineageGraphSimple,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_lineage_graph import (
    ModelLineageNode as ModelLineageNodeSimple,
)
from src.archon_services.pattern_learning.phase4_traceability.models.model_lineage_graph import (
    NodeStatus,
)

# Feedback models
from src.archon_services.pattern_learning.phase4_traceability.models.model_pattern_feedback import (
    FeedbackSentiment,
    ImprovementStatus,
    ModelPatternFeedback,
    ModelPatternImprovement,
)

# Comprehensive lineage models (Phase 4 complete)
from src.archon_services.pattern_learning.phase4_traceability.models.model_pattern_lineage_node import (
    EnumPatternEvolutionType,
    EnumPatternLineageStatus,
    ModelPatternLineageNode,
)

# Analytics models
from src.archon_services.pattern_learning.phase4_traceability.models.model_pattern_metrics import (
    ModelPatternHealthMetrics,
    ModelPatternPerformanceMetrics,
    ModelPatternTrendAnalysis,
    ModelPatternUsageMetrics,
)

__all__ = [
    # Legacy lineage models (backward compatibility)
    "ModelLineageGraphSimple",
    "ModelLineageNodeSimple",
    "ModelLineageEdgeSimple",
    "LineageRelationType",
    "NodeStatus",
    # Comprehensive lineage models
    "ModelPatternLineageNode",
    "EnumPatternLineageStatus",
    "EnumPatternEvolutionType",
    "ModelLineageEdge",
    "EnumLineageRelationshipType",
    "EnumEdgeStrength",
    # Analytics models
    "ModelPatternUsageMetrics",
    "ModelPatternPerformanceMetrics",
    "ModelPatternHealthMetrics",
    "ModelPatternTrendAnalysis",
    # Feedback models
    "ModelPatternFeedback",
    "ModelPatternImprovement",
    "FeedbackSentiment",
    "ImprovementStatus",
    # Event models
    "ModelLineageEvent",
    "EnumLineageEventType",
    "EnumEventSeverity",
    "EnumEventActor",
]
