"""Output model for PostgreSQL Pattern Effect."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class PatternResultDict(TypedDict, total=False):
    """Typed structure for a pattern query result.

    Provides type-safe fields for pattern data returned from queries.
    """

    # Identification
    pattern_id: str
    pattern_name: str
    pattern_type: str
    category: str

    # Content
    signature: str
    description: str
    keywords: list[str]
    example_code: str

    # Quality metrics
    confidence: float
    usage_count: int
    success_rate: float

    # Metadata
    source_file: str
    language: str
    framework: str
    created_at: str
    updated_at: str


class PostgresOperationMetadataDict(TypedDict, total=False):
    """Typed structure for PostgreSQL operation metadata.

    Provides type-safe fields for operation metadata.
    """

    # Processing info
    processing_time_ms: int
    timestamp: str

    # Query stats
    query_execution_ms: int
    total_matches: int

    # Status
    status: str
    message: str


class ModelPostgresPatternOutput(BaseModel):
    """Output model for PostgreSQL pattern operations.

    This model represents the result of pattern storage operations.

    All fields use strong typing without dict[str, Any].
    """

    success: bool = Field(
        ...,
        description="Whether the pattern operation succeeded",
    )
    pattern_id: str | None = Field(
        default=None,
        description="ID of the stored/updated pattern",
    )
    patterns: list[PatternResultDict] = Field(
        default_factory=list,
        description="Query results with typed pattern fields",
    )
    rows_affected: int = Field(
        default=0,
        description="Number of rows affected by the operation",
    )
    metadata: PostgresOperationMetadataDict | None = Field(
        default=None,
        description="Additional metadata about the operation with typed fields",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelPostgresPatternOutput",
    "PatternResultDict",
    "PostgresOperationMetadataDict",
]
