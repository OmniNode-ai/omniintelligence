"""Output model for Entity Extraction Compute."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ModelEntityExtractionOutput(BaseModel):
    """Output model for entity extraction operations.

    This model represents the result of extracting entities from code.
    """

    success: bool = Field(
        ...,
        description="Whether entity extraction succeeded",
    )
    entities: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of extracted entities with their metadata",
    )
    entity_count: int = Field(
        default=0,
        ge=0,
        description="Total number of extracted entities",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the extraction",
    )

    @field_validator("entity_count")
    @classmethod
    def validate_entity_count(cls, v: int, info: Any) -> int:
        """Validate that entity_count matches the length of entities list."""
        entities = info.data.get("entities", [])
        if entities and v != len(entities):
            raise ValueError(
                f"entity_count ({v}) must match len(entities) ({len(entities)})"
            )
        return v

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelEntityExtractionOutput"]
