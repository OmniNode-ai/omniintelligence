"""Output model for Relationship Detection Compute."""

from __future__ import annotations

from typing import Self, TypedDict

from pydantic import BaseModel, Field, model_validator

from omniintelligence.models.model_entity import ModelRelationship


class DetectionMetadataDict(TypedDict, total=False):
    """Typed structure for relationship detection metadata.

    Contains information about the detection process.
    """

    # Processing info
    detection_duration_ms: int
    algorithm_version: str
    model_name: str

    # Input statistics
    input_entity_count: int
    entity_types_analyzed: list[str]

    # Output statistics
    relationships_found: int
    relationships_filtered: int
    confidence_threshold: float

    # Request context
    correlation_id: str
    timestamp_utc: str


class ModelRelationshipDetectionOutput(BaseModel):
    """Output model for relationship detection operations.

    This model represents the result of detecting relationships.
    Uses typed ModelRelationship instances for proper validation and type safety.
    """

    success: bool = Field(
        ...,
        description="Whether relationship detection succeeded",
    )
    relationships: list[ModelRelationship] = Field(
        default_factory=list,
        description="List of detected relationships with their metadata",
    )
    relationship_count: int = Field(
        default=0,
        ge=0,
        description="Total number of detected relationships",
    )
    metadata: DetectionMetadataDict | None = Field(
        default=None,
        description="Additional typed metadata about the detection",
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


__all__ = ["DetectionMetadataDict", "ModelRelationshipDetectionOutput"]
