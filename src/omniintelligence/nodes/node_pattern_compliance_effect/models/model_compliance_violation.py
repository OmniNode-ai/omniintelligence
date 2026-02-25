# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Compliance violation model for Pattern Compliance Compute Node.

Ticket: OMN-2256
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Valid severity levels for compliance violations.
SeverityLiteral = Literal["critical", "major", "minor", "info"]


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
    severity: SeverityLiteral = Field(
        default="major",
        description="Severity level: critical, major, minor, info",
    )
    line_reference: str | None = Field(
        default=None,
        description="Line number or range where the violation occurs (e.g., 'line 42')",
    )


__all__ = ["ModelComplianceViolation", "SeverityLiteral"]
