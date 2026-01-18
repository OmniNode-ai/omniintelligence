"""Output model for Ingestion Effect (STUB)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelIngestionOutput(BaseModel):
    """Output model for ingestion operations (STUB).

    This model represents the result of document ingestion operations.
    This is a stub implementation for forward compatibility.
    """

    success: bool = Field(
        ...,
        description="Whether ingestion succeeded",
    )
    ingested_content: str | None = Field(
        default=None,
        description="Ingested and processed content",
    )
    content_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about the ingested content",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the ingestion",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelIngestionOutput"]
