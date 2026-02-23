"""ONEX Intelligence Nodes.

This module exports all canonical ONEX nodes for the intelligence system.
Nodes follow the four-node pattern: Orchestrator, Reducer, Compute, Effect.

Nodes are lazily imported to avoid loading heavy dependencies (like Kafka)
at package import time. This allows lightweight imports like:
    from omniintelligence import score_code_quality
without triggering the full dependency chain.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

# Lazy import map: name -> (module_path, attribute_name)
_LAZY_IMPORT_MAP: dict[str, tuple[str, str]] = {
    # Orchestrators (2)
    "NodeIntelligenceOrchestrator": (
        "omniintelligence.nodes.node_intelligence_orchestrator.node",
        "NodeIntelligenceOrchestrator",
    ),
    "NodePatternAssemblerOrchestrator": (
        "omniintelligence.nodes.node_pattern_assembler_orchestrator.node",
        "NodePatternAssemblerOrchestrator",
    ),
    # Reducers (2)
    "NodeDocPromotionReducer": (
        "omniintelligence.nodes.node_doc_promotion_reducer.node",
        "NodeDocPromotionReducer",
    ),
    "NodeIntelligenceReducer": (
        "omniintelligence.nodes.node_intelligence_reducer.node",
        "NodeIntelligenceReducer",
    ),
    # Effects (11)
    "NodeContextItemWriterEffect": (
        "omniintelligence.nodes.node_context_item_writer_effect.node",
        "NodeContextItemWriterEffect",
    ),
    "NodeDocStalenessDetectorEffect": (
        "omniintelligence.nodes.node_doc_staleness_detector_effect.node",
        "NodeDocStalenessDetectorEffect",
    ),
    "NodeDocumentFetchEffect": (
        "omniintelligence.nodes.node_document_fetch_effect.node",
        "NodeDocumentFetchEffect",
    ),
    "NodeGitRepoCrawlerEffect": (
        "omniintelligence.nodes.node_git_repo_crawler_effect.node",
        "NodeGitRepoCrawlerEffect",
    ),
    "NodeLinearCrawlerEffect": (
        "omniintelligence.nodes.node_linear_crawler_effect.node",
        "NodeLinearCrawlerEffect",
    ),
    "NodeEnforcementFeedbackEffect": (
        "omniintelligence.nodes.node_enforcement_feedback_effect.node",
        "NodeEnforcementFeedbackEffect",
    ),
    "NodePatternComplianceEffect": (
        "omniintelligence.nodes.node_pattern_compliance_effect.node",
        "NodePatternComplianceEffect",
    ),
    "NodePatternDemotionEffect": (
        "omniintelligence.nodes.node_pattern_demotion_effect.node",
        "NodePatternDemotionEffect",
    ),
    "NodePatternFeedbackEffect": (
        "omniintelligence.nodes.node_pattern_feedback_effect.node",
        "NodePatternFeedbackEffect",
    ),
    "NodePatternLifecycleEffect": (
        "omniintelligence.nodes.node_pattern_lifecycle_effect.node",
        "NodePatternLifecycleEffect",
    ),
    "NodePatternPromotionEffect": (
        "omniintelligence.nodes.node_pattern_promotion_effect.node",
        "NodePatternPromotionEffect",
    ),
    "NodePatternStorageEffect": (
        "omniintelligence.nodes.node_pattern_storage_effect.node",
        "NodePatternStorageEffect",
    ),
    "ClaudeSessionOutcome": (
        "omniintelligence.nodes.node_pattern_feedback_effect",
        "ClaudeSessionOutcome",
    ),
    "ClaudeCodeSessionOutcome": (
        "omniintelligence.nodes.node_pattern_feedback_effect",
        "ClaudeCodeSessionOutcome",
    ),
    "SessionOutcomeInput": (
        "omniintelligence.nodes.node_pattern_feedback_effect",
        "SessionOutcomeInput",
    ),
    "ModelSessionOutcomeResult": (
        "omniintelligence.nodes.node_pattern_feedback_effect",
        "ModelSessionOutcomeResult",
    ),
    "EnumOutcomeRecordingStatus": (
        "omniintelligence.nodes.node_pattern_feedback_effect",
        "EnumOutcomeRecordingStatus",
    ),
    "ProtocolPatternRepository": (
        "omniintelligence.protocols",
        "ProtocolPatternRepository",
    ),
    "record_session_outcome": (
        "omniintelligence.nodes.node_pattern_feedback_effect",
        "record_session_outcome",
    ),
    "update_pattern_rolling_metrics": (
        "omniintelligence.nodes.node_pattern_feedback_effect",
        "update_pattern_rolling_metrics",
    ),
    "ROLLING_WINDOW_SIZE": (
        "omniintelligence.nodes.node_pattern_feedback_effect",
        "ROLLING_WINDOW_SIZE",
    ),
    # Computes (10)
    "NodeDocumentParserCompute": (
        "omniintelligence.nodes.node_document_parser_compute.node",
        "NodeDocumentParserCompute",
    ),
    "NodeExecutionTraceParserCompute": (
        "omniintelligence.nodes.node_execution_trace_parser_compute.node",
        "NodeExecutionTraceParserCompute",
    ),
    "NodeIntentClassifierCompute": (
        "omniintelligence.nodes.node_intent_classifier_compute.node",
        "NodeIntentClassifierCompute",
    ),
    "NodeIntentDriftDetectCompute": (
        "omniintelligence.nodes.node_intent_drift_detect_compute.node",
        "NodeIntentDriftDetectCompute",
    ),
    "NodePatternExtractionCompute": (
        "omniintelligence.nodes.node_pattern_extraction_compute.node",
        "NodePatternExtractionCompute",
    ),
    "NodePatternLearningCompute": (
        "omniintelligence.nodes.node_pattern_learning_compute.node",
        "NodePatternLearningCompute",
    ),
    "NodePatternMatchingCompute": (
        "omniintelligence.nodes.node_pattern_matching_compute.node",
        "NodePatternMatchingCompute",
    ),
    "NodeQualityScoringCompute": (
        "omniintelligence.nodes.node_quality_scoring_compute.node",
        "NodeQualityScoringCompute",
    ),
    "NodeSemanticAnalysisCompute": (
        "omniintelligence.nodes.node_semantic_analysis_compute.node",
        "NodeSemanticAnalysisCompute",
    ),
    "NodeSuccessCriteriaMatcherCompute": (
        "omniintelligence.nodes.node_success_criteria_matcher_compute.node",
        "NodeSuccessCriteriaMatcherCompute",
    ),
}

# Cache for loaded imports
_lazy_imports: dict[str, object] = {}


def __getattr__(name: str) -> object:
    """Lazy import handler for node classes."""
    if name in _LAZY_IMPORT_MAP:
        if name not in _lazy_imports:
            module_path, attr_name = _LAZY_IMPORT_MAP[name]
            module = importlib.import_module(module_path)
            _lazy_imports[name] = getattr(module, attr_name)
        return _lazy_imports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """List available attributes including lazy imports."""
    return list(__all__)


# Type checking imports for IDE support
if TYPE_CHECKING:
    from omniintelligence.nodes.node_context_item_writer_effect.node import (
        NodeContextItemWriterEffect as NodeContextItemWriterEffect,
    )
    from omniintelligence.nodes.node_doc_promotion_reducer.node import (
        NodeDocPromotionReducer as NodeDocPromotionReducer,
    )
    from omniintelligence.nodes.node_doc_staleness_detector_effect.node import (
        NodeDocStalenessDetectorEffect as NodeDocStalenessDetectorEffect,
    )
    from omniintelligence.nodes.node_document_fetch_effect.node import (
        NodeDocumentFetchEffect as NodeDocumentFetchEffect,
    )
    from omniintelligence.nodes.node_document_parser_compute.node import (
        NodeDocumentParserCompute as NodeDocumentParserCompute,
    )
    from omniintelligence.nodes.node_enforcement_feedback_effect.node import (
        NodeEnforcementFeedbackEffect as NodeEnforcementFeedbackEffect,
    )
    from omniintelligence.nodes.node_execution_trace_parser_compute.node import (
        NodeExecutionTraceParserCompute as NodeExecutionTraceParserCompute,
    )
    from omniintelligence.nodes.node_git_repo_crawler_effect.node import (
        NodeGitRepoCrawlerEffect as NodeGitRepoCrawlerEffect,
    )
    from omniintelligence.nodes.node_intelligence_orchestrator.node import (
        NodeIntelligenceOrchestrator as NodeIntelligenceOrchestrator,
    )
    from omniintelligence.nodes.node_intelligence_reducer.node import (
        NodeIntelligenceReducer as NodeIntelligenceReducer,
    )
    from omniintelligence.nodes.node_intent_classifier_compute.node import (
        NodeIntentClassifierCompute as NodeIntentClassifierCompute,
    )
    from omniintelligence.nodes.node_intent_drift_detect_compute.node import (
        NodeIntentDriftDetectCompute as NodeIntentDriftDetectCompute,
    )
    from omniintelligence.nodes.node_linear_crawler_effect.node import (
        NodeLinearCrawlerEffect as NodeLinearCrawlerEffect,
    )
    from omniintelligence.nodes.node_pattern_assembler_orchestrator.node import (
        NodePatternAssemblerOrchestrator as NodePatternAssemblerOrchestrator,
    )
    from omniintelligence.nodes.node_pattern_compliance_effect.node import (
        NodePatternComplianceEffect as NodePatternComplianceEffect,
    )
    from omniintelligence.nodes.node_pattern_demotion_effect.node import (
        NodePatternDemotionEffect as NodePatternDemotionEffect,
    )
    from omniintelligence.nodes.node_pattern_extraction_compute.node import (
        NodePatternExtractionCompute as NodePatternExtractionCompute,
    )
    from omniintelligence.nodes.node_pattern_feedback_effect import (
        ROLLING_WINDOW_SIZE as ROLLING_WINDOW_SIZE,
    )
    from omniintelligence.nodes.node_pattern_feedback_effect import (
        ClaudeCodeSessionOutcome as ClaudeCodeSessionOutcome,
    )
    from omniintelligence.nodes.node_pattern_feedback_effect import (
        ClaudeSessionOutcome as ClaudeSessionOutcome,
    )
    from omniintelligence.nodes.node_pattern_feedback_effect import (
        EnumOutcomeRecordingStatus as EnumOutcomeRecordingStatus,
    )
    from omniintelligence.nodes.node_pattern_feedback_effect import (
        ModelSessionOutcomeResult as ModelSessionOutcomeResult,
    )
    from omniintelligence.nodes.node_pattern_feedback_effect import (
        SessionOutcomeInput as SessionOutcomeInput,
    )
    from omniintelligence.nodes.node_pattern_feedback_effect import (
        record_session_outcome as record_session_outcome,
    )
    from omniintelligence.nodes.node_pattern_feedback_effect import (
        update_pattern_rolling_metrics as update_pattern_rolling_metrics,
    )
    from omniintelligence.nodes.node_pattern_feedback_effect.node import (
        NodePatternFeedbackEffect as NodePatternFeedbackEffect,
    )
    from omniintelligence.nodes.node_pattern_learning_compute.node import (
        NodePatternLearningCompute as NodePatternLearningCompute,
    )
    from omniintelligence.nodes.node_pattern_lifecycle_effect.node import (
        NodePatternLifecycleEffect as NodePatternLifecycleEffect,
    )
    from omniintelligence.nodes.node_pattern_matching_compute.node import (
        NodePatternMatchingCompute as NodePatternMatchingCompute,
    )
    from omniintelligence.nodes.node_pattern_promotion_effect.node import (
        NodePatternPromotionEffect as NodePatternPromotionEffect,
    )
    from omniintelligence.nodes.node_pattern_storage_effect.node import (
        NodePatternStorageEffect as NodePatternStorageEffect,
    )
    from omniintelligence.nodes.node_quality_scoring_compute.node import (
        NodeQualityScoringCompute as NodeQualityScoringCompute,
    )
    from omniintelligence.nodes.node_semantic_analysis_compute.node import (
        NodeSemanticAnalysisCompute as NodeSemanticAnalysisCompute,
    )
    from omniintelligence.nodes.node_success_criteria_matcher_compute.node import (
        NodeSuccessCriteriaMatcherCompute as NodeSuccessCriteriaMatcherCompute,
    )
    from omniintelligence.protocols import (
        ProtocolPatternRepository as ProtocolPatternRepository,
    )


__all__ = [
    # Constants
    "ROLLING_WINDOW_SIZE",
    # Models and enums
    "ClaudeCodeSessionOutcome",
    "ClaudeSessionOutcome",
    "EnumOutcomeRecordingStatus",
    "ModelSessionOutcomeResult",
    "SessionOutcomeInput",
    # Nodes — Orchestrators (2)
    "NodeIntelligenceOrchestrator",
    "NodePatternAssemblerOrchestrator",
    # Nodes — Reducers (2)
    "NodeDocPromotionReducer",
    "NodeIntelligenceReducer",
    # Nodes — Computes (10)
    "NodeDocumentParserCompute",
    "NodeExecutionTraceParserCompute",
    "NodeIntentClassifierCompute",
    "NodeIntentDriftDetectCompute",
    "NodePatternExtractionCompute",
    "NodePatternLearningCompute",
    "NodePatternMatchingCompute",
    "NodeQualityScoringCompute",
    "NodeSemanticAnalysisCompute",
    "NodeSuccessCriteriaMatcherCompute",
    # Nodes — Effects (11)
    "NodeContextItemWriterEffect",
    "NodeDocStalenessDetectorEffect",
    "NodeDocumentFetchEffect",
    "NodeGitRepoCrawlerEffect",
    "NodeEnforcementFeedbackEffect",
    "NodeLinearCrawlerEffect",
    "NodePatternComplianceEffect",
    "NodePatternDemotionEffect",
    "NodePatternFeedbackEffect",
    "NodePatternLifecycleEffect",
    "NodePatternPromotionEffect",
    "NodePatternStorageEffect",
    # Protocols
    "ProtocolPatternRepository",
    # Handler functions
    "record_session_outcome",
    "update_pattern_rolling_metrics",
]
