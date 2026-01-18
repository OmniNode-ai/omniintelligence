"""Output model for Entity Extraction Compute."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


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
        description="Total number of extracted entities",
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional metadata about the extraction",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelEntityExtractionOutput"]
