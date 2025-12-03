"""
Entity Models for omniintelligence.

Models for entities and relationships in the knowledge graph.
"""

from datetime import datetime, UTC
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumEntityType, EnumRelationshipType


def _utc_now() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(UTC)


class ModelEntity(BaseModel):
    """Entity model for knowledge graph."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_id": "ent_123",
                "entity_type": "CLASS",
                "name": "MyClass",
                "metadata": {"file_path": "src/main.py"},
            }
        }
    )

    entity_id: str = Field(..., description="Unique entity identifier")
    entity_type: EnumEntityType = Field(..., description="Entity type")
    name: str = Field(..., description="Entity name")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Entity metadata"
    )
    created_at: datetime = Field(
        default_factory=_utc_now, description="Creation timestamp"
    )


class ModelRelationship(BaseModel):
    """Relationship model for knowledge graph."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_id": "ent_123",
                "target_id": "ent_456",
                "relationship_type": "CONTAINS",
            }
        }
    )

    source_id: str = Field(..., description="Source entity ID")
    target_id: str = Field(..., description="Target entity ID")
    relationship_type: EnumRelationshipType = Field(
        ..., description="Relationship type"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Relationship metadata"
    )


__all__ = [
    "ModelEntity",
    "ModelRelationship",
]
