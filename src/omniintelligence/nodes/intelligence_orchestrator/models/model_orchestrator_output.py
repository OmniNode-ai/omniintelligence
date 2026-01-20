"""Output model for Intelligence Orchestrator."""

from __future__ import annotations

from typing import TypedDict
from uuid import UUID

from pydantic import BaseModel, Field


class IntentPayloadDict(TypedDict, total=False):
    """Typed structure for intent payload data.

    Provides type-safe payload fields for orchestrator intents.
    """

    operation_type: str
    entity_id: str
    content: str
    file_path: str
    parameters: dict[str, str | int | float | bool | None]


class IntentMetadataDict(TypedDict, total=False):
    """Typed structure for intent metadata.

    Provides type-safe metadata fields for orchestrator intents.
    """

    source: str
    priority: int
    retry_count: int
    max_retries: int
    timeout_ms: int


class OrchestratorIntentDict(TypedDict, total=False):
    """Typed structure for intents emitted by the orchestrator.

    All fields are strongly typed without using Any.
    """

    intent_type: str
    target: str
    payload: IntentPayloadDict
    correlation_id: str  # Expected format: UUID (e.g., "550e8400-e29b-41d4-a716-446655440000")
    timestamp: str
    metadata: IntentMetadataDict | None


class OutputDataDict(TypedDict, total=False):
    """Typed structure for workflow output data.

    Provides type-safe output data fields for orchestrator results.
    """

    document_id: str
    vector_ids: list[str]
    entity_ids: list[str]
    quality_score: float
    pattern_ids: list[str]
    success_count: int
    failure_count: int


class OrchestratorResultsDict(TypedDict, total=False):
    """Typed structure for orchestrator workflow results.

    All fields are strongly typed without using Any.
    """

    workflow_type: str
    entity_id: str
    processing_time_ms: float
    steps_completed: int
    steps_total: int
    output_data: OutputDataDict


class ModelOrchestratorOutput(BaseModel):
    """Output model for intelligence orchestrator operations.

    This model represents the output from the intelligence orchestrator,
    containing the workflow execution status, results, any emitted intents,
    and error information if applicable.

    All fields use strong typing without dict[str, Any].
    """

    success: bool = Field(
        ...,
        description="Whether the orchestration completed successfully",
    )
    workflow_id: UUID = Field(
        ...,
        description="Unique identifier for this workflow execution",
    )
    results: OrchestratorResultsDict = Field(
        default_factory=lambda: OrchestratorResultsDict(),
        description="Results from the workflow execution",
    )
    intents: list[OrchestratorIntentDict] = Field(
        default_factory=list,
        description="Intents emitted during workflow execution",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Any errors encountered during execution",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "IntentMetadataDict",
    "IntentPayloadDict",
    "ModelOrchestratorOutput",
    "OrchestratorIntentDict",
    "OrchestratorResultsDict",
    "OutputDataDict",
]
