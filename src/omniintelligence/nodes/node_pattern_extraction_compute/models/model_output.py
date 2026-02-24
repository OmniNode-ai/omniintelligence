# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output Model for Pattern Extraction Compute Node."""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_pattern_extraction_compute.models.model_extraction_metrics import (
    ModelExtractionMetrics,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_insight import (
    ModelCodebaseInsight,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_pattern_extraction_metadata import (
    ModelPatternExtractionMetadata,
)


class ModelPatternExtractionOutput(BaseModel):
    """Output from the Pattern Extraction Compute node."""

    success: bool = Field(
        ...,
        description="Whether extraction completed successfully",
    )
    new_insights: tuple[ModelCodebaseInsight, ...] = Field(
        default=(),
        description="Newly discovered insights",
    )
    updated_insights: tuple[ModelCodebaseInsight, ...] = Field(
        default=(),
        description="Existing insights that were updated with new evidence",
    )
    metrics: ModelExtractionMetrics = Field(
        default_factory=ModelExtractionMetrics,
        description="Extraction metrics",
    )
    metadata: ModelPatternExtractionMetadata = Field(
        default_factory=ModelPatternExtractionMetadata,
        description="Execution metadata",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPatternExtractionOutput"]
