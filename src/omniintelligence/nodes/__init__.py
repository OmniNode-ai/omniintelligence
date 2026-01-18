"""ONEX Intelligence Nodes.

This module exports all 21 canonical ONEX nodes for the intelligence system.
Nodes follow the four-node pattern: Orchestrator, Reducer, Compute, Effect.
"""
# Orchestrators (2)
from omniintelligence.nodes.intelligence_orchestrator.node import (
    NodeIntelligenceOrchestrator,
)
from omniintelligence.nodes.pattern_assembler_orchestrator.node import (
    NodePatternAssemblerOrchestrator,
)

# Reducers (1)
from omniintelligence.nodes.intelligence_reducer.node import NodeIntelligenceReducer

# Effects (5 active + 1 stub)
from omniintelligence.nodes.intelligence_adapter.node_intelligence_adapter_effect import (
    NodeIntelligenceAdapterEffect,
)
from omniintelligence.nodes.intelligence_api_effect.node import NodeIntelligenceApiEffect
from omniintelligence.nodes.memgraph_graph_effect.node import NodeMemgraphGraphEffect
from omniintelligence.nodes.postgres_pattern_effect.node import NodePostgresPatternEffect
from omniintelligence.nodes.qdrant_vector_effect.node import NodeQdrantVectorEffect
# ingestion_effect is a stub - not exported

# Computes (10 active + 1 stub)
from omniintelligence.nodes.context_keyword_extractor_compute.node import (
    NodeContextKeywordExtractorCompute,
)
from omniintelligence.nodes.entity_extraction_compute.node import (
    NodeEntityExtractionCompute,
)
from omniintelligence.nodes.execution_trace_parser_compute.node import (
    NodeExecutionTraceParserCompute,
)
from omniintelligence.nodes.intent_classifier_compute.node import (
    NodeIntentClassifierCompute,
)
from omniintelligence.nodes.pattern_matching_compute.node import (
    NodePatternMatchingCompute,
)
from omniintelligence.nodes.quality_scoring_compute.node import (
    NodeQualityScoringCompute,
)
from omniintelligence.nodes.relationship_detection_compute.node import (
    NodeRelationshipDetectionCompute,
)
from omniintelligence.nodes.semantic_analysis_compute.node import (
    NodeSemanticAnalysisCompute,
)
from omniintelligence.nodes.success_criteria_matcher_compute.node import (
    NodeSuccessCriteriaMatcherCompute,
)
from omniintelligence.nodes.vectorization_compute.node import NodeVectorizationCompute
# pattern_learning_compute is a stub - not exported

__all__ = [
    "NodeContextKeywordExtractorCompute",
    "NodeEntityExtractionCompute",
    "NodeExecutionTraceParserCompute",
    "NodeIntelligenceAdapterEffect",
    "NodeIntelligenceApiEffect",
    "NodeIntelligenceOrchestrator",
    "NodeIntelligenceReducer",
    "NodeIntentClassifierCompute",
    "NodeMemgraphGraphEffect",
    "NodePatternAssemblerOrchestrator",
    "NodePatternMatchingCompute",
    "NodePostgresPatternEffect",
    "NodeQdrantVectorEffect",
    "NodeQualityScoringCompute",
    "NodeRelationshipDetectionCompute",
    "NodeSemanticAnalysisCompute",
    "NodeSuccessCriteriaMatcherCompute",
    "NodeVectorizationCompute",
]
