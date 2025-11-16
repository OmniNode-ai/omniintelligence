"""
Output model for Vectorization Compute Node
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any
from uuid import UUID


class ModelVectorizationComputeOutput(BaseModel):
    """Output model for vectorization operations."""

    success: bool = Field(..., description="Whether vectorization succeeded")
    embeddings: List[float] = Field(..., description="Generated embeddings (1536D)")
    model_used: str = Field(..., description="Model used for embedding generation")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the embedding"
    )
    correlation_id: UUID = Field(..., description="Correlation ID from request")
    processing_time_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
        ge=0.0
    )
    cache_hit: bool = Field(
        default=False,
        description="Whether result was served from cache"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "embeddings": [0.1, 0.2, 0.3],  # Truncated for example
                "model_used": "text-embedding-3-small",
                "metadata": {"content_length": 100},
                "processing_time_ms": 45.2,
                "cache_hit": False
            }
        }
