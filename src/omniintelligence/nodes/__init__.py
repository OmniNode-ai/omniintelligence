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
from typing import TYPE_CHECKING, Any

# Lazy import map: name -> (module_path, attribute_name)
_LAZY_IMPORT_MAP: dict[str, tuple[str, str]] = {
    # Orchestrators (2)
    "NodeIntelligenceOrchestrator": (
        "omniintelligence.nodes.intelligence_orchestrator.node",
        "NodeIntelligenceOrchestrator",
    ),
    "NodePatternAssemblerOrchestrator": (
        "omniintelligence.nodes.pattern_assembler_orchestrator.node",
        "NodePatternAssemblerOrchestrator",
    ),
    # Reducers (1)
    "NodeIntelligenceReducer": (
        "omniintelligence.nodes.intelligence_reducer.node",
        "NodeIntelligenceReducer",
    ),
    # Effects (1)
    "NodePatternFeedbackEffect": (
        "omniintelligence.nodes.node_pattern_feedback_effect",
        "NodePatternFeedbackEffect",
    ),
    "ModelSessionOutcomeRequest": (
        "omniintelligence.nodes.node_pattern_feedback_effect",
        "ModelSessionOutcomeRequest",
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
        "omniintelligence.nodes.node_pattern_feedback_effect",
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
    # Computes (7)
    "NodeExecutionTraceParserCompute": (
        "omniintelligence.nodes.execution_trace_parser_compute.node",
        "NodeExecutionTraceParserCompute",
    ),
    "NodeIntentClassifierCompute": (
        "omniintelligence.nodes.intent_classifier_compute.node",
        "NodeIntentClassifierCompute",
    ),
    "NodePatternExtractionCompute": (
        "omniintelligence.nodes.pattern_extraction_compute.node",
        "NodePatternExtractionCompute",
    ),
    "NodePatternMatchingCompute": (
        "omniintelligence.nodes.pattern_matching_compute.node",
        "NodePatternMatchingCompute",
    ),
    "NodeQualityScoringCompute": (
        "omniintelligence.nodes.quality_scoring_compute.node",
        "NodeQualityScoringCompute",
    ),
    "NodeSemanticAnalysisCompute": (
        "omniintelligence.nodes.semantic_analysis_compute.node",
        "NodeSemanticAnalysisCompute",
    ),
    "NodeSuccessCriteriaMatcherCompute": (
        "omniintelligence.nodes.success_criteria_matcher_compute.node",
        "NodeSuccessCriteriaMatcherCompute",
    ),
}

# Cache for loaded imports
_lazy_imports: dict[str, Any] = {}


def __getattr__(name: str) -> Any:
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
    from omniintelligence.nodes.execution_trace_parser_compute.node import (
        NodeExecutionTraceParserCompute as NodeExecutionTraceParserCompute,
    )
    from omniintelligence.nodes.intelligence_orchestrator.node import (
        NodeIntelligenceOrchestrator as NodeIntelligenceOrchestrator,
    )
    from omniintelligence.nodes.intelligence_reducer.node import (
        NodeIntelligenceReducer as NodeIntelligenceReducer,
    )
    from omniintelligence.nodes.intent_classifier_compute.node import (
        NodeIntentClassifierCompute as NodeIntentClassifierCompute,
    )
    from omniintelligence.nodes.pattern_assembler_orchestrator.node import (
        NodePatternAssemblerOrchestrator as NodePatternAssemblerOrchestrator,
    )
    from omniintelligence.nodes.pattern_extraction_compute.node import (
        NodePatternExtractionCompute as NodePatternExtractionCompute,
    )
    from omniintelligence.nodes.pattern_matching_compute.node import (
        NodePatternMatchingCompute as NodePatternMatchingCompute,
    )
    from omniintelligence.nodes.quality_scoring_compute.node import (
        NodeQualityScoringCompute as NodeQualityScoringCompute,
    )
    from omniintelligence.nodes.semantic_analysis_compute.node import (
        NodeSemanticAnalysisCompute as NodeSemanticAnalysisCompute,
    )
    from omniintelligence.nodes.success_criteria_matcher_compute.node import (
        NodeSuccessCriteriaMatcherCompute as NodeSuccessCriteriaMatcherCompute,
    )

    from omniintelligence.nodes.node_pattern_feedback_effect import (
        ROLLING_WINDOW_SIZE as ROLLING_WINDOW_SIZE,
        EnumOutcomeRecordingStatus as EnumOutcomeRecordingStatus,
        ModelSessionOutcomeRequest as ModelSessionOutcomeRequest,
        ModelSessionOutcomeResult as ModelSessionOutcomeResult,
        NodePatternFeedbackEffect as NodePatternFeedbackEffect,
        ProtocolPatternRepository as ProtocolPatternRepository,
        record_session_outcome as record_session_outcome,
        update_pattern_rolling_metrics as update_pattern_rolling_metrics,
    )


__all__ = [
    "EnumOutcomeRecordingStatus",
    "ModelSessionOutcomeRequest",
    "ModelSessionOutcomeResult",
    "ROLLING_WINDOW_SIZE",
    "NodeExecutionTraceParserCompute",
    "NodeIntelligenceOrchestrator",
    "NodeIntelligenceReducer",
    "NodeIntentClassifierCompute",
    "NodePatternAssemblerOrchestrator",
    "NodePatternExtractionCompute",
    "NodePatternFeedbackEffect",
    "NodePatternMatchingCompute",
    "NodeQualityScoringCompute",
    "NodeSemanticAnalysisCompute",
    "NodeSuccessCriteriaMatcherCompute",
    "ProtocolPatternRepository",
    "record_session_outcome",
    "update_pattern_rolling_metrics",
]
