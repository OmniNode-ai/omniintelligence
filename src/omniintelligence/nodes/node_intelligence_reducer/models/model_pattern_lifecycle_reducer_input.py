"""Pattern Lifecycle Reducer Input Model.

Payload model for PATTERN_LIFECYCLE FSM operations in the intelligence reducer.
This model is used as part of the discriminated union ModelReducerInput.

Naming note: "ReducerInput" not "Payload" to distinguish from intent payloads.

Ticket: OMN-1805
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.models.domain import ModelGateSnapshot


class ModelPatternLifecycleReducerInput(BaseModel):
    """Reducer input payload for pattern lifecycle FSM.

    This model carries the transition request data that the reducer
    validates against contract.yaml before emitting an intent.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str = Field(..., description="Pattern UUID as string")
    from_status: EnumPatternLifecycleStatus = Field(
        ..., description="Current status (for validation)"
    )
    to_status: EnumPatternLifecycleStatus = Field(..., description="Target status")
    trigger: str = Field(
        ...,
        description="Trigger name: promote, promote_direct, deprecate, manual_reenable",
    )
    actor_type: Literal["system", "admin", "handler"] = Field(
        default="handler",
        description="Actor type for guard condition evaluation (e.g., admin required for manual_reenable)",
    )
    gate_snapshot: ModelGateSnapshot | None = Field(
        default=None,
        description="Gate values at decision time",
    )
    reason: str | None = Field(default=None, description="Human-readable reason")
    actor: str = Field(default="reducer", description="Who initiated")


__all__ = ["ModelPatternLifecycleReducerInput"]
