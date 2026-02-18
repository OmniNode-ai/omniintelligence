"""Output event model for node_compliance_evaluate_effect.

Defines the Kafka event payload published to
onex.evt.omniintelligence.compliance-evaluated.v1 after evaluation completes.

Ticket: OMN-2339
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

#: Valid severity levels (mirrors node_pattern_compliance_effect).
SeverityLiteral = Literal["critical", "major", "minor", "info"]


class ModelComplianceViolationPayload(BaseModel):
    """A single violation serialized in the compliance-evaluated event.

    Attributes:
        pattern_id: ID of the pattern that was violated.
        pattern_signature: Pattern signature text for context.
        description: Human-readable description of the violation.
        severity: Severity level.
        line_reference: Optional line reference string.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str = Field(..., min_length=1)
    pattern_signature: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    severity: SeverityLiteral = Field(default="major")
    line_reference: str | None = Field(default=None)


class ModelComplianceEvaluatedEvent(BaseModel):
    """Kafka event payload for onex.evt.omniintelligence.compliance-evaluated.v1.

    Published by NodeComplianceEvaluateEffect after each evaluation.
    Consumers (e.g., omnimemory) can use this to track compliance history
    or trigger downstream workflows.

    Attributes:
        event_type: Always "ComplianceEvaluated" for routing.
        correlation_id: Propagated from the originating command for tracing.
        source_path: Path of the file that was evaluated.
        content_sha256: SHA-256 fingerprint of the evaluated content.
        language: Programming language of the evaluated content.
        success: True if the LLM evaluation completed without errors.
        compliant: True if no violations were found.
        violations: List of violation details.
        confidence: Evaluation confidence score (0.0-1.0).
        patterns_checked: Number of patterns checked.
        model_used: LLM model identifier used for evaluation.
        status: Processing status (completed, llm_error, parse_error, etc.).
        processing_time_ms: Evaluation duration in milliseconds.
        evaluated_at: ISO-8601 timestamp of evaluation completion.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str = Field(
        default="ComplianceEvaluated",
        description="Always 'ComplianceEvaluated' for routing",
    )
    correlation_id: UUID = Field(
        ...,
        description="Correlation ID propagated from the originating command",
    )
    source_path: str = Field(
        ...,
        min_length=1,
        description="Path of the source file that was evaluated",
    )
    content_sha256: str = Field(
        ...,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 hex digest of the evaluated content (idempotency key)",
    )
    language: str = Field(
        default="python",
        description="Programming language of the evaluated content",
    )
    success: bool = Field(
        ...,
        description="True if the LLM evaluation completed without errors",
    )
    compliant: bool = Field(
        default=True,
        description="True if no violations were found",
    )
    violations: list[ModelComplianceViolationPayload] = Field(
        default_factory=list,
        description="List of compliance violations found",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Evaluation confidence score (0.0-1.0)",
    )
    patterns_checked: int = Field(
        default=0,
        ge=0,
        description="Number of patterns that were checked",
    )
    model_used: str | None = Field(
        default=None,
        description="LLM model identifier used for evaluation",
    )
    status: str = Field(
        default="completed",
        description="Processing status (completed, llm_error, parse_error, etc.)",
    )
    processing_time_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Evaluation duration in milliseconds",
    )
    evaluated_at: str = Field(
        ...,
        description="ISO-8601 timestamp of evaluation completion",
    )


__all__ = [
    "ModelComplianceEvaluatedEvent",
    "ModelComplianceViolationPayload",
    "SeverityLiteral",
]
