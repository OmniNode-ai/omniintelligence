"""
FSM State Model for omniintelligence.

Models for finite state machine state representation.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence._legacy.enums import EnumFSMType


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
    previous_state: str | None = Field(default=None, description="Previous state")
    transition_timestamp: datetime = Field(..., description="Last transition timestamp")
    metadata: dict[str, Any] | None = Field(default=None, description="State metadata")
    lease_id: str | None = Field(default=None, description="Current lease ID")
    lease_epoch: int | None = Field(default=None, description="Lease epoch")
    lease_expires_at: datetime | None = Field(
        default=None, description="Lease expiration"
    )


__all__ = ["ModelFSMState"]
