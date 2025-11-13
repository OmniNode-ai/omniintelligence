"""
ONEX Contract Models for Pattern Learning Vector Index Operations

Defines input/output contracts for Qdrant vector indexing operations
following ONEX architecture patterns for Phase 1 Foundation.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# Vector Index Point Models
# =============================================================================


# NOTE: correlation_id support enabled for tracing
class ModelVectorIndexPoint(BaseModel):
    """
    Represents a single execution pattern point to be indexed in Qdrant.
    The payload must contain the text representation for embedding generation.
    """

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the pattern. Auto-generated if not provided.",
    )
    payload: Dict[str, Any] = Field(
        ...,
        description="Pattern metadata payload. Must include 'text' key for embedding.",
    )

    @field_validator("payload")
    @classmethod
    def validate_text_field(cls, v):
        """Ensures the text field for embedding is present and non-empty."""
        if (
            "text" not in v
            or not isinstance(v.get("text"), str)
            or not v["text"].strip()
        ):
            raise ValueError(
                "payload must contain a non-empty string 'text' key for embedding generation"
            )
        return v


# =============================================================================
# Index Operation Contracts
# =============================================================================


class ModelContractVectorIndexEffect(BaseModel):
    """Contract for the Vector Indexing Effect Node."""

    collection_name: str = Field(
        default="code_generation_patterns",
        min_length=1,
        description="Target Qdrant collection name for pattern storage.",
    )
    points: List[ModelVectorIndexPoint] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of pattern points to index. Batch size up to 100 for optimal performance.",
    )


class ModelResultVectorIndexEffect(BaseModel):
    """Result model for the Vector Indexing Effect Node."""

    status: str = Field(
        ..., description="Status of the indexing operation (success/failure)."
    )
    indexed_count: int = Field(
        ..., ge=0, description="Number of patterns successfully indexed."
    )
    point_ids: List[UUID] = Field(
        ..., description="List of UUIDs for the indexed pattern points."
    )
    collection_name: str = Field(
        ..., description="The collection where patterns were indexed."
    )
    duration_ms: float = Field(
        ..., ge=0, description="Total operation duration in milliseconds."
    )


# =============================================================================
# Search Operation Contracts
# =============================================================================


class ModelContractVectorSearchEffect(BaseModel):
    """Contract for the Vector Search Effect Node."""

    collection_name: str = Field(
        default="code_generation_patterns",
        min_length=1,
        description="Target Qdrant collection name for search.",
    )
    query_text: str = Field(
        ..., min_length=1, description="Query text to search for similar patterns."
    )
    limit: int = Field(
        default=10, ge=1, le=100, description="Maximum number of results to return."
    )
    score_threshold: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold (0.0-1.0).",
    )


class ModelVectorSearchHit(BaseModel):
    """Represents a single search result from vector similarity search."""

    id: str = Field(..., description="Pattern point ID")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    payload: Optional[Dict[str, Any]] = Field(
        default=None, description="Pattern metadata payload"
    )


class ModelResultVectorSearchEffect(BaseModel):
    """Result model for the Vector Search Effect Node."""

    hits: List[ModelVectorSearchHit] = Field(
        ..., description="List of similar patterns found."
    )
    search_time_ms: float = Field(
        ..., ge=0, description="Search operation duration in milliseconds."
    )
    total_results: int = Field(
        ..., ge=0, description="Total number of results returned."
    )
    collection_name: str = Field(..., description="Collection that was searched.")


# =============================================================================
# Delete Operation Contracts
# =============================================================================


class ModelContractVectorDeleteEffect(BaseModel):
    """Contract for the Vector Delete Effect Node."""

    collection_name: str = Field(
        default="code_generation_patterns",
        min_length=1,
        description="Target Qdrant collection name.",
    )
    point_ids: List[UUID] = Field(
        ..., min_length=1, description="List of pattern point IDs to delete."
    )


class ModelResultVectorDeleteEffect(BaseModel):
    """Result model for the Vector Delete Effect Node."""

    status: str = Field(..., description="Status of the delete operation.")
    deleted_count: int = Field(
        ..., ge=0, description="Number of patterns successfully deleted."
    )
    collection_name: str = Field(
        ..., description="Collection where patterns were deleted from."
    )
    duration_ms: float = Field(
        ..., ge=0, description="Total operation duration in milliseconds."
    )


# =============================================================================
# Batch Operation Contracts
# =============================================================================


class ModelContractBatchIndexEffect(BaseModel):
    """Contract for batch indexing multiple pattern sets."""

    collection_name: str = Field(
        default="code_generation_patterns",
        min_length=1,
        description="Target Qdrant collection name.",
    )
    batch_points: List[List[ModelVectorIndexPoint]] = Field(
        ...,
        min_length=1,
        description="List of batches, each containing up to 100 points.",
    )

    @field_validator("batch_points")
    @classmethod
    def validate_batch_sizes(cls, v):
        """Ensures each batch doesn't exceed 100 points."""
        for i, batch in enumerate(v):
            if len(batch) > 100:
                raise ValueError(
                    f"Batch {i} contains {len(batch)} points. Maximum is 100 per batch."
                )
        return v


class ModelResultBatchIndexEffect(BaseModel):
    """Result model for batch indexing operation."""

    status: str = Field(..., description="Overall status of the batch operation.")
    total_indexed: int = Field(
        ..., ge=0, description="Total number of patterns indexed across all batches."
    )
    batches_processed: int = Field(
        ..., ge=0, description="Number of batches successfully processed."
    )
    failed_batches: int = Field(
        default=0, ge=0, description="Number of batches that failed."
    )
    total_duration_ms: float = Field(
        ..., ge=0, description="Total duration for all batch operations."
    )
    collection_name: str = Field(
        ..., description="Collection where patterns were indexed."
    )
