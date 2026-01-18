"""Input model for Vectorization Compute."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelVectorizationInput(BaseModel):
    """Input model for vectorization operations.

    This model represents the input for generating embeddings.
    """

    content: str = Field(
        ...,
        description="Text content to vectorize",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (language, source_path, etc.)",
    )
    model_name: str = Field(
        default="text-embedding-3-small",
        description="Embedding model to use",
    )
    batch_mode: bool = Field(
        default=False,
        description="Whether to process in batch mode",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelVectorizationInput"]
