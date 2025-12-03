"""
Reducer Models for omniintelligence.

Input, output, and configuration models for intelligence reducers.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumFSMAction, EnumFSMType

from .model_intent import ModelIntent


class ModelReducerInput(BaseModel):
    """Input model for intelligence reducer."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fsm_type": "INGESTION",
                "entity_id": "doc_123",
                "action": "START_PROCESSING",
                "correlation_id": "corr_456",
            }
        }
    )

    fsm_type: EnumFSMType = Field(..., description="Type of FSM")
    entity_id: str = Field(..., description="Entity identifier")
    action: EnumFSMAction = Field(..., description="FSM action to execute")
    payload: Optional[dict[str, Any]] = Field(None, description="Action payload")
    correlation_id: str = Field(..., description="Correlation ID")
    lease_id: Optional[str] = Field(None, description="Action lease ID")
    epoch: Optional[int] = Field(None, description="Lease epoch")


class ModelReducerOutput(BaseModel):
    """Output model for intelligence reducer."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "previous_state": "RECEIVED",
                "current_state": "PROCESSING",
                "intents": [],
            }
        }
    )

    success: bool = Field(..., description="Whether transition succeeded")
    previous_state: Optional[str] = Field(default=None, description="Previous FSM state")
    current_state: str = Field(..., description="Current FSM state")
    intents: list[ModelIntent] = Field(
        default_factory=list, description="Emitted intents"
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None, description="Transition metadata"
    )
    errors: list[str] = Field(default_factory=list, description="Error messages")


class ModelReducerConfig(BaseModel):
    """Configuration for intelligence reducer."""

    database_url: str = Field(..., description="PostgreSQL connection URL")
    enable_lease_management: bool = Field(True, description="Enable action leases")
    lease_timeout_seconds: int = Field(300, description="Lease timeout")
    max_retry_attempts: int = Field(3, description="Max retry attempts")


__all__ = [
    "ModelReducerConfig",
    "ModelReducerInput",
    "ModelReducerOutput",
]
