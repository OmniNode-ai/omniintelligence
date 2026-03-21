# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Quality scoring result model.

Reference: OMN-5675
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelQualityResult(BaseModel):
    """Result of multi-dimensional quality scoring for a code entity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    overall_score: float = Field(ge=0.0, le=1.0, description="Weighted overall score")
    dimensions: dict[str, float] = Field(
        default_factory=dict,
        description="Per-dimension scores (e.g. complexity, maintainability, documentation)",
    )
