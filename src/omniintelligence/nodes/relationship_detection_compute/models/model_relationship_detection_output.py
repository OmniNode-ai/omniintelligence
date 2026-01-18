"""Output model for Relationship Detection Compute."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


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
        ge=0,
        description="Total number of detected relationships",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the detection",
    )

    @field_validator("relationship_count")
    @classmethod
    def validate_relationship_count(cls, v: int, info: Any) -> int:
        """Validate that relationship_count matches the length of relationships list."""
        relationships = info.data.get("relationships", [])
        if relationships and v != len(relationships):
            raise ValueError(
                f"relationship_count ({v}) must match len(relationships) ({len(relationships)})"
            )
        return v

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelRelationshipDetectionOutput"]
