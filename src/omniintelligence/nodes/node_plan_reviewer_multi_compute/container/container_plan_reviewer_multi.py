# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for the handler of node_plan_reviewer_multi_compute.

The handler is built here, the one binding site, and the node resolves it
through ``resolve_plan_reviewer_multi_compute_handler`` instead of constructing
it (OMN-21679).
"""

from __future__ import annotations

from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.handler_confidence_scorer import (
    ProtocolDBConnection,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.handler_plan_reviewer_multi_compute import (
    HandlerPlanReviewerMultiCompute,
    ModelCaller,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.strategies.handler_sequential_critique import (
    CriticCaller,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)


def resolve_plan_reviewer_multi_compute_handler(
    *,
    model_callers: dict[EnumReviewModel, ModelCaller],
    db_conn: ProtocolDBConnection | None,
    critic_caller: CriticCaller | None,
) -> HandlerPlanReviewerMultiCompute:
    """Resolve the HandlerPlanReviewerMultiCompute bound to the injected callers."""
    return HandlerPlanReviewerMultiCompute(
        model_callers=model_callers,
        db_conn=db_conn,
        critic_caller=critic_caller,
    )


__all__ = ["resolve_plan_reviewer_multi_compute_handler"]
