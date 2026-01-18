"""Input model for Relationship Detection Compute."""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.enums import EnumRelationshipType
from omniintelligence.models.model_entity import ModelEntity


class ModelRelationshipDetectionContext(BaseModel):
    """Structured context for relationship detection operations.

    Provides fully typed context fields for relationship detection,
    replacing the previous dict[str, Any].
    """

    # Source context
    source_path: str | None = Field(
        default=None,
        description="Path to the source file being analyzed",
    )
    repository_name: str | None = Field(
        default=None,
        description="Name of the source repository",
    )
    branch: str | None = Field(
        default=None,
        description="Git branch name",
    )

    # Detection parameters
    min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for detected relationships (0.0 to 1.0)",
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum relationship traversal depth",
    )
    relationship_types: list[EnumRelationshipType] = Field(
        default_factory=list,
        description="Filter for specific relationship types (empty = all types)",
    )
    include_transitive: bool = Field(
        default=False,
        description="Whether to include transitive relationships",
    )

    # Request metadata
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for distributed tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelRelationshipDetectionInput(BaseModel):
    """Input model for relationship detection operations.

    This model represents the input for detecting relationships between entities.
    Uses typed ModelEntity instances for proper validation and type safety.
    """

    entities: list[ModelEntity] = Field(
        ...,
        min_length=1,
        description="List of entities to analyze for relationships",
    )
    context: ModelRelationshipDetectionContext = Field(
        default_factory=ModelRelationshipDetectionContext,
        description="Structured context for relationship detection",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelRelationshipDetectionContext",
    "ModelRelationshipDetectionInput",
]
