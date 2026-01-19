"""Typed entity and relationship models for OmniIntelligence.

These models provide type-safe structures for entities and relationships
used in knowledge graph operations, vector storage, and code analysis.

Usage:
    Instead of using untyped `list[dict[str, Any]]` for entities,
    use the typed models:

    # Before (untyped)
    entities: list[dict[str, Any]] = [{"entity_id": "e1", "name": "Foo", ...}]

    # After (typed)
    entities: list[ModelEntity] = [ModelEntity(entity_id="e1", name="Foo", ...)]
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumEntityType, EnumRelationshipType


class EntityMetadataDict(TypedDict, total=False):
    """Typed structure for entity metadata.

    All fields are optional (total=False) to allow flexible metadata
    while maintaining type safety. Common fields for code entities:
    - Location info: file_path, line_start, line_end, column_start, column_end
    - Scope info: scope, visibility, namespace
    - Documentation: docstring, description, annotations
    """

    # Location information
    file_path: str
    line_start: int
    line_end: int
    column_start: int
    column_end: int

    # Scope and visibility
    scope: str
    visibility: str  # e.g., "public", "private", "protected"
    namespace: str
    module: str
    package: str

    # Documentation
    docstring: str
    description: str
    annotations: list[str]

    # Additional metadata
    language: str
    version: str
    correlation_id: str
    source: str


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
    correlation_id: str

    # Temporal
    discovered_at: str
    version: str


def _utc_now() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(UTC)


class ModelEntity(BaseModel):
    """Typed entity model for knowledge graph and code analysis.

    This model provides type-safe entity representation with validated fields
    for use in entity extraction, vector storage, and graph operations.

    Example:
        >>> entity = ModelEntity(
        ...     entity_id="ent_abc123",
        ...     entity_type=EnumEntityType.CLASS,
        ...     name="MyService",
        ...     metadata={"file_path": "src/services/my_service.py", "line_start": 10},
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "entity_id": "ent_abc123",
                "entity_type": "CLASS",
                "name": "MyService",
                "metadata": {"file_path": "src/services/my_service.py"},
            }
        },
    )

    entity_id: str = Field(
        ...,
        min_length=1,
        description="Unique entity identifier",
    )
    entity_type: EnumEntityType = Field(
        ...,
        description="Type of the entity (CLASS, FUNCTION, MODULE, etc.)",
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Human-readable entity name",
    )
    metadata: EntityMetadataDict = Field(
        default_factory=lambda: EntityMetadataDict(),
        description="Additional entity metadata with typed fields (file_path, line numbers, etc.)",
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        description="Timestamp when the entity was created or discovered",
    )


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
        description="Source entity ID",
    )
    target_id: str = Field(
        ...,
        min_length=1,
        description="Target entity ID",
    )
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


__all__ = [
    "EntityMetadataDict",
    "ModelEntity",
    "ModelRelationship",
    "RelationshipMetadataDict",
]
