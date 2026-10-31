# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Violation fields parsed from the LLM response (OMN-21536)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_pattern_compliance_effect.models.model_compliance_violation import (
    SeverityLiteral,
)


class ModelComplianceParsedViolation(BaseModel):
    """Normalized parser output, preserving empty strings from LLM responses."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    pattern_id: str
    pattern_signature: str
    description: str
    severity: SeverityLiteral
    line_reference: str | None


__all__ = ["ModelComplianceParsedViolation"]
