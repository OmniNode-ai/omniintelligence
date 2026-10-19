# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Output of the review rubric check node (OMN-21186)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_review_rubric_check_compute.models.enum_review_rubric_check_outcome import (
    EnumReviewRubricCheckOutcome,
)
from omniintelligence.nodes.node_review_rubric_check_compute.models.model_review_rubric_refusal import (
    ModelReviewRubricRefusal,
)


class ModelReviewRubricCheckResult(BaseModel):
    """A pass, or the named refusal; a refusal is data, never a raise."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    rubric_source: str
    outcome: EnumReviewRubricCheckOutcome
    refusal: ModelReviewRubricRefusal | None = None
    version: int | None = None
    content_hash: str = ""
    rule_count: int = Field(default=0, ge=0)
    token_count: int = Field(default=0, ge=0)
    token_budget: int = Field(gt=0)
    correlation_id: UUID | None = None


__all__ = ["ModelReviewRubricCheckResult"]
