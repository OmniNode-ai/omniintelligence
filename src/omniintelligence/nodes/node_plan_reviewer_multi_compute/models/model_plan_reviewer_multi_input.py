# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input command model for NodePlanReviewerMultiCompute.

Defines ``ModelPlanReviewerMultiCommand`` — the frozen input model that callers
pass to the node dispatcher.

Ticket: OMN-3290
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_plan_review_category import (
    EnumPlanReviewCategory,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_strategy import (
    EnumReviewStrategy,
)


class ModelPlanReviewerMultiCommand(BaseModel):
    """Input command for the multi-LLM plan reviewer node.

    Callers build one of these and pass it to
    ``handle_plan_reviewer_multi_compute`` (or the node shell's ``compute``
    method).  The model is frozen so handlers can safely pass it between
    async tasks without mutation risk.

    Attributes:
        plan_text: The full plan content to be reviewed.  Must be non-empty.
        strategy: Review strategy to apply.  Defaults to
            ``INDEPENDENT_MERGE`` (S4 — widest coverage, all findings
            included regardless of agreement count).
        review_categories: Subset of R1-R6 categories to evaluate.
            Defaults to all six categories.
        model_ids: Explicit list of model IDs to use.  When ``None``, all
            four models registered in ``EnumReviewModel`` are used.
        run_id: Caller-supplied correlation ID written to the
            ``plan_reviewer_strategy_runs`` audit row.  May be any string
            (ticket ID, session ID, UUID).  ``None`` is allowed and stored
            as an empty string in the DB row.

    Example::

        cmd = ModelPlanReviewerMultiCommand(
            plan_text="## Plan\\n1. Step one\\n2. Step two",
            strategy=EnumReviewStrategy.S1_PANEL_VOTE,
            run_id="OMN-1234",
        )
    """

    model_config = {"frozen": True, "extra": "forbid"}

    plan_text: str = Field(
        description="Full plan content to review.  Must be non-empty.",
        min_length=1,
    )
    strategy: EnumReviewStrategy = Field(
        default=EnumReviewStrategy.S4_INDEPENDENT_MERGE,
        description="Review strategy.  Defaults to S4 independent_merge.",
    )
    review_categories: list[EnumPlanReviewCategory] = Field(
        default_factory=lambda: list(EnumPlanReviewCategory),
        description="R1-R6 categories to evaluate.  Defaults to all six.",
    )
    model_ids: list[EnumReviewModel] | None = Field(
        default=None,
        description=(
            "Explicit model list.  ``None`` = all four registered models "
            "(qwen3-coder, deepseek-r1, gemini-flash, glm-4)."
        ),
    )
    run_id: str | None = Field(
        default=None,
        description=(
            "Caller-supplied correlation ID stored in the audit row. "
            "``None`` is stored as an empty string."
        ),
    )


__all__ = ["ModelPlanReviewerMultiCommand"]
