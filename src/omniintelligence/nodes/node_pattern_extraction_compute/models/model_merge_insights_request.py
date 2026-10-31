# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request for merging duplicate codebase insights."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_extraction_compute.models.model_insight import (
    ModelCodebaseInsight,
)


class ModelMergeInsightsRequest(BaseModel):
    """Request for merging duplicate codebase insights."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    new: ModelCodebaseInsight = Field(description="New insight to merge")
    existing: ModelCodebaseInsight = Field(description="Existing canonical insight")


__all__ = ["ModelMergeInsightsRequest"]
