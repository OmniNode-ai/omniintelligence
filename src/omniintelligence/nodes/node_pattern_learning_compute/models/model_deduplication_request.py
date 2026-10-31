# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for HandlerDeduplication."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
    DEFAULT_DEDUPLICATION_THRESHOLD,
    NEAR_THRESHOLD_MARGIN,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    PatternClusterDict,
    SimilarityWeightsDict,
)


class ModelDeduplicationRequest(BaseModel):
    """Typed inputs for HandlerDeduplication."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    clusters: list[PatternClusterDict]
    confidence_scores: dict[str, float] | None = None
    similarity_threshold: float = DEFAULT_DEDUPLICATION_THRESHOLD
    near_threshold_margin: float = NEAR_THRESHOLD_MARGIN
    weights: SimilarityWeightsDict | None = None
