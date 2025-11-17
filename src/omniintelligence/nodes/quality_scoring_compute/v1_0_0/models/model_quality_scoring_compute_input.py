"""Input model for QualityScoring Compute Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID, uuid4

class ModelQualityScoringComputeInput(BaseModel):
    """Input model for quality_scoring operations."""
    code: str
file_path: str
metrics: Dict[str, Any]
    correlation_id: UUID = Field(default_factory=uuid4, description="Correlation ID")
    
    class Config:
        json_schema_extra = {"example": {"correlation_id": "550e8400-e29b-41d4-a716-446655440000"}}
