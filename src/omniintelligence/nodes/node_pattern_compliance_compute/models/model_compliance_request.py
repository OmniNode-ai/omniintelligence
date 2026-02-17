"""Input model for Pattern Compliance Compute Node.

Defines the request structure for evaluating code against applicable patterns.
The caller provides the code content and the list of patterns to check against.

Ticket: OMN-2256
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelApplicablePattern(BaseModel):
    """A single pattern to check compliance against.

    This model represents a pattern retrieved from the pattern store
    (OMN-2253) that is applicable to the code being evaluated.

    Attributes:
        pattern_id: Unique identifier for the pattern.
        pattern_signature: The pattern signature text describing the pattern.
        domain_id: Domain the pattern belongs to (e.g., "onex", "python").
        confidence: Confidence score of the pattern (0.0-1.0).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the pattern",
    )
    pattern_signature: str = Field(
        ...,
        min_length=1,
        description="Pattern signature text describing what the pattern enforces",
    )
    domain_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Domain the pattern belongs to",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the pattern",
    )


class ModelComplianceRequest(BaseModel):
    """Input model for pattern compliance evaluation.

    Contains the code to evaluate and the list of patterns to check against.
    The patterns are typically retrieved from the pattern store API (OMN-2253).

    Attributes:
        file_path: Path to the source file being evaluated.
        content: Source code content to evaluate.
        language: Programming language of the content.
        applicable_patterns: List of patterns to check compliance against.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str = Field(
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
