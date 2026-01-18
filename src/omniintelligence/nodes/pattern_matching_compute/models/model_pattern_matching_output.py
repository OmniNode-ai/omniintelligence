"""Output model for Pattern Matching Compute."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelPatternMatchingOutput(BaseModel):
    """Output model for pattern matching operations.

    This model represents the result of matching code patterns.
    """

    success: bool = Field(
        ...,
        description="Whether pattern matching succeeded",
    )
    patterns_matched: list[str] = Field(
        default_factory=list,
        description="List of matched pattern names",
    )
    pattern_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Confidence scores for each matched pattern",
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional metadata about the matching",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPatternMatchingOutput"]
