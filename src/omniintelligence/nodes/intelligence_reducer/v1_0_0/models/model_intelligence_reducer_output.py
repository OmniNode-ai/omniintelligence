"""Output model for Intelligence Reducer Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from .....shared.models import ModelIntent

class ModelIntelligenceReducerOutput(BaseModel):
    """Output model for reducer operations."""
    success: bool = Field(..., description="Operation success")
    previous_state: Optional[str] = Field(None, description="Previous FSM state")
    current_state: str = Field(..., description="Current FSM state")
    intents: List[ModelIntent] = Field(default_factory=list, description="Emitted intents")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Transition metadata")
    errors: List[str] = Field(default_factory=list, description="Error messages")
