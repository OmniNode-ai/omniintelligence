"""Output model for SemanticAnalysis Compute Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID

class ModelSemanticAnalysisComputeOutput(BaseModel):
    """Output model for semantic_analysis operations."""
    success: bool = Field(..., description="Operation success")
    features: Dict[str, Any]
complexity: Dict[str, float]
    correlation_id: UUID = Field(..., description="Correlation ID")
    processing_time_ms: float = Field(..., description="Processing time in ms", ge=0.0)
    
    class Config:
        json_schema_extra = {"example": {"success": True, "processing_time_ms": 45.2}}
