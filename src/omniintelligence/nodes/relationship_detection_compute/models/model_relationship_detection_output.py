"""Output model for Relationship Detection Compute."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelRelationshipDetectionOutput(BaseModel):
    """Output model for relationship detection operations.

    This model represents the result of detecting relationships.
    """

    success: bool = Field(
        ...,
        description="Whether relationship detection succeeded",
    )
    relationships: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of detected relationships with their metadata",
    )
    relationship_count: int = Field(
        default=0,
        description="Total number of detected relationships",
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional metadata about the detection",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelRelationshipDetectionOutput"]
