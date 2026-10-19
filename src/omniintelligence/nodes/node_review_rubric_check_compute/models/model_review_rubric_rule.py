# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""One rule of a review rubric (OMN-21186)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_review_rubric_check_compute.models.model_review_rule_support import (
    ModelReviewRuleSupport,
)


class ModelReviewRubricRule(BaseModel):
    """A category, the instruction the reviewer reads, and the evidence behind it.

    ``repositories`` lists where the rule's examples came from: a rule carries
    its repositories so an overfit to one repository is visible (plan section 7).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    category: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    support: ModelReviewRuleSupport
    repositories: tuple[str, ...] = Field(min_length=1)


__all__ = ["ModelReviewRubricRule"]
