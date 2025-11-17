"""Input model for QdrantVector Effect Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID, uuid4

class ModelQdrantVectorEffectInput(BaseModel):
    """Input model for qdrant_vector operations."""
    collection: str
operation: str
vector_id: str
embeddings: List[float]
    correlation_id: UUID = Field(default_factory=uuid4, description="Correlation ID")
