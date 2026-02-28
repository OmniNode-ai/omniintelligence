# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Plan Reviewer Compute Node — thin shell delegating to handler."""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_plan_reviewer_compute.handlers import (
    handle_plan_reviewer_compute,
)
from omniintelligence.nodes.node_plan_reviewer_compute.models import (
    ModelPlanReviewerComputeCommand,
    ModelPlanReviewerComputeOutput,
)


class NodePlanReviewerCompute(
    NodeCompute[ModelPlanReviewerComputeCommand, ModelPlanReviewerComputeOutput]
):
    """Pure compute node for adversarial review of implementation plans.

    Checks six failure categories (R1-R6): count integrity, acceptance
    criteria strength, scope violations, integration traps, idempotency,
    and verification soundness. Returns structured findings and text patches.

    This node is a thin shell following the ONEX declarative pattern.
    All computation logic is delegated to the handler function.
    """

    async def compute(
        self, input_data: ModelPlanReviewerComputeCommand
    ) -> ModelPlanReviewerComputeOutput:
        """Run adversarial review by delegating to handler function."""
        return handle_plan_reviewer_compute(input_data)


__all__ = ["NodePlanReviewerCompute"]
