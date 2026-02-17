"""Output model for Pattern Compliance Compute Node.

Defines the result structure for pattern compliance evaluation,
including the list of violations found and overall compliance status.

Ticket: OMN-2256
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelComplianceViolation(BaseModel):
    """A single compliance violation found during evaluation.

    Attributes:
        pattern_id: ID of the pattern that was violated.
        pattern_signature: The pattern signature text for context.
        description: Human-readable description of the violation.
        severity: Severity level (critical, major, minor, info).
        line_reference: Optional line number or range where the violation occurs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str = Field(
        ...,
        min_length=1,
        description="ID of the pattern that was violated",
    )
    pattern_signature: str = Field(
        ...,
        min_length=1,
        description="Pattern signature text for context",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Human-readable description of how the code violates the pattern",
    )
    severity: str = Field(
        default="major",
        description="Severity level: critical, major, minor, info",
    )
    line_reference: str | None = Field(
        default=None,
        description="Line number or range where the violation occurs (e.g., 'line 42')",
    )


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


class ModelComplianceResult(BaseModel):
    """Output model for pattern compliance evaluation.

    Contains the list of violations found, overall compliance status,
    and confidence in the evaluation result.

    Attributes:
        success: Whether the evaluation completed without errors.
        violations: List of compliance violations found.
        compliant: Whether the code is compliant with all checked patterns.
        confidence: Confidence score in the evaluation result (0.0-1.0).
        metadata: Metadata about the evaluation operation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    success: bool = Field(
        ...,
        description="Whether the compliance evaluation completed without errors",
    )
    violations: list[ModelComplianceViolation] = Field(
        default_factory=list,
        description="List of compliance violations found",
    )
    compliant: bool = Field(
        default=True,
        description="Whether the code is compliant with all checked patterns",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score in the evaluation result (0.0-1.0)",
    )
    metadata: ModelComplianceMetadata | None = Field(
        default=None,
        description="Metadata about the evaluation operation",
    )


__all__ = [
    "ModelComplianceMetadata",
    "ModelComplianceResult",
    "ModelComplianceViolation",
]
