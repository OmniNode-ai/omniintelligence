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

    The relationship_count field is auto-computed from the relationships list if not
    explicitly provided, ensuring consistency between the count and actual
    relationships.

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
        >>> output.relationship_count  # Auto-computed
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
        default=-1,
        ge=-1,
        description="Total number of detected relationships (auto-computed if not set)",
    )
    metadata: DetectionMetadataDict | None = Field(
        default=None,
        description="Additional typed metadata about the detection",
    )

    @model_validator(mode="after")
    def validate_and_compute_relationship_count(self) -> Self:
        """Validate and auto-compute relationship_count from relationships list.

        This validator runs after all fields are populated (mode="after"),
        ensuring it fires even when the relationships list is empty.

        Behavior:
            - If relationship_count is -1 (default), auto-compute from len(relationships)
            - If relationship_count is explicitly set, validate it matches len(relationships)

        Returns:
            Self with validated/computed relationship_count.

        Raises:
            ValueError: If explicitly provided relationship_count doesn't match.
        """
        actual_count = len(self.relationships)

        # Auto-compute if using default sentinel value (-1)
        if self.relationship_count == -1:
            # Use object.__setattr__ since model is frozen
            object.__setattr__(self, "relationship_count", actual_count)
        elif self.relationship_count != actual_count:
            raise ValueError(
                f"relationship_count ({self.relationship_count}) must match "
                f"len(relationships) ({actual_count})"
            )
        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["DetectionMetadataDict", "ModelRelationshipDetectionOutput"]
