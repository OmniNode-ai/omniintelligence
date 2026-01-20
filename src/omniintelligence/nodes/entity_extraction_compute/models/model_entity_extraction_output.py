"""Output model for Entity Extraction Compute."""

from __future__ import annotations

from typing import Self, TypedDict

from pydantic import BaseModel, Field, model_validator

from omniintelligence.models.model_entity import ModelEntity


class EntityExtractionMetadataDict(TypedDict, total=False):
    """Typed structure for entity extraction metadata.

    Contains information about the extraction process itself.
    """

    # Processing info
    extraction_duration_ms: int
    algorithm_version: str
    model_name: str

    # Input statistics
    input_length: int
    input_line_count: int
    source_file: str
    source_language: str

    # Output statistics
    total_entities_found: int
    entities_filtered: int
    confidence_threshold: float

    # Entity type breakdown
    entity_type_counts: dict[str, int]

    # Request context
    correlation_id: str  # Expected format: UUID (e.g., "550e8400-e29b-41d4-a716-446655440000")
    timestamp_utc: str


class ModelEntityExtractionOutput(BaseModel):
    """Output model for entity extraction operations.

    This model represents the result of extracting entities from code.
    Uses typed ModelEntity instances for proper validation and type safety.

    The entity_count field is always computed from the entities list,
    ensuring consistency between the count and actual entities.

    Example:
        >>> from omniintelligence.enums import EnumEntityType
        >>> output = ModelEntityExtractionOutput(
        ...     success=True,
        ...     entities=[
        ...         ModelEntity(
        ...             entity_id="ent_1",
        ...             entity_type=EnumEntityType.CLASS,
        ...             name="MyClass",
        ...         )
        ...     ],
        ... )
        >>> output.entity_count  # Always computed from list
        1
    """

    success: bool = Field(
        ...,
        description="Whether entity extraction succeeded",
    )
    entities: list[ModelEntity] = Field(
        default_factory=list,
        description="List of extracted entities with their metadata",
    )
    entity_count: int = Field(
        default=0,
        ge=0,
        description="Total number of extracted entities (computed from entities list)",
    )
    metadata: EntityExtractionMetadataDict | None = Field(
        default=None,
        description="Additional typed metadata about the extraction process",
    )

    @model_validator(mode="after")
    def compute_entity_count(self) -> Self:
        """Compute entity_count from entities list unconditionally.

        This validator runs after all fields are populated (mode="after"),
        ensuring it fires even when the entities list is empty.

        The count is always derived from the actual list length, ensuring
        consistency without requiring sentinel values or conditional logic.

        Returns:
            Self with computed entity_count.
        """
        # Unconditionally compute count from list - use object.__setattr__ since model is frozen
        object.__setattr__(self, "entity_count", len(self.entities))
        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["EntityExtractionMetadataDict", "ModelEntityExtractionOutput"]
