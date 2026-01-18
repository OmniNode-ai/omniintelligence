"""Output model for Entity Extraction Compute."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="after")
    def validate_entity_count_matches_list(self) -> Self:
        """Validate that entity_count matches the length of entities list.

        This validator runs after all fields are populated, ensuring
        proper validation even when entities list is empty.
        """
        actual_count = len(self.entities)
        if self.entity_count != actual_count:
            raise ValueError(
                f"entity_count ({self.entity_count}) must match "
                f"len(entities) ({actual_count})"
            )
        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelEntityExtractionOutput"]
