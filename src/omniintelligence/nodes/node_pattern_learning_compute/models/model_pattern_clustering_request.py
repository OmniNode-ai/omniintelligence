# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for HandlerPatternClustering."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
    DEFAULT_CLUSTERING_THRESHOLD,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    ExtractedFeaturesDict,
    SimilarityWeightsDict,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.replay import (
    NULL_EMITTER,
    ReplayArtifactEmitter,
)


class ModelPatternClusteringRequest(BaseModel):
    """Typed inputs for HandlerPatternClustering."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    features_list: list[ExtractedFeaturesDict]
    threshold: float = DEFAULT_CLUSTERING_THRESHOLD
    weights: SimilarityWeightsDict | None = None
    max_input_items: int = 500
    replay_emitter: ReplayArtifactEmitter = NULL_EMITTER
