"""Output model for Success Criteria Matcher Compute."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelSuccessCriteriaOutput(BaseModel):
    """Output model for success criteria matching operations.

    This model represents the result of matching against success criteria.
    """

    success: bool = Field(
        ...,
        description="Whether criteria matching succeeded",
    )
    matched_criteria: list[str] = Field(
        default_factory=list,
        description="List of matched criteria identifiers",
    )
    match_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall match score (0.0 to 1.0)",
    )
    unmatched_criteria: list[str] = Field(
        default_factory=list,
        description="List of unmatched criteria identifiers",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the matching",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelSuccessCriteriaOutput"]
