"""Output model for Intelligence Orchestrator."""

from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field


class OrchestratorIntentDict(TypedDict, total=False):
    """Typed structure for intents emitted by the orchestrator.

    Provides stronger typing for intent fields while allowing
    additional fields via dict[str, Any] union.
    """

    intent_type: str
    target: str
    payload: dict[str, Any]
    correlation_id: str  # Expected format: UUID (e.g., "550e8400-e29b-41d4-a716-446655440000")
    timestamp: str
    metadata: dict[str, Any] | None


class OrchestratorResultsDict(TypedDict, total=False):
    """Typed structure for orchestrator workflow results.

    Provides stronger typing for common result fields.
    """

    workflow_type: str
    entity_id: str
    processing_time_ms: float
    steps_completed: int
    steps_total: int
    output_data: dict[str, Any]


class ModelOrchestratorOutput(BaseModel):
    """Output model for intelligence orchestrator operations.

    This model represents the output from the intelligence orchestrator,
    containing the workflow execution status, results, any emitted intents,
    and error information if applicable.
    """

    success: bool = Field(
        ...,
        description="Whether the orchestration completed successfully",
    )
    workflow_id: UUID = Field(
        ...,
        description="Unique identifier for this workflow execution",
    )
    results: OrchestratorResultsDict | dict[str, Any] = Field(
        default_factory=dict,
        description="Results from the workflow execution",
    )
    intents: list[OrchestratorIntentDict | dict[str, Any]] = Field(
        default_factory=list,
        description="Intents emitted during workflow execution",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Any errors encountered during execution",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelOrchestratorOutput",
    "OrchestratorIntentDict",
    "OrchestratorResultsDict",
]
