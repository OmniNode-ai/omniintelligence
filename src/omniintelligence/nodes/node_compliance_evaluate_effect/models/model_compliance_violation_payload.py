"""Compliance violation payload model for compliance-evaluated events.

Ticket: OMN-2339
"""

from __future__ import annotations

from typing import Literal

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


__all__ = ["ModelComplianceViolationPayload", "SeverityLiteral"]
