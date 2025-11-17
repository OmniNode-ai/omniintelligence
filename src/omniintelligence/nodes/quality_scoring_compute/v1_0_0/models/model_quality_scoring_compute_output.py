"""Output model for QualityScoring Compute Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID

class ModelQualityScoringComputeOutput(BaseModel):
    """Output model for quality_scoring operations."""
    success: bool = Field(..., description="Operation success")
    overall_score: float
scores: Dict[str, float]
    correlation_id: UUID = Field(..., description="Correlation ID")
    processing_time_ms: float = Field(..., description="Processing time in ms", ge=0.0)
    
    class Config:
        json_schema_extra = {"example": {"success": True, "processing_time_ms": 45.2}}
