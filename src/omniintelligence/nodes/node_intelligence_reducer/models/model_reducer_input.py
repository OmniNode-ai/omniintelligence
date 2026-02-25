# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input models for Intelligence Reducer.

This module provides type-safe input models for the intelligence reducer node.
Payload types are discriminated by FSM type to ensure full type safety without
relying on dict[str, Any].

ONEX Compliance:
    - Strong typing for all payload fields
    - Discriminated unions based on fsm_type
    - Frozen immutable models
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from omniintelligence.nodes.node_intelligence_reducer.models.model_ingestion_payload import (
    ModelIngestionPayload,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_pattern_learning_payload import (
    ModelPatternLearningPayload,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_pattern_lifecycle_reducer_input import (
    ModelPatternLifecycleReducerInput,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_quality_assessment_payload import (
    ModelQualityAssessmentPayload,
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

# =============================================================================
# Union Type for All Payloads
# =============================================================================

# Type alias for all valid payload types
ReducerPayload = (
    ModelIngestionPayload | ModelPatternLearningPayload | ModelQualityAssessmentPayload
)


# =============================================================================
# Discriminated union for all input types
# =============================================================================
# Pydantic will automatically select the correct model based on fsm_type value
ModelReducerInput = Annotated[
    ModelReducerInputIngestion
    | ModelReducerInputPatternLearning
    | ModelReducerInputQualityAssessment
    | ModelReducerInputPatternLifecycle,
    Field(discriminator="fsm_type"),
]


__all__ = [
    "ModelIngestionPayload",
    "ModelPatternLearningPayload",
    "ModelPatternLifecycleReducerInput",
    "ModelQualityAssessmentPayload",
    "ModelReducerInput",
    "ModelReducerInputIngestion",
    "ModelReducerInputPatternLearning",
    "ModelReducerInputPatternLifecycle",
    "ModelReducerInputQualityAssessment",
    "ReducerPayload",
]
