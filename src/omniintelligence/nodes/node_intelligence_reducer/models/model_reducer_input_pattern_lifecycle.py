"""Input model for Intelligence Reducer - PATTERN_LIFECYCLE FSM."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_intelligence_reducer.models.model_pattern_lifecycle_reducer_input import (
    ModelPatternLifecycleReducerInput,
)


class ModelReducerInputPatternLifecycle(BaseModel):
    """Input model for PATTERN_LIFECYCLE FSM operations.

    Used for pattern lifecycle transitions: CANDIDATE -> PROVISIONAL -> VALIDATED -> DEPRECATED.

    Ticket: OMN-1805
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fsm_type: Literal["PATTERN_LIFECYCLE"] = Field(
        ...,
        description="FSM type - must be PATTERN_LIFECYCLE",
    )
    entity_id: str = Field(
        ...,
        min_length=1,
        description="Pattern ID as entity identifier",
    )
    action: str = Field(
        ...,
        min_length=1,
        description="Trigger name (FSM transition trigger)",
    )
    payload: ModelPatternLifecycleReducerInput = Field(
        ...,
        description="Pattern lifecycle-specific payload",
    )
    correlation_id: UUID = Field(
        ...,
        description="Correlation ID for tracing",
    )
    request_id: UUID = Field(
        ...,
        description="Idempotency key - flows end-to-end through the system",
    )
    lease_id: str | None = Field(
        default=None,
        description="Action lease ID for distributed coordination",
    )
    epoch: int | None = Field(
        default=None,
        description="Epoch for action lease management",
    )
