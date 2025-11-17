"""Output model for KafkaEvent Effect Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID

class ModelKafkaEventEffectOutput(BaseModel):
    """Output model for kafka_event operations."""
    published: bool
event_id: str
    correlation_id: UUID = Field(..., description="Correlation ID")
    processing_time_ms: float = Field(..., description="Processing time in ms", ge=0.0)
