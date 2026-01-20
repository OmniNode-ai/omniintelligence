"""Input model for Ingestion Effect (STUB)."""

from __future__ import annotations

from typing import Self, TypedDict

from pydantic import BaseModel, Field, model_validator


class IngestionOptionsDict(TypedDict, total=False):
    """Typed structure for ingestion options.

    Provides type-safe fields for configuring document ingestion.
    """

    # Format detection
    detect_format: bool
    force_format: str  # "markdown", "python", "typescript", "json", etc.

    # Preprocessing
    extract_docstrings: bool
    extract_comments: bool
    strip_whitespace: bool

    # Vectorization
    vectorize: bool
    embedding_model: str
    chunk_size: int
    chunk_overlap: int

    # Entity extraction
    extract_entities: bool
    entity_types: list[str]

    # Quality assessment
    assess_quality: bool
    quality_threshold: float

    # Storage
    collection_name: str
    overwrite_existing: bool


class ModelIngestionInput(BaseModel):
    """Input model for ingestion operations (STUB).

    This model represents the input for document ingestion operations.
    This is a stub implementation for forward compatibility.

    Field Naming:
        - source_path: Standardized path field (alias: document_path for backward compatibility)
        - options: Standardized options field (alias: ingestion_parameters for backward compatibility)

    All fields use strong typing without dict[str, Any].
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
    options: IngestionOptionsDict = Field(
        default_factory=lambda: IngestionOptionsDict(),
        description="Options for ingestion with typed fields",
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


__all__ = [
    "IngestionOptionsDict",
    "ModelIngestionInput",
]
