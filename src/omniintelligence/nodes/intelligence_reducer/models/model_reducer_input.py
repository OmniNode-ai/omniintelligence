"""Input model for Intelligence Reducer."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ModelReducerInput(BaseModel):
    """Input model for intelligence reducer operations.

    This model represents the input to the intelligence reducer,
    containing the FSM type, entity identifier, action to execute,
    and any associated payload data.
    """

    fsm_type: str = Field(
        ...,
        description="Type of FSM (INGESTION, PATTERN_LEARNING, QUALITY_ASSESSMENT)",
    )
    entity_id: str = Field(
        ...,
        description="Unique identifier for the entity",
    )
    action: str = Field(
        ...,
        description="FSM action to execute",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific payload data",
    )
    correlation_id: UUID = Field(
        ...,
        description="Correlation ID for tracing",
    )
    lease_id: str | None = Field(
        default=None,
        description="Action lease ID for distributed coordination",
    )
    epoch: int | None = Field(
        default=None,
        description="Epoch for action lease management",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelReducerInput"]
