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
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumEntityType, EnumRelationshipType


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
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional entity metadata (file_path, line numbers, etc.)",
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
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional relationship metadata",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for the relationship (0.0 to 1.0)",
    )


__all__ = [
    "ModelEntity",
    "ModelRelationship",
]
