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
    correlation_id: str  # Expected format: UUID (e.g., "550e8400-e29b-41d4-a716-446655440000")
    timestamp_utc: str


class ModelRelationshipDetectionOutput(BaseModel):
    """Output model for relationship detection operations.

    This model represents the result of detecting relationships.
    Uses typed ModelRelationship instances for proper validation and type safety.

    The relationship_count field is always computed from the relationships list,
    ensuring consistency between the count and actual relationships.

    Example:
        >>> from omniintelligence.enums import EnumRelationshipType
        >>> output = ModelRelationshipDetectionOutput(
        ...     success=True,
        ...     relationships=[
        ...         ModelRelationship(
        ...             source_id="ent_1",
        ...             target_id="ent_2",
        ...             relationship_type=EnumRelationshipType.CALLS,
        ...         )
        ...     ],
        ... )
        >>> output.relationship_count  # Always computed from list
        1
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
        description="Total number of detected relationships (computed from relationships list)",
    )
    metadata: DetectionMetadataDict | None = Field(
        default=None,
        description="Additional typed metadata about the detection",
    )

    @model_validator(mode="after")
    def compute_relationship_count(self) -> Self:
        """Compute relationship_count from relationships list unconditionally.

        This validator runs after all fields are populated (mode="after"),
        ensuring it fires even when the relationships list is empty.

        The count is always derived from the actual list length, ensuring
        consistency without requiring sentinel values or conditional logic.

        Returns:
            Self with computed relationship_count.
        """
        # Unconditionally compute count from list - use object.__setattr__ since model is frozen
        object.__setattr__(self, "relationship_count", len(self.relationships))
        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["DetectionMetadataDict", "ModelRelationshipDetectionOutput"]
