"""Input model for Intelligence Orchestrator Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any
from uuid import UUID, uuid4
from .....shared.enums import EnumOperationType

class ModelIntelligenceOrchestratorInput(BaseModel):
    """Input model for orchestrator operations."""
    operation_type: EnumOperationType = Field(..., description="Operation type")
    entity_id: str = Field(..., description="Entity identifier")
    payload: Dict[str, Any] = Field(..., description="Operation payload")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    correlation_id: str = Field(..., description="Correlation ID for tracing")
