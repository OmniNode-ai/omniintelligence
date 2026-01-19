"""Input model for Qdrant Vector Effect."""

from __future__ import annotations

from typing import Literal, Self, TypedDict

from pydantic import BaseModel, Field, model_validator


class VectorPayloadInputDict(TypedDict, total=False):
    """Typed structure for vector payload data.

    Provides type-safe fields for vector payloads to upsert.
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


class VectorFilterDict(TypedDict, total=False):
    """Typed structure for vector search/delete filters.

    Provides type-safe fields for Qdrant filter conditions.
    """

    # Field filters (equality)
    document_id: str
    entity_type: str
    category: str
    language: str
    source_type: str

    # Range filters
    min_quality_score: float
    max_quality_score: float
    min_confidence: float

    # Date filters
    created_after: str
    created_before: str
    updated_after: str
    updated_before: str

    # List filters
    tags_any: list[str]
    tags_all: list[str]


class ModelQdrantVectorInput(BaseModel):
    """Input model for Qdrant vector operations.

    This model represents the input for vector storage operations.

    Operation-specific requirements:
        - upsert_vectors: requires vectors and ids (must be same length)
        - search_vectors: requires query_vector
        - delete_vectors: requires either ids or filters

    All fields use strong typing without dict[str, Any].
    """

    operation: Literal["upsert_vectors", "search_vectors", "delete_vectors"] = Field(
        default="upsert_vectors",
        description="Type of vector operation",
    )
    collection_name: str = Field(
        default="default",
        min_length=1,
        description="Name of the Qdrant collection",
    )
    vectors: list[list[float]] = Field(
        default_factory=list,
        description="Vectors to upsert",
    )
    payloads: list[VectorPayloadInputDict] = Field(
        default_factory=list,
        description="Payloads associated with vectors with typed fields",
    )
    ids: list[str] = Field(
        default_factory=list,
        description="IDs for the vectors",
    )
    query_vector: list[float] | None = Field(
        default=None,
        description="Query vector for search operations",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=10000,
        description="Number of results to return for search",
    )
    filters: VectorFilterDict = Field(
        default_factory=lambda: VectorFilterDict(),
        description="Filters for search or delete operations with typed fields",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )

    @model_validator(mode="after")
    def validate_operation_requirements(self) -> Self:
        """Validate that required fields are provided for each operation type."""
        if self.operation == "upsert_vectors":
            if not self.vectors:
                raise ValueError("upsert_vectors operation requires vectors")
            if not self.ids:
                raise ValueError("upsert_vectors operation requires ids")
            if len(self.vectors) != len(self.ids):
                raise ValueError(
                    f"vectors ({len(self.vectors)}) and ids ({len(self.ids)}) "
                    "must have the same length"
                )
            if self.payloads and len(self.payloads) != len(self.vectors):
                raise ValueError(
                    f"payloads ({len(self.payloads)}) must match vectors ({len(self.vectors)}) "
                    "length if provided"
                )
        elif self.operation == "search_vectors":
            if self.query_vector is None:
                raise ValueError("search_vectors operation requires query_vector")
        elif self.operation == "delete_vectors":
            if not self.ids and not self.filters:
                raise ValueError(
                    "delete_vectors operation requires either ids or filters"
                )
        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelQdrantVectorInput",
    "VectorFilterDict",
    "VectorPayloadInputDict",
]
