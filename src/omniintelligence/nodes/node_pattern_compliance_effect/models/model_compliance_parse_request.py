# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelComplianceParseRequest for compliance handlers (OMN-21536)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_compliance_effect.models.model_applicable_pattern import (
    ModelApplicablePattern,
)


class ModelComplianceParseRequest(BaseModel):
    """Raw LLM response and patterns used for signature lookup."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    raw_text: str
    patterns: list[ModelApplicablePattern] = Field(default_factory=list)


__all__ = ["ModelComplianceParseRequest"]
