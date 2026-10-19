# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Support counts of one rubric rule (OMN-21186)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_review_rubric_check_compute.models.model_review_actionability_counts import (
    ModelReviewActionabilityCounts,
)
from omniintelligence.nodes.node_review_rubric_check_compute.models.model_review_truth_counts import (
    ModelReviewTruthCounts,
)


class ModelReviewRuleSupport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    truth: ModelReviewTruthCounts
    actionability: ModelReviewActionabilityCounts


__all__ = ["ModelReviewRuleSupport"]
