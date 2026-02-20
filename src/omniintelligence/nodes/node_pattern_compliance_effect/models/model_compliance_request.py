"""Input model for Pattern Compliance Compute Node.

Defines the request structure for evaluating code against applicable patterns.
The caller provides the code content and the list of patterns to check against.

Ticket: OMN-2256
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_compliance_effect.models.model_applicable_pattern import (
    ModelApplicablePattern,
)


class ModelComplianceRequest(BaseModel):
    """Input model for pattern compliance evaluation.

    Contains the code to evaluate and the list of patterns to check against.
    The patterns are typically retrieved from the pattern store API (OMN-2253).

    Attributes:
        correlation_id: UUID for end-to-end tracing across operations.
        source_path: Path to the source file being evaluated.
        content: Source code content to evaluate.
        language: Programming language of the content.
        applicable_patterns: List of patterns to check compliance against.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    correlation_id: UUID = Field(
        ...,
        description="Correlation ID for end-to-end tracing",
    )
    source_path: str = Field(
        ...,
        min_length=1,
        description="Path to the source file being evaluated",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Source code content to evaluate for compliance",
    )
    language: str = Field(
        default="python",
        description="Programming language of the content",
    )
    applicable_patterns: list[ModelApplicablePattern] = Field(
        ...,
        min_length=1,
        description="List of patterns to check compliance against (from OMN-2253 API)",
    )


__all__ = ["ModelApplicablePattern", "ModelComplianceRequest"]
