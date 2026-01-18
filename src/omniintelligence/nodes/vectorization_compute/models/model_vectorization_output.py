"""Output model for Vectorization Compute."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, Field, model_validator


class ModelVectorizationOutput(BaseModel):
    """Output model for vectorization operations.

    This model represents the result of generating embeddings with CONSISTENT
    structure for both single and batch modes.

    Output Structure (consistent for both modes):
        - embeddings: List of embedding vectors, where each vector is list[float]
        - batch_count: Number of items vectorized
        - embedding_dimension: Dimension of each embedding vector

    Single content vectorization (batch_mode=False):
        >>> output = ModelVectorizationOutput(
        ...     success=True,
        ...     embeddings=[[0.1, 0.2, 0.3]],  # One embedding vector
        ...     model_used="text-embedding-3-small",
        ...     batch_count=1,
        ...     embedding_dimension=3,
        ... )
        >>> len(output.embeddings)  # Always 1 for single mode
        1
        >>> output.embeddings[0]  # The embedding vector
        [0.1, 0.2, 0.3]

    Batch vectorization (batch_mode=True):
        >>> output = ModelVectorizationOutput(
        ...     success=True,
        ...     embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],  # Two embeddings
        ...     model_used="text-embedding-3-small",
        ...     batch_count=2,
        ...     embedding_dimension=3,
        ... )
        >>> len(output.embeddings)  # Number of items
        2
        >>> output.embeddings[0]  # First embedding
        [0.1, 0.2, 0.3]
        >>> output.embeddings[1]  # Second embedding
        [0.4, 0.5, 0.6]

    Accessing embeddings (same pattern for both modes):
        >>> for embedding in output.embeddings:
        ...     process_embedding(embedding)

    Failed operations:
        >>> output = ModelVectorizationOutput(
        ...     success=False,
        ...     embeddings=[],  # Empty on failure
        ...     model_used="none",
        ...     batch_count=0,
        ...     embedding_dimension=0,
        ...     metadata={"error": "Content was empty"},
        ... )
    """

    success: bool = Field(
        ...,
        description="Whether vectorization succeeded",
    )
    embeddings: list[list[float]] = Field(
        ...,
        description=(
            "List of embedding vectors. Each vector is a list of floats. "
            "For single mode: contains one vector [[0.1, 0.2, ...]]. "
            "For batch mode: contains N vectors [[0.1, ...], [0.2, ...], ...]. "
            "Empty list [] on failure."
        ),
    )
    model_used: str = Field(
        ...,
        description="Model used for embedding generation ('none' on failure)",
    )
    batch_count: int = Field(
        default=1,
        ge=0,
        description=(
            "Number of items vectorized. "
            "0 if operation failed, 1 for single mode, N for batch mode."
        ),
    )
    embedding_dimension: int = Field(
        default=0,
        ge=0,
        description=(
            "Dimension of each embedding vector. "
            "0 if operation failed or no embeddings generated."
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the embedding",
    )

    @model_validator(mode="after")
    def validate_embeddings_consistency(self) -> Self:
        """Validate consistency between fields.

        Ensures:
        - batch_count matches len(embeddings) for successful operations
        - embedding_dimension matches vector length for successful operations
        - All embedding vectors have consistent dimensions
        - Failed operations can have empty/zero values

        Returns:
            Self with validated parameters.

        Raises:
            ValueError: If field values are inconsistent.
        """
        if self.success:
            # Successful operations must have at least one embedding
            if len(self.embeddings) == 0:
                raise ValueError(
                    "Successful vectorization must have at least one embedding"
                )

            # batch_count must match number of embeddings
            if self.batch_count != len(self.embeddings):
                raise ValueError(
                    f"batch_count ({self.batch_count}) must match "
                    f"number of embeddings ({len(self.embeddings)})"
                )

            # Validate embedding dimensions
            if len(self.embeddings) > 0 and len(self.embeddings[0]) > 0:
                first_dim = len(self.embeddings[0])

                # embedding_dimension must match actual vector dimension
                if self.embedding_dimension != first_dim:
                    raise ValueError(
                        f"embedding_dimension ({self.embedding_dimension}) must match "
                        f"actual vector dimension ({first_dim})"
                    )

                # All embeddings must have same dimension
                for i, emb in enumerate(self.embeddings):
                    if len(emb) != first_dim:
                        raise ValueError(
                            f"Embedding {i} has dimension {len(emb)}, "
                            f"expected {first_dim}"
                        )
        else:
            # Failed operations should have consistent empty state
            if len(self.embeddings) > 0:
                raise ValueError(
                    "Failed vectorization should have empty embeddings list"
                )
            if self.batch_count != 0:
                raise ValueError(
                    "Failed vectorization should have batch_count=0"
                )
            if self.embedding_dimension != 0:
                raise ValueError(
                    "Failed vectorization should have embedding_dimension=0"
                )

        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelVectorizationOutput"]
