"""Input model for Intelligence Orchestrator."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ModelOrchestratorInput(BaseModel):
    """Input model for intelligence orchestrator operations.

    This model represents the input to the intelligence orchestrator,
    containing the operation type, entity identifier, payload data,
    and correlation ID for distributed tracing.
    """

    operation_type: str = Field(
        ...,
        description="Type of intelligence operation (e.g., DOCUMENT_INGESTION, PATTERN_LEARNING)",
    )
    entity_id: str = Field(
        ...,
        description="Unique identifier for the entity being processed",
    )
    payload: dict[str, Any] = Field(
        ...,
        description="Operation-specific payload data",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for the operation",
    )
    correlation_id: UUID = Field(
        ...,
        description="Correlation ID for distributed tracing",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelOrchestratorInput"]
