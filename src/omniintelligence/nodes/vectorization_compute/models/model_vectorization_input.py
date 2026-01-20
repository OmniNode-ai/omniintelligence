"""Input model for Vectorization Compute."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class VectorizationInputMetadataDict(TypedDict, total=False):
    """Typed structure for vectorization input metadata.

    Provides stronger typing for input metadata fields.
    With total=False, all fields are optional.
    """

    # Source tracking
    source: str
    source_path: str
    document_id: str

    # Content metadata
    language: str
    content_type: str
    content_length: int

    # Chunking metadata
    chunk_index: int
    chunk_total: int


class ModelVectorizationInput(BaseModel):
    """Input model for vectorization operations.

    This model represents the input for generating embeddings.
    """

    content: str = Field(
        ...,
        min_length=1,
        description="Text content to vectorize",
    )
    metadata: VectorizationInputMetadataDict = Field(
        default_factory=lambda: VectorizationInputMetadataDict(),
        description="Additional metadata (language, source_path, etc.). Uses VectorizationInputMetadataDict "
        "with total=False, allowing any subset of typed fields.",
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


__all__ = ["ModelVectorizationInput", "VectorizationInputMetadataDict"]
