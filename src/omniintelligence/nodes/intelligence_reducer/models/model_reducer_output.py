"""Output model for Intelligence Reducer."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
    intents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Intents emitted to orchestrator",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the transition",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Any errors encountered",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelReducerOutput"]
