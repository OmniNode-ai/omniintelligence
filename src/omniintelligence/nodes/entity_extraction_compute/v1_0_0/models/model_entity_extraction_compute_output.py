"""Output model for EntityExtraction Compute Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID

class ModelEntityExtractionComputeOutput(BaseModel):
    """Output model for entity_extraction operations."""
    success: bool = Field(..., description="Operation success")
    entities: List[Dict[str, Any]]
entity_count: int
    correlation_id: UUID = Field(..., description="Correlation ID")
    processing_time_ms: float = Field(..., description="Processing time in ms", ge=0.0)
    
    class Config:
        json_schema_extra = {"example": {"success": True, "processing_time_ms": 45.2}}
