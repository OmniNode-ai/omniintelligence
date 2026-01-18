"""Output model for Vectorization Compute."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelVectorizationOutput(BaseModel):
    """Output model for vectorization operations.

    This model represents the result of generating embeddings.

    For single content vectorization (batch_mode=False):
        - embeddings: A single embedding vector [0.1, 0.2, ...]
        - batch_count: 1
        - embedding_dimension: Length of the embedding

    For batch vectorization (batch_mode=True):
        - embeddings: Flattened list of all embeddings concatenated
        - batch_count: Number of items processed
        - embedding_dimension: Dimension of each embedding (for parsing)

    To parse batch results:
        embeddings_per_item = len(embeddings) // batch_count
        item_embeddings = [
            embeddings[i*embedding_dimension:(i+1)*embedding_dimension]
            for i in range(batch_count)
        ]
    """

    success: bool = Field(
        ...,
        description="Whether vectorization succeeded",
    )
    embeddings: list[float] = Field(
        ...,
        description="Generated embeddings (flattened for batch mode)",
    )
    model_used: str = Field(
        ...,
        description="Model used for embedding generation",
    )
    batch_count: int = Field(
        default=1,
        ge=1,
        description="Number of items vectorized (1 for single mode, N for batch mode)",
    )
    embedding_dimension: int = Field(
        default=0,
        ge=0,
        description="Dimension of each embedding vector (for parsing batch results)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the embedding",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelVectorizationOutput"]
