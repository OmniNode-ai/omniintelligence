# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Models for Intelligence Reducer Node.

This module provides type-safe input and output models for the intelligence reducer.
All models use strong typing with discriminated unions to eliminate dict[str, Any].

ONEX Compliance:
    - Discriminated unions for FSM-specific payload types
    - Frozen immutable models
    - Full type safety for all fields
"""

from omniintelligence.nodes.node_intelligence_reducer.models.model_ingestion_payload import (
    ModelIngestionPayload,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_intelligence_state import (
    ModelIntelligenceState,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_pattern_learning_payload import (
    ModelPatternLearningPayload,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_pattern_lifecycle_reducer_input import (
    ModelPatternLifecycleReducerInput,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_payload_update_pattern_status import (
    ModelPayloadUpdatePatternStatus,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_quality_assessment_payload import (
    ModelQualityAssessmentPayload,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input import (
    ModelReducerInput,
    ReducerPayload,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input_ingestion import (
    ModelReducerInputIngestion,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input_pattern_learning import (
    ModelReducerInputPatternLearning,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input_pattern_lifecycle import (
    ModelReducerInputPatternLifecycle,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input_quality_assessment import (
    ModelReducerInputQualityAssessment,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_intent import (
    ModelReducerIntent,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_intent_payload import (
    ModelReducerIntentPayload,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_metadata import (
    ModelReducerMetadata,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_output import (
    ModelReducerOutput,
)

__all__ = [
    "ModelIntelligenceState",
    "ModelIngestionPayload",
    "ModelPatternLearningPayload",
    "ModelPatternLifecycleReducerInput",
    "ModelPayloadUpdatePatternStatus",
    "ModelQualityAssessmentPayload",
    "ModelReducerInput",
    "ModelReducerInputIngestion",
    "ModelReducerInputPatternLearning",
    "ModelReducerInputPatternLifecycle",
    "ModelReducerInputQualityAssessment",
    "ModelReducerIntent",
    "ModelReducerIntentPayload",
    "ModelReducerMetadata",
    "ModelReducerOutput",
    "ReducerPayload",
]
