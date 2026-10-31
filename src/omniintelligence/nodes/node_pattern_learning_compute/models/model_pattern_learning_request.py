# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for HandlerPatternLearning."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
    DEFAULT_PROMOTION_THRESHOLD,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    SimilarityWeightsDict,
)
from omniintelligence.nodes.node_pattern_learning_compute.models.model_pattern_learning_input import (
    LearningParametersDict,
    TrainingDataItemDict,
)


class ModelPatternLearningRequest(BaseModel):
    """Typed inputs for HandlerPatternLearning."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    training_data: Sequence[TrainingDataItemDict]
    parameters: LearningParametersDict | None = None
    similarity_weights: SimilarityWeightsDict | None = None
    promotion_threshold: float = DEFAULT_PROMOTION_THRESHOLD
