# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for HandlerFeatureExtractionItem."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_pattern_learning_compute.models.model_pattern_learning_input import (
    TrainingDataItemDict,
)


class ModelFeatureExtractionItemRequest(BaseModel):
    """Typed inputs for HandlerFeatureExtractionItem."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    item: TrainingDataItemDict
