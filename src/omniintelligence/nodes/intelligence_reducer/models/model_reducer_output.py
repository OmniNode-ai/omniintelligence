"""Output model for Intelligence Reducer."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class ReducerIntentDict(TypedDict, total=False):
    """Typed structure for intents emitted by the reducer.

    Provides stronger typing for intent fields while allowing
    additional fields via dict[str, Any] union.
    """

    intent_type: str
    target: str
    payload: dict[str, Any]
    correlation_id: str
    timestamp: str
    metadata: dict[str, Any] | None


class ReducerMetadataDict(TypedDict, total=False):
    """Typed structure for reducer output metadata.

    Provides stronger typing for common metadata fields.
    """

    transition_timestamp: str
    processing_time_ms: float
    lease_id: str | None
    epoch: int | None
    fsm_type: str
    entity_id: str
    action: str


class ModelReducerOutput(BaseModel):
    """Output model for intelligence reducer operations.

    This model represents the output from the intelligence reducer,
    containing the state transition result and any emitted intents.
    """

    success: bool = Field(
        ...,
        description="Whether the state transition succeeded",
    )
    previous_state: str | None = Field(
        default=None,
        description="Previous FSM state before transition",
    )
    current_state: str = Field(
        ...,
        description="Current FSM state after transition",
    )
    intents: list[ReducerIntentDict | dict[str, Any]] = Field(
        default_factory=list,
        description="Intents emitted to orchestrator",
    )
    metadata: ReducerMetadataDict | dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the transition",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Any errors encountered",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelReducerOutput",
    "ReducerIntentDict",
    "ReducerMetadataDict",
]
