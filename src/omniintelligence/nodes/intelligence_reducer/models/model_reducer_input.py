"""Input model for Intelligence Reducer."""

from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field

from omniintelligence.enums import EnumFSMType


class ReducerPayloadDict(TypedDict, total=False):
    """Typed structure for reducer action payload.

    Provides stronger typing for common payload fields while allowing
    additional fields via dict[str, Any] union. Fields are optional
    (total=False) since payloads vary by action type.
    """

    # Common fields across FSM types
    document_id: str
    content: str
    file_path: str
    source_type: str

    # Ingestion-specific fields
    document_hash: str
    indexing_options: dict[str, bool]

    # Pattern learning-specific fields
    pattern_id: str
    pattern_name: str
    confidence_threshold: float
    pattern_metadata: dict[str, str]

    # Quality assessment-specific fields
    quality_score: float
    compliance_status: str
    recommendations: list[str]
    assessment_metadata: dict[str, str]

    # Error/failure fields
    failure_reason: str
    error_code: str
    error_details: str


class ModelReducerInput(BaseModel):
    """Input model for intelligence reducer operations.

    This model represents the input to the intelligence reducer,
    containing the FSM type, entity identifier, action to execute,
    and any associated payload data.
    """

    fsm_type: EnumFSMType = Field(
        ...,
        description="Type of FSM (INGESTION, PATTERN_LEARNING, QUALITY_ASSESSMENT)",
    )
    entity_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the entity",
    )
    action: str = Field(
        ...,
        min_length=1,
        description="FSM action to execute",
    )
    payload: ReducerPayloadDict | dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific payload data with typed common fields",
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


__all__ = ["ModelReducerInput", "ReducerPayloadDict"]
