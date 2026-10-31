# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for HandlerConfidenceScoring."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
    DEFAULT_MIN_FREQUENCY,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    PatternClusterDict,
)


class ModelConfidenceScoringRequest(BaseModel):
    """Typed inputs for HandlerConfidenceScoring."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    cluster: PatternClusterDict
    min_frequency: int = DEFAULT_MIN_FREQUENCY
