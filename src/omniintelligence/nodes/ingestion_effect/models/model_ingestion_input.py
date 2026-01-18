"""Input model for Ingestion Effect (STUB)."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, Field, model_validator


class ModelIngestionInput(BaseModel):
    """Input model for ingestion operations (STUB).

    This model represents the input for document ingestion operations.
    This is a stub implementation for forward compatibility.

    Field Naming:
        - source_path: Standardized path field (alias: document_path for backward compatibility)
        - options: Standardized options field (alias: ingestion_parameters for backward compatibility)
    """

    source_path: str | None = Field(
        default=None,
        min_length=1,
        description="Path to the source document to ingest",
        validation_alias="document_path",
    )
    content: str | None = Field(
        default=None,
        min_length=1,
        description="Raw content to ingest (alternative to path)",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Options for ingestion (format detection, preprocessing)",
        validation_alias="ingestion_parameters",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )

    @model_validator(mode="after")
    def validate_has_content(self) -> Self:
        """Validate that either content or source_path is provided."""
        if not self.content and not self.source_path:
            raise ValueError("Either content or source_path must be provided")
        return self

    model_config = {"frozen": True, "extra": "forbid", "populate_by_name": True}


__all__ = ["ModelIngestionInput"]
