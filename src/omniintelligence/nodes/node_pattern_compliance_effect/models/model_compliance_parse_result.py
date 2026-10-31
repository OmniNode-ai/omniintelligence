# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelComplianceParseResult for compliance handlers (OMN-21536)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_compliance_effect.models.model_compliance_parsed_violation import (
    ModelComplianceParsedViolation,
)


class ModelComplianceParseResult(BaseModel):
    """Parsed compliance fields, including structured parse failures."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    compliant: bool
    violations: list[ModelComplianceParsedViolation] = Field(default_factory=list)
    confidence: float
    raw_response: str


__all__ = ["ModelComplianceParseResult"]
