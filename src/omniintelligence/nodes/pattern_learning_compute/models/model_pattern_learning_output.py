"""Output model for Pattern Learning Compute (STUB)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelPatternLearningOutput(BaseModel):
    """Output model for pattern learning operations (STUB).

    This model represents the result of pattern learning operations.
    This is a stub implementation for forward compatibility.
    """

    success: bool = Field(
        ...,
        description="Whether pattern learning succeeded",
    )
    learned_patterns: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of learned patterns",
    )
    metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Learning metrics (accuracy, loss, etc.)",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the learning",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPatternLearningOutput"]
