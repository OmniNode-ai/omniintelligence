"""Input model for Qdrant Vector Effect."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelQdrantVectorInput(BaseModel):
    """Input model for Qdrant vector operations.

    This model represents the input for vector storage operations.
    """

    operation: str = Field(
        default="upsert_vectors",
        description="Type of operation (upsert_vectors, search_vectors, delete_vectors)",
    )
    collection_name: str = Field(
        default="default",
        description="Name of the Qdrant collection",
    )
    vectors: list[list[float]] = Field(
        default_factory=list,
        description="Vectors to upsert",
    )
    payloads: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Payloads associated with vectors",
    )
    ids: list[str] = Field(
        default_factory=list,
        description="IDs for the vectors",
    )
    query_vector: Optional[list[float]] = Field(
        default=None,
        description="Query vector for search operations",
    )
    top_k: int = Field(
        default=10,
        description="Number of results to return for search",
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Filters for search or delete operations",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracing",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelQdrantVectorInput"]
