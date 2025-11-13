"""
ONEX Contract Models for Qdrant Vector Operations

Defines input/output contracts for all Qdrant effect nodes following
ONEX architecture patterns.
"""

from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, root_validator, validator

# =============================================================================
# Index Effect Contracts
# =============================================================================


class QdrantIndexPoint(BaseModel):
    """
    Represents a single data point to be indexed in Qdrant.
    The payload must contain the text to be embedded.
    """

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the point. Auto-generated if not provided.",
    )
    payload: Dict[str, Any] = Field(
        ..., description="Metadata payload. Must include a 'text' key for embedding."
    )

    @validator("payload")
    def text_in_payload(cls, v):
        """Ensures the text for embedding is present and valid."""
        if (
            "text" not in v
            or not isinstance(v.get("text"), str)
            or not v["text"].strip()
        ):
            raise ValueError(
                "'payload' must contain a non-empty string 'text' key for embedding."
            )
        return v


class ModelContractQdrantVectorIndexEffect(BaseModel):
    """Contract for the Qdrant Vector Indexing Effect Node."""

    collection_name: str = Field(
        ..., min_length=1, description="Target Qdrant collection name."
    )
    points: List[QdrantIndexPoint] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="List of points to index. Batch size up to 100.",
    )


class ModelResultQdrantVectorIndexEffect(BaseModel):
    """Result model for the Qdrant Vector Indexing Effect Node."""

    status: str = Field(
        ..., description="Status of the indexing operation (e.g., 'success')."
    )
    indexed_count: int = Field(
        ..., description="Number of points successfully indexed."
    )
    point_ids: List[UUID] = Field(
        ..., description="List of UUIDs for the indexed points."
    )
    collection_name: str = Field(
        ..., description="The collection where points were indexed."
    )
    duration_ms: float = Field(
        ..., description="Total operation duration in milliseconds."
    )


# =============================================================================
# Search Effect Contracts
# =============================================================================


class ModelQdrantHit(BaseModel):
    """Represents a single search result from Qdrant."""

    id: Union[str, int]
    score: float
    payload: Optional[Dict[str, Any]] = None

    @field_validator("payload", mode="before")
    @classmethod
    def validate_payload(cls, v: Any) -> Optional[Dict[str, Any]]:
        """
        Validate optional payload field to prevent None access errors.

        Expected schema (when present):
        - payload: {"text": str, "metadata": dict, "entity_type": str, ...}
        """
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ValueError(f"payload must be a dict or None, got {type(v).__name__}")
        return v


class ModelQdrantSearchResult(BaseModel):
    """Represents the output of a successful Qdrant search effect."""

    hits: List[ModelQdrantHit]
    search_time_ms: float
    total_results: int


class ModelContractQdrantSearchEffect(BaseModel):
    """Contract for the Qdrant search effect node."""

    collection_name: str = Field(
        ..., description="Name of the Qdrant collection to search in."
    )
    query_text: str = Field(..., description="The text to search for.")
    limit: int = Field(
        10, gt=0, le=1000, description="Maximum number of results to return."
    )
    score_threshold: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Similarity score threshold for results."
    )
    filters: Optional[Dict[str, Any]] = Field(
        None, description="Qdrant filter conditions."
    )
    search_params: Optional[Dict[str, Any]] = Field(
        None, description="Optional HNSW search parameters, e.g., {'hnsw_ef': 128}."
    )

    @field_validator("filters", "search_params", mode="before")
    @classmethod
    def validate_optional_dict(cls, v: Any, info) -> Optional[Dict[str, Any]]:
        """
        Validate optional dict fields to prevent None access errors.

        Expected schemas (when present):
        - filters: {"must": list, "should": list, "must_not": list, ...}
        - search_params: {"hnsw_ef": int, "exact": bool, ...}
        """
        if v is None:
            return None
        if not isinstance(v, dict):
            field_name = info.field_name
            raise ValueError(
                f"{field_name} must be a dict or None, got {type(v).__name__}"
            )
        return v


# =============================================================================
# Update Effect Contracts
# =============================================================================


class ModelQdrantUpdateResult(BaseModel):
    """Represents the output of a successful Qdrant update effect."""

    point_id: Union[str, int]
    status: str
    operation_time_ms: float


class ModelContractQdrantUpdateEffect(BaseModel):
    """Contract for the Qdrant update effect node."""

    collection_name: str = Field(
        ..., description="Name of the Qdrant collection to update."
    )
    point_id: Union[str, int] = Field(..., description="The ID of the point to update.")
    payload: Optional[Dict[str, Any]] = Field(
        None, description="The new payload data to set/update for the point."
    )
    text_for_embedding: Optional[str] = Field(
        None,
        description="If provided, a new vector will be generated from this text and updated.",
    )

    @field_validator("payload", mode="before")
    @classmethod
    def validate_payload(cls, v: Any) -> Optional[Dict[str, Any]]:
        """
        Validate optional payload field to prevent None access errors.

        Expected schema (when present):
        - payload: {"text": str, "metadata": dict, "entity_type": str, ...}
        """
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ValueError(f"payload must be a dict or None, got {type(v).__name__}")
        return v

    @root_validator(skip_on_failure=True)
    def check_at_least_one_field_provided(cls, values):
        if values.get("payload") is None and values.get("text_for_embedding") is None:
            raise ValueError(
                "Either 'payload' or 'text_for_embedding' must be provided for an update operation."
            )
        return values


# =============================================================================
# Health Effect Contracts
# =============================================================================


class ModelQdrantCollectionInfo(BaseModel):
    """Detailed statistics for a single Qdrant collection."""

    name: str
    points_count: int
    vectors_count: int
    indexed_vectors_count: int
    configuration: Dict[str, Any]


class ModelQdrantHealthResult(BaseModel):
    """Represents the output of a successful Qdrant health check effect."""

    service_ok: bool
    collections: List[ModelQdrantCollectionInfo]
    response_time_ms: float


class ModelContractQdrantHealthEffect(BaseModel):
    """Contract for the Qdrant health effect node."""

    collection_name: Optional[str] = Field(
        None,
        description="Specific collection to check. If None, checks all collections.",
    )
