"""Output model for Quality Scoring Compute."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelQualityScoringOutput(BaseModel):
    """Output model for quality scoring operations.

    This model represents the result of scoring code quality.
    """

    success: bool = Field(
        ...,
        description="Whether quality scoring succeeded",
    )
    quality_score: float = Field(
        default=0.0,
        description="Overall quality score (0.0 to 1.0)",
    )
    dimensions: dict[str, float] = Field(
        default_factory=dict,
        description="Quality scores by dimension (maintainability, complexity, etc.)",
    )
    onex_compliant: bool = Field(
        default=False,
        description="Whether the code is ONEX compliant",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="List of quality improvement recommendations",
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional metadata about the scoring",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelQualityScoringOutput"]
