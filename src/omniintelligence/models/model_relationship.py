"""Typed relationship model for knowledge graph edges."""

from __future__ import annotations

import re
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator

from omniintelligence.enums import EnumRelationshipType

# Entity ID format pattern matching the format used in ModelEntity
ENTITY_ID_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")


class RelationshipMetadataDict(TypedDict, total=False):
    """Typed structure for relationship metadata.

    All fields are optional (total=False) to allow flexible metadata
    while maintaining type safety. Common fields for code relationships:
    - Location: file_path, line_number
    - Strength: weight, strength
    - Classification: direction, category
    """

    # Location information
    file_path: str
    line_number: int
    source_line: int
    target_line: int

    # Relationship strength
    weight: float
    strength: float
    importance: float

    # Classification
    direction: str  # e.g., "unidirectional", "bidirectional"
    category: str
    semantic_type: str

    # Context
    context: str
    description: str
    correlation_id: (
        str  # Expected format: UUID (e.g., "550e8400-e29b-41d4-a716-446655440000")
    )

    # Temporal
    discovered_at: str
    version: str


class ModelRelationship(BaseModel):
    """Typed relationship model for knowledge graph edges.

    This model provides type-safe relationship representation for connecting
    entities in the knowledge graph.

    Example:
        >>> relationship = ModelRelationship(
        ...     source_id="ent_class1",
        ...     target_id="ent_class2",
        ...     relationship_type=EnumRelationshipType.EXTENDS,
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "source_id": "ent_class1",
                "target_id": "ent_class2",
                "relationship_type": "EXTENDS",
            }
        },
    )

    source_id: str = Field(
        ...,
        min_length=1,
        description=(
            "Source entity ID. Must follow entity_id format: start with a letter "
            "or underscore, contain only letters, numbers, underscores, and hyphens."
        ),
    )
    target_id: str = Field(
        ...,
        min_length=1,
        description=(
            "Target entity ID. Must follow entity_id format: start with a letter "
            "or underscore, contain only letters, numbers, underscores, and hyphens."
        ),
    )

    @field_validator("source_id", "target_id")
    @classmethod
    def validate_relationship_entity_ids(cls, v: str) -> str:
        """Validate source_id and target_id follow entity_id format."""
        if not ENTITY_ID_PATTERN.match(v):
            raise ValueError(
                f"Entity ID '{v}' must start with a letter or underscore, "
                "and contain only letters, numbers, underscores, and hyphens."
            )
        return v

    relationship_type: EnumRelationshipType = Field(
        ...,
        description="Type of relationship (CONTAINS, CALLS, DEPENDS_ON, etc.)",
    )
    metadata: RelationshipMetadataDict = Field(
        default_factory=lambda: RelationshipMetadataDict(),
        description="Additional relationship metadata with typed fields",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for the relationship (0.0 to 1.0)",
    )


__all__ = ["ModelRelationship", "RelationshipMetadataDict"]
