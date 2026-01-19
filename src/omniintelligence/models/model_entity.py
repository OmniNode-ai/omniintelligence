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

import re
from datetime import UTC, datetime
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator

from omniintelligence.enums import EnumEntityType, EnumRelationshipType

# Entity ID format pattern:
# - Must start with a letter or underscore
# - Can contain letters, numbers, underscores, and hyphens
# - Optional prefix followed by underscore (e.g., "ent_", "cls_", "fn_")
# - Examples: "ent_abc123", "cls_MyClass", "fn_process_data", "node_1234"
ENTITY_ID_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")


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
    correlation_id: (
        str  # Expected format: UUID (e.g., "550e8400-e29b-41d4-a716-446655440000")
    )
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
    correlation_id: (
        str  # Expected format: UUID (e.g., "550e8400-e29b-41d4-a716-446655440000")
    )

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
        description=(
            "Unique entity identifier. Must start with a letter or underscore, "
            "and contain only letters, numbers, underscores, and hyphens. "
            "Examples: 'ent_abc123', 'cls_MyClass', 'fn_process_data'"
        ),
    )

    @field_validator("entity_id")
    @classmethod
    def validate_entity_id_format(cls, v: str) -> str:
        """Validate entity_id follows the expected format.

        Valid formats:
            - Must start with a letter or underscore
            - Can contain letters, numbers, underscores, and hyphens
            - Common prefixes: ent_, cls_, fn_, mod_, var_, node_

        Args:
            v: The entity_id value to validate.

        Returns:
            The validated entity_id.

        Raises:
            ValueError: If entity_id doesn't match the expected format.
        """
        if not ENTITY_ID_PATTERN.match(v):
            raise ValueError(
                f"entity_id '{v}' must start with a letter or underscore, "
                "and contain only letters, numbers, underscores, and hyphens. "
                "Examples: 'ent_abc123', 'cls_MyClass', 'fn_process_data'"
            )
        return v

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
        """Validate source_id and target_id follow entity_id format.

        Args:
            v: The entity ID value to validate.

        Returns:
            The validated entity ID.

        Raises:
            ValueError: If the ID doesn't match the expected format.
        """
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


__all__ = [
    "EntityMetadataDict",
    "ModelEntity",
    "ModelRelationship",
    "RelationshipMetadataDict",
]
