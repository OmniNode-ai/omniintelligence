# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Typed request models for the plan-reviewer strategy handlers.

Each strategy handler takes one request model through ``handle(request)``
instead of positional parameters.  The caller type aliases live here so the
request models and the handlers share one definition.

Ticket: OMN-21536
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_plan_review_category import (
    EnumPlanReviewCategory,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_review_finding import (
    PlanReviewFinding,
    PlanReviewFindingWithConfidence,
)

# A caller receives (plan_text, categories) and returns findings.
ModelCaller = Callable[
    [str, list[EnumPlanReviewCategory]],
    Awaitable[list[PlanReviewFinding]],
]

# A critic caller receives (plan_text, drafter_findings) and returns a
# CritiqueResult dict.
CritiqueResult = dict[str, list[UUID] | list[PlanReviewFinding]]
CriticCaller = Callable[
    [str, list[PlanReviewFinding]],
    Awaitable[CritiqueResult],
]

# What a strategy handler returns: the merged findings with their confidence.
StrategyFindings = list[PlanReviewFindingWithConfidence]


class ModelStrategyReviewRequest(BaseModel):
    """Request for the S1, S2 and S4 strategy handlers.

    Attributes:
        plan_text: The plan content to review.
        categories: Review categories to evaluate.
        callers: Mapping of model ID to async caller.
        weights: Per-model accuracy weight; models absent from the
            mapping default to ``0.5``.
    """

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    plan_text: str
    categories: list[EnumPlanReviewCategory]
    callers: dict[EnumReviewModel, ModelCaller] = Field(default_factory=dict)
    weights: dict[EnumReviewModel, float] = Field(default_factory=dict)


class ModelSequentialCritiqueRequest(BaseModel):
    """Request for the S3 sequential_critique strategy handler.

    Attributes:
        plan_text: The plan content to review.
        categories: Review categories to evaluate.
        drafter_caller: Async caller for the drafter model (initial findings).
        critic_caller: Async caller for the critic model.
        weights: Per-model accuracy weight; missing keys default to
            ``0.5``.
    """

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    plan_text: str
    categories: list[EnumPlanReviewCategory]
    drafter_caller: ModelCaller
    critic_caller: CriticCaller
    weights: dict[EnumReviewModel, float] = Field(default_factory=dict)


__all__ = [
    "CriticCaller",
    "CritiqueResult",
    "ModelCaller",
    "ModelSequentialCritiqueRequest",
    "ModelStrategyReviewRequest",
    "StrategyFindings",
]
