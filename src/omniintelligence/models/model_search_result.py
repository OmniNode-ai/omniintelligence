# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Typed search result model for vector and semantic search."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field


class SearchResultMetadataDict(TypedDict, total=False):
    """Typed structure for search result metadata.

    Provides type-safe fields for search result metadata.
    """

    # Source information
    file_path: str
    source_type: str
    language: str

    # Entity classification
    entity_type: str
    entity_id: str
    category: str

    # Quality metrics
    quality_score: float
    confidence: float

    # Timestamps
    created_at: str
    indexed_at: str


class ModelSearchResult(BaseModel):
    """Typed search result model for vector and semantic search.

    This model provides type-safe search result representation for use
    with Qdrant vector search, semantic code search, and pattern matching.

    All fields use strong typing without dict[str, Any].

    Example:
        >>> result = ModelSearchResult(
        ...     id="doc_abc123",
        ...     score=0.95,
        ...     content="def calculate_total(): ...",
        ...     metadata={"file_path": "src/utils.py", "entity_type": "FUNCTION"},
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "id": "doc_abc123",
                "score": 0.95,
                "content": "def calculate_total(): ...",
                "metadata": {"file_path": "src/utils.py", "entity_type": "FUNCTION"},
            }
        },
    )

    id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the search result",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score (0.0 to 1.0, higher is more relevant)",
    )
    content: str | None = Field(
        default=None,
        description="Content snippet or full content of the matched document",
    )
    metadata: SearchResultMetadataDict = Field(
        default_factory=lambda: SearchResultMetadataDict(),
        description="Additional metadata about the search result with typed fields",
    )
    vector_id: str | None = Field(
        default=None,
        description="Vector ID in the vector database (if applicable)",
    )
    distance: float | None = Field(
        default=None,
        ge=0.0,
        description="Raw distance metric from vector search (lower is closer)",
    )


__all__ = ["ModelSearchResult", "SearchResultMetadataDict"]
