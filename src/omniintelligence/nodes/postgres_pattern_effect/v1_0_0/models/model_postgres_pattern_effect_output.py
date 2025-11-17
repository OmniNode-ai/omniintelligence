"""Output model for PostgresPattern Effect Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID

class ModelPostgresPatternEffectOutput(BaseModel):
    """Output model for postgres_pattern operations."""
    success: bool
pattern_id: str
    correlation_id: UUID = Field(..., description="Correlation ID")
    processing_time_ms: float = Field(..., description="Processing time in ms", ge=0.0)
