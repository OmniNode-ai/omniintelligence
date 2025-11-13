"""
Qdrant API Response Models

Pydantic models for validating Qdrant API responses (search, upsert, collections).

API Documentation: https://qdrant.tech/documentation/
Performance: Validation overhead <2ms for typical responses
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QdrantUpdateStatus(str, Enum):
    """Status enum for Qdrant update operations."""

    COMPLETED = "completed"
    ACKNOWLEDGED = "acknowledged"


class QdrantDistance(str, Enum):
    """Distance metric enum for Qdrant vectors."""

    COSINE = "Cosine"
    EUCLID = "Euclid"
    DOT = "Dot"
    MANHATTAN = "Manhattan"


class QdrantScoredPoint(BaseModel):
    """
    Individual scored point from Qdrant search results.

    Represents a single document/vector match with score and payload.
    """

    id: Union[str, int] = Field(..., description="Point ID (UUID string or integer)")
    score: float = Field(
        ..., description="Similarity score (higher is better for Cosine/Dot)"
    )
    payload: Optional[Dict[str, Any]] = Field(
        default=None, description="Document metadata and content"
    )
    vector: Optional[List[float]] = Field(
        default=None, description="Original vector (if requested)"
    )
    version: Optional[int] = Field(default=None, description="Point version number")

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: float) -> float:
        """Validate score is a valid number."""
        if not isinstance(v, (int, float)):
            raise ValueError(f"Score must be a number, got {type(v)}")
        return float(v)


class QdrantSearchHit(BaseModel):
    """
    Simplified search hit model for application use.

    Provides a cleaner interface than raw QdrantScoredPoint.
    """

    id: str = Field(..., description="Point ID as string")
    score: float = Field(..., description="Similarity score")
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Document metadata"
    )

    @classmethod
    def from_scored_point(cls, point: QdrantScoredPoint) -> "QdrantSearchHit":
        """Create SearchHit from QdrantScoredPoint."""
        return cls(id=str(point.id), score=point.score, payload=point.payload or {})


class QdrantSearchResponse(BaseModel):
    """
    Response model for Qdrant search operations.

    Validates the list of scored points returned from search.

    Example:
        [
            {
                "id": "uuid-1234",
                "score": 0.92,
                "payload": {"text": "...", "metadata": {...}},
                "vector": null,
                "version": 1
            },
            ...
        ]
    """

    results: List[QdrantScoredPoint] = Field(
        default_factory=list, description="List of scored search results"
    )

    @field_validator("results", mode="before")
    @classmethod
    def validate_results(cls, v: Any) -> List[Dict]:
        """
        Handle both direct list and nested response formats.

        Qdrant can return:
        - Direct list: [{"id": ..., "score": ...}, ...]
        - Nested: {"result": [{"id": ..., "score": ...}, ...]}
        """
        if isinstance(v, list):
            return v
        elif isinstance(v, dict) and "result" in v:
            return v["result"]
        else:
            raise ValueError(f"Invalid search response format: {type(v)}")

    def get_hits(self) -> List[QdrantSearchHit]:
        """Convert results to simplified SearchHit format."""
        return [QdrantSearchHit.from_scored_point(p) for p in self.results]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "results": [
                    {
                        "id": "uuid-1234",
                        "score": 0.92,
                        "payload": {
                            "text": "Sample document content",
                            "source_path": "/path/to/doc.md",
                        },
                    }
                ]
            }
        }
    )


class QdrantUpdateResult(BaseModel):
    """Result information for update operations."""

    operation_id: Optional[int] = Field(
        default=None, description="Operation ID for tracking"
    )
    status: QdrantUpdateStatus = Field(..., description="Operation status")


class QdrantUpsertResponse(BaseModel):
    """
    Response model for Qdrant upsert operations.

    Validates the status and operation info from point upserts.

    Example:
        {
            "result": {
                "operation_id": 123,
                "status": "completed"
            },
            "status": "ok",
            "time": 0.123
        }
    """

    result: Optional[QdrantUpdateResult] = Field(
        default=None, description="Update operation result"
    )
    status: str = Field(..., description="Overall operation status")
    time: Optional[float] = Field(default=None, description="Operation time in seconds")

    @field_validator("result", mode="before")
    @classmethod
    def validate_result(cls, v: Any) -> Optional[Dict]:
        """Handle various result formats from Qdrant."""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        # If result is just a status string, wrap it
        if isinstance(v, str):
            return {"status": v}
        return None

    def is_success(self) -> bool:
        """Check if operation was successful."""
        return (
            self.status == "ok"
            and self.result is not None
            and self.result.status
            in (QdrantUpdateStatus.COMPLETED, QdrantUpdateStatus.ACKNOWLEDGED)
        )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "result": {"operation_id": 123, "status": "completed"},
                "status": "ok",
                "time": 0.123,
            }
        }
    )


class QdrantDeleteResponse(BaseModel):
    """
    Response model for Qdrant delete operations.

    Validates the status and operation info from point deletions.
    """

    result: Optional[QdrantUpdateResult] = Field(
        default=None, description="Delete operation result"
    )
    status: str = Field(..., description="Overall operation status")
    time: Optional[float] = Field(default=None, description="Operation time in seconds")

    def is_success(self) -> bool:
        """Check if operation was successful."""
        return (
            self.status == "ok"
            and self.result is not None
            and self.result.status
            in (QdrantUpdateStatus.COMPLETED, QdrantUpdateStatus.ACKNOWLEDGED)
        )


class QdrantVectorParams(BaseModel):
    """Vector configuration for a collection."""

    size: int = Field(..., description="Vector dimension size")
    distance: QdrantDistance = Field(..., description="Distance metric")
    on_disk: Optional[bool] = Field(default=None, description="Store vectors on disk")


class QdrantCollectionInfo(BaseModel):
    """
    Response model for Qdrant collection info.

    Provides details about a collection's configuration and status.

    Example:
        {
            "result": {
                "status": "green",
                "vectors_count": 1000,
                "indexed_vectors_count": 1000,
                "points_count": 1000,
                "segments_count": 2,
                "config": {
                    "params": {
                        "vectors": {
                            "size": 768,
                            "distance": "Cosine"
                        }
                    }
                }
            },
            "status": "ok",
            "time": 0.001
        }
    """

    result: Dict[str, Any] = Field(..., description="Collection information")
    status: str = Field(..., description="Overall operation status")
    time: Optional[float] = Field(default=None, description="Operation time in seconds")

    def get_vector_count(self) -> int:
        """Get number of vectors in collection."""
        return self.result.get("vectors_count", 0)

    def get_points_count(self) -> int:
        """Get number of points in collection."""
        return self.result.get("points_count", 0)

    def get_collection_status(self) -> str:
        """Get collection status (green, yellow, red)."""
        return self.result.get("status", "unknown")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "result": {
                    "status": "green",
                    "vectors_count": 1000,
                    "points_count": 1000,
                },
                "status": "ok",
                "time": 0.001,
            }
        }
    )
