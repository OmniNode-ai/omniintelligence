"""Output model for Intelligence Reducer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_intent import (
    ModelReducerIntent,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_metadata import (
    ModelReducerMetadata,
)


class ModelReducerOutput(BaseModel):
    """Output model for intelligence reducer operations.

    This model represents the output from the intelligence reducer,
    containing the state transition result and any emitted intents.
    All fields use strong typing without dict[str, Any].
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
    intents: list[ModelReducerIntent] = Field(
        default_factory=list,
        description="Intents emitted to orchestrator",
    )
    metadata: ModelReducerMetadata | None = Field(
        default=None,
        description="Metadata about the transition",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Any errors encountered",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


__all__ = ["ModelReducerOutput"]
