# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""S3 — sequential_critique strategy handler for NodePlanReviewerMultiCompute.

Two-stage drafter → critic pipeline:

1. **Drafter** (``code-drafter``) produces an initial set of findings
   across all requested categories.
2. **Critic** (``deep-reasoner``) receives both the original plan text and
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

Ticket: OMN-3288
"""

from __future__ import annotations

import logging
from uuid import UUID

from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_review_finding import (
    PlanReviewFinding,
    PlanReviewFindingWithConfidence,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_strategy_review_request import (
    CriticCaller,
    CritiqueResult,
    ModelCaller,
    ModelSequentialCritiqueRequest,
)

logger = logging.getLogger(__name__)

# Fixed role assignment for S3.
_DRAFTER = EnumReviewModel.CODE_DRAFTER
_CRITIC = EnumReviewModel.DEEP_REASONER


class HandlerSequentialCritique:
    """Typed entry point for the sequential_critique strategy."""

    async def handle(
        self, request: ModelSequentialCritiqueRequest
    ) -> list[PlanReviewFindingWithConfidence]:
        """Run S3 sequential_critique strategy.

        Args:
            request: Typed request; its fields are:

            plan_text: The plan content to review.
            categories: Review categories to evaluate.
            drafter_caller: Async callable for ``code-drafter`` (produces
                initial findings).
            critic_caller: Async callable for ``deep-reasoner`` (receives plan
                + drafter findings; returns a ``CritiqueResult``).
            accuracy_weights: Per-model accuracy weight.  Missing keys default
                to ``0.5``.

        Returns:
            List of ``PlanReviewFindingWithConfidence``:
            - confirmed drafter findings (critic agreed)
            - critic-added findings (drafter missed)
            - rejected drafter findings are **not** present
        """
        plan_text = request.plan_text
        categories = request.categories
        drafter_caller = request.drafter_caller
        critic_caller = request.critic_caller
        accuracy_weights = request.weights
        drafter_weight = accuracy_weights.get(_DRAFTER, 0.5)
        critic_weight = accuracy_weights.get(_CRITIC, 0.5)
        combined_weight = drafter_weight + critic_weight
        if combined_weight == 0.0:
            combined_weight = 1.0

        # Stage 1: drafter produces initial findings.
        try:
            drafter_findings = await drafter_caller(plan_text, categories)
        except Exception:
            logger.exception(
                "sequential_critique: drafter call failed — empty findings"
            )
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


__all__ = ["CriticCaller", "CritiqueResult", "HandlerSequentialCritique", "ModelCaller"]
