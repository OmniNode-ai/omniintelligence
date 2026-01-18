"""Output model for Intelligence Orchestrator."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


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
    results: dict[str, Any] = Field(
        default_factory=dict,
        description="Results from the workflow execution",
    )
    intents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Intents emitted during workflow execution",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Any errors encountered during execution",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelOrchestratorOutput"]
