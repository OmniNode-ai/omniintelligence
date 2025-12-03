"""
FSM State Model for omniintelligence.

Models for finite state machine state representation.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumFSMType


class ModelFSMState(BaseModel):
    """FSM state representation."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fsm_type": "INGESTION",
                "entity_id": "doc_123",
                "current_state": "PROCESSING",
                "previous_state": "RECEIVED",
                "transition_timestamp": "2025-11-14T12:00:00Z",
            }
        }
    )

    fsm_type: EnumFSMType = Field(..., description="FSM type")
    entity_id: str = Field(..., description="Entity identifier")
    current_state: str = Field(..., description="Current state")
    previous_state: Optional[str] = Field(default=None, description="Previous state")
    transition_timestamp: datetime = Field(..., description="Last transition timestamp")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="State metadata")
    lease_id: Optional[str] = Field(default=None, description="Current lease ID")
    lease_epoch: Optional[int] = Field(default=None, description="Lease epoch")
    lease_expires_at: Optional[datetime] = Field(
        default=None, description="Lease expiration"
    )


__all__ = ["ModelFSMState"]
