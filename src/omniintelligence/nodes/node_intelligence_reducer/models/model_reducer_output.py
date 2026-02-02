"""Output model for Intelligence Reducer.

This module provides type-safe output models for the intelligence reducer node.
All models use strong typing to eliminate dict[str, Any].

ONEX Compliance:
    - Strong typing for all fields
    - Frozen immutable models
    - No dict[str, Any] usage
    - Enum-based FSM type for type safety
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from omniintelligence.enums import EnumFSMType, EnumOrchestratorWorkflowType


class ModelReducerIntentPayload(BaseModel):
    """Typed payload for reducer intents.

    Contains the data needed by the intent target (orchestrator, Kafka, etc.).
    """

    # Workflow trigger fields
    operation_type: EnumOrchestratorWorkflowType | None = Field(
        default=None,
        description="Operation type for workflow triggers",
    )
    entity_id: str | None = Field(
        default=None,
        description="Entity ID for the workflow",
    )
    fsm_type: EnumFSMType | None = Field(
        default=None,
        description="FSM type for context",
    )
    current_state: str | None = Field(
        default=None,
        description="Current FSM state",
    )

    # Event publish fields
    topic: str | None = Field(
        default=None,
        description="Kafka topic for event publish intents",
    )
    event_type: str | None = Field(
        default=None,
        description="Event type identifier",
    )
    event_data: str | None = Field(
        default=None,
        description="Serialized event data",
    )

    # Additional context
    source_action: str | None = Field(
        default=None,
        description="The action that triggered this intent",
    )
    priority: int | None = Field(
        default=None,
        description="Priority level for intent processing",
    )

    model_config = {"frozen": True, "extra": "forbid"}


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

    model_config = {"frozen": True, "extra": "forbid"}


class ModelReducerMetadata(BaseModel):
    """Typed structure for reducer output metadata.

    Contains timing, context, and traceability information about the
    state transition.
    """

    transition_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of the state transition",
    )
    processing_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Processing time in milliseconds",
    )
    lease_id: str | None = Field(
        default=None,
        description="Action lease ID if distributed coordination was used",
    )
    epoch: int | None = Field(
        default=None,
        description="Epoch for action lease management",
    )
    fsm_type: EnumFSMType = Field(
        ...,
        description="FSM type that was processed",
    )
    entity_id: str = Field(
        ...,
        description="Entity ID that was processed",
    )
    action: str = Field(
        ...,
        description="Action that triggered the transition",
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Idempotency key used for deduplication",
    )
    was_duplicate: bool = Field(
        default=False,
        description="Whether this was a duplicate action (skipped)",
    )

    model_config = {"frozen": True, "extra": "forbid"}


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

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelReducerIntent",
    "ModelReducerIntentPayload",
    "ModelReducerMetadata",
    "ModelReducerOutput",
]
