"""Output model for QdrantVector Effect Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID

class ModelQdrantVectorEffectOutput(BaseModel):
    """Output model for qdrant_vector operations."""
    success: bool
results: List[Dict[str, Any]]
    correlation_id: UUID = Field(..., description="Correlation ID")
    processing_time_ms: float = Field(..., description="Processing time in ms", ge=0.0)
