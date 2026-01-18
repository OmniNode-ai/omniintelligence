"""Input model for Relationship Detection Compute."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelRelationshipDetectionInput(BaseModel):
    """Input model for relationship detection operations.

    This model represents the input for detecting relationships between entities.
    """

    entities: list[dict[str, Any]] = Field(
        ...,
        description="List of entities to analyze for relationships",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for relationship detection",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelRelationshipDetectionInput"]
