"""Output model for Qdrant Vector Effect."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class VectorSearchResultDict(TypedDict, total=False):
    """Typed structure for vector search results.

    Provides stronger typing for search result entries from Qdrant.
    With total=False, all fields are optional.
    """

    id: str | int
    score: float
    payload: dict[str, Any]
    vector: list[float]


class QdrantOperationMetadataDict(TypedDict, total=False):
    """Typed structure for Qdrant operation metadata."""

    status: str
    message: str
    tracking_url: str
    collection_name: str
    operation_type: str
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
    "VectorSearchResultDict",
]
