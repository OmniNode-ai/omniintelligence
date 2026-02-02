"""Input model for Intelligence Reducer.

This module provides type-safe input models for the intelligence reducer node.
Payload types are discriminated by FSM type to ensure full type safety without
relying on dict[str, Any].

ONEX Compliance:
    - Strong typing for all payload fields
    - Discriminated unions based on fsm_type
    - Frozen immutable models
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_intelligence_reducer.models.model_pattern_lifecycle_reducer_input import (
    ModelPatternLifecycleReducerInput,
)


# =============================================================================
# FSM-Specific Payload Models
# =============================================================================
# Each FSM type has its own typed payload model. This provides full type safety
# and eliminates the need for dict[str, Any].


class ModelIngestionPayload(BaseModel):
    """Payload for INGESTION FSM operations.

    Used for document ingestion workflows: RECEIVED -> PROCESSING -> INDEXED.
    """

    # Document identification
    document_id: str | None = Field(
        default=None,
        description="Unique identifier for the document",
    )
    document_hash: str | None = Field(
        default=None,
        description="Content hash for deduplication",
    )

    # Content fields
    content: str | None = Field(
        default=None,
        min_length=1,
        description="Document content to ingest",
    )
    file_path: str | None = Field(
        default=None,
        min_length=1,
        description="Source file path",
    )
    source_type: str | None = Field(
        default=None,
        description="Source type (e.g., 'file', 'api', 'stream')",
    )

    # Indexing configuration
    indexing_options: dict[str, bool] = Field(
        default_factory=dict,
        description="Indexing options (e.g., {'vectorize': True, 'extract_entities': True})",
    )

    # Error fields (used when action is 'fail')
    failure_reason: str | None = Field(
        default=None,
        description="Reason for failure if action is 'fail'",
    )
    error_code: str | None = Field(
        default=None,
        description="Error code for failure categorization",
    )
    error_details: str | None = Field(
        default=None,
        description="Detailed error information",
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelPatternLearningPayload(BaseModel):
    """Payload for PATTERN_LEARNING FSM operations.

    Used for 4-phase pattern learning: Foundation -> Matching -> Validation -> Traceability.
    """

    # Pattern identification
    pattern_id: str | None = Field(
        default=None,
        description="Unique identifier for the pattern",
    )
    pattern_name: str | None = Field(
        default=None,
        description="Human-readable pattern name",
    )

    # Learning configuration
    confidence_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for pattern matching",
    )

    # Pattern metadata
    pattern_metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Additional pattern metadata",
    )

    # Source content for learning
    content: str | None = Field(
        default=None,
        min_length=1,
        description="Source content for pattern learning",
    )
    file_path: str | None = Field(
        default=None,
        min_length=1,
        description="Source file path",
    )

    # Error fields (used when action is 'fail')
    failure_reason: str | None = Field(
        default=None,
        description="Reason for failure if action is 'fail'",
    )
    error_code: str | None = Field(
        default=None,
        description="Error code for failure categorization",
    )
    error_details: str | None = Field(
        default=None,
        description="Detailed error information",
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelQualityAssessmentPayload(BaseModel):
    """Payload for QUALITY_ASSESSMENT FSM operations.

    Used for quality assessment: RAW -> ASSESSING -> SCORED -> STORED.
    """

    # Assessment input
    content: str | None = Field(
        default=None,
        min_length=1,
        description="Content to assess",
    )
    file_path: str | None = Field(
        default=None,
        min_length=1,
        description="Source file path",
    )
    source_type: str | None = Field(
        default=None,
        description="Source type for assessment context",
    )

    # Assessment results (populated during SCORED state)
    quality_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Quality score (0.0 to 1.0)",
    )
    compliance_status: str | None = Field(
        default=None,
        description="ONEX compliance status",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Quality improvement recommendations",
    )

    # Assessment metadata
    assessment_metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Additional assessment metadata",
    )

    # Error fields (used when action is 'fail')
    failure_reason: str | None = Field(
        default=None,
        description="Reason for failure if action is 'fail'",
    )
    error_code: str | None = Field(
        default=None,
        description="Error code for failure categorization",
    )
    error_details: str | None = Field(
        default=None,
        description="Detailed error information",
    )

    model_config = {"frozen": True, "extra": "forbid"}


# =============================================================================
# Union Type for All Payloads
# =============================================================================

# Type alias for all valid payload types
ReducerPayload = (
    ModelIngestionPayload | ModelPatternLearningPayload | ModelQualityAssessmentPayload
)


# =============================================================================
# Discriminated Input Models
# =============================================================================
# These models use Literal types for fsm_type to enable discriminated unions,
# providing runtime validation that payload matches fsm_type.


class ModelReducerInputIngestion(BaseModel):
    """Input model for INGESTION FSM operations."""

    fsm_type: Literal["INGESTION"] = Field(
        ...,
        description="FSM type - must be INGESTION",
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
    payload: ModelIngestionPayload = Field(
        default_factory=ModelIngestionPayload,
        description="Ingestion-specific payload",
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


class ModelReducerInputPatternLearning(BaseModel):
    """Input model for PATTERN_LEARNING FSM operations."""

    fsm_type: Literal["PATTERN_LEARNING"] = Field(
        ...,
        description="FSM type - must be PATTERN_LEARNING",
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
    payload: ModelPatternLearningPayload = Field(
        default_factory=ModelPatternLearningPayload,
        description="Pattern learning-specific payload",
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


class ModelReducerInputQualityAssessment(BaseModel):
    """Input model for QUALITY_ASSESSMENT FSM operations."""

    fsm_type: Literal["QUALITY_ASSESSMENT"] = Field(
        ...,
        description="FSM type - must be QUALITY_ASSESSMENT",
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
    payload: ModelQualityAssessmentPayload = Field(
        default_factory=ModelQualityAssessmentPayload,
        description="Quality assessment-specific payload",
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


class ModelReducerInputPatternLifecycle(BaseModel):
    """Input model for PATTERN_LIFECYCLE FSM operations.

    Used for pattern lifecycle transitions: CANDIDATE -> PROVISIONAL -> VALIDATED -> DEPRECATED.

    Ticket: OMN-1805
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fsm_type: Literal["PATTERN_LIFECYCLE"] = Field(
        ...,
        description="FSM type - must be PATTERN_LIFECYCLE",
    )
    entity_id: str = Field(
        ...,
        min_length=1,
        description="Pattern ID as entity identifier",
    )
    action: str = Field(
        ...,
        min_length=1,
        description="Trigger name (FSM transition trigger)",
    )
    payload: ModelPatternLifecycleReducerInput = Field(
        ...,
        description="Pattern lifecycle-specific payload",
    )
    correlation_id: UUID = Field(
        ...,
        description="Correlation ID for tracing",
    )
    request_id: UUID = Field(
        ...,
        description="Idempotency key - flows end-to-end through the system",
    )
    lease_id: str | None = Field(
        default=None,
        description="Action lease ID for distributed coordination",
    )
    epoch: int | None = Field(
        default=None,
        description="Epoch for action lease management",
    )


# Discriminated union for all input types
# Pydantic will automatically select the correct model based on fsm_type value
ModelReducerInput = Annotated[
    ModelReducerInputIngestion
    | ModelReducerInputPatternLearning
    | ModelReducerInputQualityAssessment
    | ModelReducerInputPatternLifecycle,
    Field(discriminator="fsm_type"),
]


__all__ = [
    "ModelIngestionPayload",
    "ModelPatternLearningPayload",
    "ModelPatternLifecycleReducerInput",
    "ModelQualityAssessmentPayload",
    "ModelReducerInput",
    "ModelReducerInputIngestion",
    "ModelReducerInputPatternLearning",
    "ModelReducerInputPatternLifecycle",
    "ModelReducerInputQualityAssessment",
    "ReducerPayload",
]
