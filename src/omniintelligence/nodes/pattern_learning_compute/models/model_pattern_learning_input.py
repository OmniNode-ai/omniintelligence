"""Input model for Pattern Learning Compute (STUB)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelPatternLearningInput(BaseModel):
    """Input model for pattern learning operations (STUB).

    This model represents the input for pattern learning operations.
    This is a stub implementation for forward compatibility.
    """

    training_data: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Training data for pattern learning",
    )
    learning_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the learning algorithm",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPatternLearningInput"]
