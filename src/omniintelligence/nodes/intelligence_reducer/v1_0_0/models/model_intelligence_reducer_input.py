"""Input model for Intelligence Reducer Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from .....shared.enums import EnumFSMType, EnumFSMAction

class ModelIntelligenceReducerInput(BaseModel):
    """Input model for reducer operations."""
    fsm_type: EnumFSMType = Field(..., description="FSM type")
    entity_id: str = Field(..., description="Entity identifier")
    action: EnumFSMAction = Field(..., description="FSM action")
    payload: Optional[Dict[str, Any]] = Field(None, description="Action payload")
    correlation_id: str = Field(..., description="Correlation ID")
    lease_id: Optional[str] = Field(None, description="Lease ID")
    epoch: Optional[int] = Field(None, description="Lease epoch")
