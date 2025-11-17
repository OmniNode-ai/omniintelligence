"""Input model for IntelligenceApi Effect Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID, uuid4

class ModelIntelligenceApiEffectInput(BaseModel):
    """Input model for intelligence_api operations."""
    endpoint: str
method: str
payload: Dict[str, Any]
    correlation_id: UUID = Field(default_factory=uuid4, description="Correlation ID")
