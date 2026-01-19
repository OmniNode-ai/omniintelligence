"""Output model for Qdrant Vector Effect."""

from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, Field

# Literal type for Qdrant operation types
QdrantOperationType = Literal[
    "upsert",
    "search",
    "delete",
    "scroll",
    "count",
    "get",
    "recommend",
    "batch_upsert",
    "batch_delete",
]


class VectorPayloadDict(TypedDict, total=False):
    """Typed structure for vector payload data.

    Provides type-safe fields for vector payloads stored in Qdrant.
    All fields are optional (total=False) for flexibility.
    """

    # Document identification
    document_id: str
    document_hash: str
    file_path: str
    source_type: str

    # Content metadata
    content_type: str
    language: str
    title: str
    description: str

    # Classification
    entity_type: str
    category: str
    tags: list[str]

    # Quality metrics
    quality_score: float
    confidence: float

    # Timestamps
    created_at: str
    updated_at: str


class VectorSearchResultDict(TypedDict, total=False):
    """Typed structure for vector search results.

    Provides stronger typing for search result entries from Qdrant.
    With total=False, all fields are optional.
    """

    id: str | int
    score: float
    payload: VectorPayloadDict
    vector: list[float]


class QdrantOperationMetadataDict(TypedDict, total=False):
    """Typed structure for Qdrant operation metadata."""

    status: str
    message: str
    tracking_url: str
    collection_name: str
    operation_type: QdrantOperationType  # Literal type for valid Qdrant operations
    duration_ms: float


class ModelQdrantVectorOutput(BaseModel):
    """Output model for Qdrant vector operations.

    This model represents the result of vector storage operations.
    """

    success: bool = Field(
        ...,
        description="Whether the vector operation succeeded",
    )
    vectors_processed: int = Field(
        default=0,
        ge=0,
        description="Number of vectors processed",
    )
    search_results: list[VectorSearchResultDict] = Field(
        default_factory=list,
        description="Search results with scores and payloads. Uses VectorSearchResultDict "
        "with total=False, allowing any subset of typed fields per entry.",
    )
    deleted_count: int = Field(
        default=0,
        ge=0,
        description="Number of vectors deleted",
    )
    metadata: QdrantOperationMetadataDict | None = Field(
        default=None,
        description="Additional metadata about the operation. Uses QdrantOperationMetadataDict "
        "with total=False, allowing any subset of typed fields.",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelQdrantVectorOutput",
    "QdrantOperationMetadataDict",
    "QdrantOperationType",
    "VectorPayloadDict",
    "VectorSearchResultDict",
]
