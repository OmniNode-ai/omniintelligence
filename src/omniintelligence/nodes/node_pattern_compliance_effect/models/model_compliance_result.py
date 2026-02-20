"""Output model for Pattern Compliance Compute Node.

Defines the result structure for pattern compliance evaluation,
including the list of violations found and overall compliance status.

Ticket: OMN-2256
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_compliance_effect.models.model_compliance_metadata import (
    ModelComplianceMetadata,
)
from omniintelligence.nodes.node_pattern_compliance_effect.models.model_compliance_violation import (
    ModelComplianceViolation,
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
