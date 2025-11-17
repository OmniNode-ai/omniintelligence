"""Output model for Intelligence Orchestrator Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from .....shared.models import ModelIntent

class ModelIntelligenceOrchestratorOutput(BaseModel):
    """Output model for orchestrator operations."""
    success: bool = Field(..., description="Operation success")
    workflow_id: str = Field(..., description="Workflow identifier")
    results: Dict[str, Any] = Field(default_factory=dict, description="Workflow results")
    intents: List[ModelIntent] = Field(default_factory=list, description="Emitted intents")
    errors: List[str] = Field(default_factory=list, description="Error messages")
