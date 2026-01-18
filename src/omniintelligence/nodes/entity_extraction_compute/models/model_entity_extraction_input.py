"""Input model for Entity Extraction Compute."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ModelEntityExtractionInput(BaseModel):
    """Input model for entity extraction operations.

    This model represents the input for extracting entities from code.
    """

    content: str = Field(
        ...,
        description="Content to extract entities from",
    )
    language: str = Field(
        default="python",
        description="Programming language of the content",
    )
    entity_types: list[str] = Field(
        default_factory=lambda: ["class", "function", "variable"],
        description="Types of entities to extract",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelEntityExtractionInput"]
