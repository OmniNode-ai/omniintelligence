# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for HandlerSimilarity."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    ExtractedFeaturesDict,
    SimilarityWeightsDict,
)


class ModelSimilarityRequest(BaseModel):
    """Typed inputs for HandlerSimilarity."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    features_a: ExtractedFeaturesDict
    features_b: ExtractedFeaturesDict
    weights: SimilarityWeightsDict | None = None
