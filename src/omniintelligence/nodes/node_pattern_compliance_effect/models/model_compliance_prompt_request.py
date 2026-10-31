# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelCompliancePromptRequest for compliance handlers (OMN-21536)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_compliance_effect.models.model_applicable_pattern import (
    ModelApplicablePattern,
)


class ModelCompliancePromptRequest(BaseModel):
    """Code and applicable patterns used to build the LLM prompt."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    content: str
    language: str
    patterns: list[ModelApplicablePattern] = Field(default_factory=list)


__all__ = ["ModelCompliancePromptRequest"]
