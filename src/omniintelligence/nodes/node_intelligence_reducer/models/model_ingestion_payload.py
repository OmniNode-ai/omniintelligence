"""Ingestion payload model for Intelligence Reducer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelIngestionPayload(BaseModel):
    """Payload for INGESTION FSM operations.

    Used for document ingestion workflows: RECEIVED -> PROCESSING -> INDEXED.
    """

    # Document identification
    document_id: str | None = Field(
        default=None,
        description="Unique identifier for the document",
    )
    document_hash: str | None = Field(
        default=None,
        description="Content hash for deduplication",
    )

    # Content fields
    content: str | None = Field(
        default=None,
        min_length=1,
        description="Document content to ingest",
    )
    file_path: str | None = Field(
        default=None,
        min_length=1,
        description="Source file path",
    )
    source_type: str | None = Field(
        default=None,
        description="Source type (e.g., 'file', 'api', 'stream')",
    )

    # Indexing configuration
    indexing_options: dict[str, bool] = Field(
        default_factory=dict,
        description="Indexing options (e.g., {'vectorize': True, 'extract_entities': True})",
    )

    # Error fields (used when action is 'fail')
    failure_reason: str | None = Field(
        default=None,
        description="Reason for failure if action is 'fail'",
    )
    error_code: str | None = Field(
        default=None,
        description="Error code for failure categorization",
    )
    error_details: str | None = Field(
        default=None,
        description="Detailed error information",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


__all__ = ["ModelIngestionPayload"]
