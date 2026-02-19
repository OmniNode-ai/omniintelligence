"""Reducer intent model for Intelligence Reducer."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_intent_payload import (
    ModelReducerIntentPayload,
)


class ModelReducerIntent(BaseModel):
    """Typed structure for intents emitted by the reducer.

    Intents represent side effects that should be executed by the orchestrator
    or other downstream systems. They are emitted during state transitions.
    """

    intent_type: str = Field(
        ...,
        description="Type of intent (e.g., 'workflow.trigger', 'event.publish')",
    )
    target: str = Field(
        ...,
        description="Target URI pattern (e.g., 'orchestrator://intelligence/ingestion')",
    )
    payload: ModelReducerIntentPayload = Field(
        default_factory=ModelReducerIntentPayload,
        description="Intent payload data",
    )
    correlation_id: UUID = Field(
        ...,
        description="Correlation ID for tracing",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when intent was created",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


__all__ = ["ModelReducerIntent"]
