"""Output model for RelationshipDetection Compute Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID

class ModelRelationshipDetectionComputeOutput(BaseModel):
    """Output model for relationship_detection operations."""
    success: bool = Field(..., description="Operation success")
    relationships: List[Dict[str, Any]]
relationship_count: int
    correlation_id: UUID = Field(..., description="Correlation ID")
    processing_time_ms: float = Field(..., description="Processing time in ms", ge=0.0)
    
    class Config:
        json_schema_extra = {"example": {"success": True, "processing_time_ms": 45.2}}
