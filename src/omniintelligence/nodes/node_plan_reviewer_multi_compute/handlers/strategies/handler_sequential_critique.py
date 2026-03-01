# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""S3 — sequential_critique strategy handler for NodePlanReviewerMultiCompute.

Two-stage drafter → critic pipeline:

1. **Drafter** (``qwen3-coder``) produces an initial set of findings
   across all requested categories.
2. **Critic** (``deepseek-r1``) receives both the original plan text and
   the drafter's findings.  It returns a structured critique:

   * ``confirmed`` — finding IDs the critic agrees with (kept as-is)
   * ``rejected``  — finding IDs the critic believes are false-positives
                     (removed from output)
   * ``added``     — new findings the drafter missed (added with the
                     critic as the source)

Final output = confirmed drafter findings + critic-added findings.

Confidence formula:

    confirmed finding: drafter_weight * critic_weight /
                       (drafter_weight + critic_weight) * 2
    added finding:     critic_weight / (drafter_weight + critic_weight)

Because the critic model does not produce ``PlanReviewFinding`` objects
directly (its output is a structured dict parsed from JSON/text), a
``CriticCaller`` callable with a distinct signature is used.

Architecture note:
    This module contains only pure business logic.  No ``httpx`` or
    ``os.getenv`` usage is allowed here (ARCH-002).

Ticket: OMN-3288
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

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

logger = logging.getLogger(__name__)

# Fixed role assignment for S3.
_DRAFTER = EnumReviewModel.QWEN3_CODER
_CRITIC = EnumReviewModel.DEEPSEEK_R1

# Type alias: standard model caller.
ModelCaller = Callable[
    [str, list[EnumPlanReviewCategory]],
    Awaitable[list[PlanReviewFinding]],
]

# Type alias: critic caller receives (plan_text, drafter_findings) and returns
# a CritiqueResult dict.
CritiqueResult = dict[str, list[UUID] | list[PlanReviewFinding]]
CriticCaller = Callable[
    [str, list[PlanReviewFinding]],
    Awaitable[CritiqueResult],
]


async def handle_sequential_critique(
    plan_text: str,
    categories: list[EnumPlanReviewCategory],
    drafter_caller: ModelCaller,
    critic_caller: CriticCaller,
    accuracy_weights: dict[EnumReviewModel, float],
) -> list[PlanReviewFindingWithConfidence]:
    """Run S3 sequential_critique strategy.

    Args:
        plan_text: The plan content to review.
        categories: Review categories to evaluate.
        drafter_caller: Async callable for ``qwen3-coder`` (produces
            initial findings).
        critic_caller: Async callable for ``deepseek-r1`` (receives plan
            + drafter findings; returns a ``CritiqueResult``).
        accuracy_weights: Per-model accuracy weight.  Missing keys default
            to ``0.5``.

    Returns:
        List of ``PlanReviewFindingWithConfidence``:
        - confirmed drafter findings (critic agreed)
        - critic-added findings (drafter missed)
        - rejected drafter findings are **not** present
    """
    drafter_weight = accuracy_weights.get(_DRAFTER, 0.5)
    critic_weight = accuracy_weights.get(_CRITIC, 0.5)
    combined_weight = drafter_weight + critic_weight
    if combined_weight == 0.0:
        combined_weight = 1.0

    # Stage 1: drafter produces initial findings.
    try:
        drafter_findings = await drafter_caller(plan_text, categories)
    except Exception:
        logger.exception("sequential_critique: drafter call failed — empty findings")
        drafter_findings = []

    # Stage 2: critic reviews plan + drafter findings.
    critique: CritiqueResult = {"confirmed": [], "rejected": [], "added": []}
    try:
        critique = await critic_caller(plan_text, drafter_findings)
    except Exception:
        logger.exception(
            "sequential_critique: critic call failed — treating all drafter findings as confirmed"
        )
        critique = {
            "confirmed": [f.finding_id for f in drafter_findings],
            "rejected": [],
            "added": [],
        }

    confirmed_ids: set[UUID] = {
        uid for uid in critique.get("confirmed", []) if isinstance(uid, UUID)
    }
    added_findings: list[PlanReviewFinding] = [
        f for f in critique.get("added", []) if isinstance(f, PlanReviewFinding)
    ]

    output: list[PlanReviewFindingWithConfidence] = []

    # Confirmed drafter findings.
    for finding in drafter_findings:
        if finding.finding_id not in confirmed_ids:
            continue
        confidence = (drafter_weight * critic_weight) / (combined_weight / 2.0)
        confidence = min(confidence / combined_weight, 1.0)
        output.append(
            PlanReviewFindingWithConfidence(
                category=finding.category,
                location=finding.location,
                location_normalized=finding.location_normalized,
                severity=finding.severity,
                description=finding.description,
                suggested_fix=finding.suggested_fix,
                patch=finding.patch,
                confidence=confidence,
                sources=[_DRAFTER],
            )
        )

    # Critic-added findings.
    for finding in added_findings:
        confidence = min(critic_weight / combined_weight, 1.0)
        output.append(
            PlanReviewFindingWithConfidence(
                category=finding.category,
                location=finding.location,
                location_normalized=finding.location_normalized,
                severity=finding.severity,
                description=finding.description,
                suggested_fix=finding.suggested_fix,
                patch=finding.patch,
                confidence=confidence,
                sources=[_CRITIC],
            )
        )

    logger.debug(
        "sequential_critique: %d drafter, %d confirmed, %d added",
        len(drafter_findings),
        len(confirmed_ids),
        len(added_findings),
    )
    return output


__all__ = [
    "CriticCaller",
    "CritiqueResult",
    "ModelCaller",
    "handle_sequential_critique",
]
