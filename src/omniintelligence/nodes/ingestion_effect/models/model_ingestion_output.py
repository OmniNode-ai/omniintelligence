"""Output model for Ingestion Effect (STUB)."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class ContentMetadataDict(TypedDict, total=False):
    """Typed structure for ingested content metadata.

    Provides stronger typing for content metadata fields.
    With total=False, all fields are optional.
    """

    source_path: str
    content_type: str
    language: str
    encoding: str
    file_size_bytes: int
    line_count: int
    character_count: int
    checksum: str


class IngestionOperationMetadataDict(TypedDict, total=False):
    """Typed structure for ingestion operation metadata."""

    status: str
    message: str
    tracking_url: str
    processing_time_ms: float
    ingestion_mode: str
    version: str


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
    content_metadata: ContentMetadataDict = Field(
        default_factory=lambda: ContentMetadataDict(),
        description="Metadata about the ingested content. Uses ContentMetadataDict "
        "with total=False, allowing any subset of typed fields.",
    )
    metadata: IngestionOperationMetadataDict | None = Field(
        default=None,
        description="Additional metadata about the ingestion. Uses IngestionOperationMetadataDict "
        "with total=False, allowing any subset of typed fields.",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ContentMetadataDict",
    "IngestionOperationMetadataDict",
    "ModelIngestionOutput",
]
