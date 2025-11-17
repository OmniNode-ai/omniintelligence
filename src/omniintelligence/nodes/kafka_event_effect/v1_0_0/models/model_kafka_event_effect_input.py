"""Input model for KafkaEvent Effect Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID, uuid4

class ModelKafkaEventEffectInput(BaseModel):
    """Input model for kafka_event operations."""
    topic: str
event_type: str
payload: Dict[str, Any]
    correlation_id: UUID = Field(default_factory=uuid4, description="Correlation ID")
