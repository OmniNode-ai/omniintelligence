# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for NodePlanReviewerMultiCompute.

Defines ``ModelPlanReviewerMultiOutput`` — the frozen result model returned
by the node dispatcher after all strategy handlers complete and the DB audit
row is written.

Ticket: OMN-3290
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_strategy import (
    EnumReviewStrategy,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_review_finding import (
    PlanReviewFindingWithConfidence,
)


class ModelPlanReviewerMultiOutput(BaseModel):
    """Output of the multi-LLM plan reviewer node.

    Returned by ``handle_plan_reviewer_multi_compute`` after all strategy
    handlers complete.  The model is frozen so it can be safely cached or
    passed between threads.

    Attributes:
        strategy_run_id: UUID of the row inserted into
            ``plan_reviewer_strategy_runs``.  ``None`` when the DB write
            was skipped (``strategy_run_stored=False``).
        strategy: The review strategy that was executed.
        models_used: The model IDs that participated in this run.
        findings: Merged findings with per-finding confidence scores.
            Empty list = plan is clean (no issues found).
        findings_count: ``len(findings)`` — convenience field for callers
            that only need the count.
        strategy_run_stored: ``True`` when the audit row was successfully
            written to ``plan_reviewer_strategy_runs``.  ``False`` when the
            DB was unavailable; the review result itself is still valid.
        run_id: Echo of the caller-supplied ``run_id`` from the input
            command.

    Example::

        output = ModelPlanReviewerMultiOutput(
            strategy_run_id=uuid4(),
            strategy=EnumReviewStrategy.S1_PANEL_VOTE,
            models_used=[EnumReviewModel.QWEN3_CODER, EnumReviewModel.DEEPSEEK_R1],
            findings=[...],
            findings_count=3,
            strategy_run_stored=True,
            run_id="OMN-1234",
        )
    """

    model_config = {"frozen": True, "extra": "forbid"}

    strategy_run_id: UUID | None = Field(
        default=None,
        description=(
            "UUID of the ``plan_reviewer_strategy_runs`` row. "
            "``None`` when DB write was skipped."
        ),
    )
    strategy: EnumReviewStrategy = Field(
        description="Review strategy that was executed.",
    )
    models_used: list[EnumReviewModel] = Field(
        description="Model IDs that participated in this run.",
        min_length=1,
    )
    findings: list[PlanReviewFindingWithConfidence] = Field(
        default_factory=list,
        description="Merged findings with confidence scores.  Empty = plan is clean.",
    )
    findings_count: int = Field(
        description="Total number of findings (len(findings)).",
        ge=0,
    )
    strategy_run_stored: bool = Field(
        description=(
            "``True`` when the audit row was written successfully. "
            "``False`` when DB was unavailable (review result is still valid)."
        ),
    )
    run_id: str | None = Field(
        default=None,
        description="Echo of the caller-supplied run_id from the input command.",
    )


__all__ = ["ModelPlanReviewerMultiOutput"]
