"""Output model for IntelligenceApi Effect Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID

class ModelIntelligenceApiEffectOutput(BaseModel):
    """Output model for intelligence_api operations."""
    success: bool
response: Dict[str, Any]
status_code: int
    correlation_id: UUID = Field(..., description="Correlation ID")
    processing_time_ms: float = Field(..., description="Processing time in ms", ge=0.0)
