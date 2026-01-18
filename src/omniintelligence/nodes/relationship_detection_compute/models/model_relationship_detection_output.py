"""Output model for Relationship Detection Compute."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="after")
    def validate_relationship_count_matches_list(self) -> Self:
        """Validate that relationship_count matches the length of relationships list.

        This validator runs after all fields are populated, ensuring
        proper validation even when relationships list is empty.
        """
        actual_count = len(self.relationships)
        if self.relationship_count != actual_count:
            raise ValueError(
                f"relationship_count ({self.relationship_count}) must match "
                f"len(relationships) ({actual_count})"
            )
        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelRelationshipDetectionOutput"]
