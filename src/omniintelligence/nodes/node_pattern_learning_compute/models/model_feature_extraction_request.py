# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for HandlerFeatureExtraction."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_pattern_learning_compute.models.model_pattern_learning_input import (
    TrainingDataItemDict,
)


class ModelFeatureExtractionRequest(BaseModel):
    """Typed inputs for HandlerFeatureExtraction."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    items: Sequence[TrainingDataItemDict]
