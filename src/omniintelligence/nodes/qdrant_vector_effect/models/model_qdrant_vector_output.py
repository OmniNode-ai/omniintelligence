"""Output model for Qdrant Vector Effect."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


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
        description="Number of vectors processed",
    )
    search_results: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Search results with scores and payloads",
    )
    deleted_count: int = Field(
        default=0,
        description="Number of vectors deleted",
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional metadata about the operation",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelQdrantVectorOutput"]
