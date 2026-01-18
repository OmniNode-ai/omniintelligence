"""Input model for Ingestion Effect (STUB)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelIngestionInput(BaseModel):
    """Input model for ingestion operations (STUB).

    This model represents the input for document ingestion operations.
    This is a stub implementation for forward compatibility.
    """

    document_path: Optional[str] = Field(
        default=None,
        description="Path to the document to ingest",
    )
    content: Optional[str] = Field(
        default=None,
        description="Raw content to ingest (alternative to path)",
    )
    ingestion_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for ingestion (format detection, preprocessing)",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelIngestionInput"]
