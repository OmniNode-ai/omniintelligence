# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Typed entity model for knowledge graph and code analysis."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator

from omniintelligence.enums import EnumEntityType

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
        """Validate entity_id follows the expected format."""
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


__all__ = ["EntityMetadataDict", "ModelEntity"]
