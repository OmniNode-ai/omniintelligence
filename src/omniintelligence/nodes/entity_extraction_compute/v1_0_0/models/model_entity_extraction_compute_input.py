"""Input model for EntityExtraction Compute Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID, uuid4

class ModelEntityExtractionComputeInput(BaseModel):
    """Input model for entity_extraction operations."""
    code: str
file_path: str
language: str
    correlation_id: UUID = Field(default_factory=uuid4, description="Correlation ID")
    
    class Config:
        json_schema_extra = {"example": {"correlation_id": "550e8400-e29b-41d4-a716-446655440000"}}
