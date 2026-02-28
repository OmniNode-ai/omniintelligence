# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for Plan Reviewer Compute Node."""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_plan_reviewer_compute.models.model_plan_reviewer_output import (
    EnumPlanReviewCategory,
)


class ModelPlanReviewerComputeCommand(BaseModel):
    """Input model for plan review operations.

    Accepts a plan document text and an optional list of review categories
    to run. Defaults to all six categories (R1-R6).
    """

    plan_text: str = Field(
        ...,
        min_length=1,
        description="Full text of the plan document to review.",
    )
    review_categories: list[EnumPlanReviewCategory] = Field(
        default_factory=lambda: list(EnumPlanReviewCategory),
        description=(
            "Which review categories to run. Defaults to all six (R1-R6). "
            "Pass a subset to run targeted checks only."
        ),
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPlanReviewerComputeCommand"]
