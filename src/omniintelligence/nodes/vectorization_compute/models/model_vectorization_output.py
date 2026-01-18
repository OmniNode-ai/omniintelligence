"""Output model for Vectorization Compute."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelVectorizationOutput(BaseModel):
    """Output model for vectorization operations.

    This model represents the result of generating embeddings.
    """

    success: bool = Field(
        ...,
        description="Whether vectorization succeeded",
    )
    embeddings: list[float] = Field(
        ...,
        description="Generated embeddings",
    )
    model_used: str = Field(
        ...,
        description="Model used for embedding generation",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the embedding",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelVectorizationOutput"]
