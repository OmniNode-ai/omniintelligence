# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request for core model pattern extraction."""

from __future__ import annotations

from omnibase_core.models.intelligence.model_pattern_extraction_input import (
    ModelPatternExtractionInput as CoreInput,
)
from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_extraction_compute.models.model_extraction_config import (
    ModelExtractionConfig,
)


class ModelCoreExtractionRequest(BaseModel):
    """Request for core model pattern extraction."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    input_data: CoreInput = Field(description="Core pattern extraction input")
    extraction_config: ModelExtractionConfig | None = Field(
        default=None, description="Optional extraction configuration override"
    )


__all__ = ["ModelCoreExtractionRequest"]
