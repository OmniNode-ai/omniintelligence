"""Models for Intelligence Reducer Node.

This module provides type-safe input and output models for the intelligence reducer.
All models use strong typing with discriminated unions to eliminate dict[str, Any].

ONEX Compliance:
    - Discriminated unions for FSM-specific payload types
    - Frozen immutable models
    - Full type safety for all fields
"""

from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input import (
    ModelIngestionPayload,
    ModelPatternLearningPayload,
    ModelQualityAssessmentPayload,
    ModelReducerInput,
    ModelReducerInputIngestion,
    ModelReducerInputPatternLearning,
    ModelReducerInputQualityAssessment,
    ReducerPayload,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_output import (
    ModelReducerIntent,
    ModelReducerIntentPayload,
    ModelReducerMetadata,
    ModelReducerOutput,
)

__all__ = [
    "ModelIngestionPayload",
    "ModelPatternLearningPayload",
    "ModelQualityAssessmentPayload",
    "ModelReducerInput",
    "ModelReducerInputIngestion",
    "ModelReducerInputPatternLearning",
    "ModelReducerInputQualityAssessment",
    "ModelReducerIntent",
    "ModelReducerIntentPayload",
    "ModelReducerMetadata",
    "ModelReducerOutput",
    "ReducerPayload",
]
