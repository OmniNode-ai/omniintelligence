"""Compliance metadata model for Pattern Compliance Compute Node.

Ticket: OMN-2256
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelComplianceMetadata(BaseModel):
    """Metadata about the compliance evaluation operation.

    Attributes:
        correlation_id: Correlation ID propagated from the request for tracing.
        status: Status of the evaluation (completed, error, validation_error).
        message: Human-readable message about the evaluation result.
        compliance_prompt_version: Version of the prompt template used for LLM evaluation.
        model_used: LLM model identifier used for evaluation.
        processing_time_ms: Time taken to process the evaluation in milliseconds.
        patterns_checked: Number of patterns checked.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID propagated from the request for end-to-end tracing",
    )
    status: str = Field(
        default="completed",
        description="Status of the evaluation operation",
    )
    message: str | None = Field(
        default=None,
        description="Human-readable message about the evaluation result",
    )
    compliance_prompt_version: str = Field(
        ...,
        description="Version of the prompt template used for LLM evaluation",
    )
    model_used: str | None = Field(
        default=None,
        description="LLM model identifier used for evaluation",
    )
    processing_time_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Time taken to process the evaluation in milliseconds",
    )
    patterns_checked: int = Field(
        default=0,
        ge=0,
        description="Number of patterns checked during evaluation",
    )


__all__ = ["ModelComplianceMetadata"]
