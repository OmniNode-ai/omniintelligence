# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""S1 — panel_vote strategy handler for NodePlanReviewerMultiCompute.

All four models review the plan independently and in parallel.  A finding
is included in the output only if **at least two** models agree on the
same ``(category, location_normalized)`` pair.

Confidence formula::

    confidence = Σ(weight[m] for m in agreeing_models)
               / Σ(weight[m] for m in all_participating_models)

The patch for an included finding is taken from the agreeing model with
the highest accuracy weight.

Ticket: OMN-3288
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_plan_review_category import (
    EnumPlanReviewCategory,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_review_finding import (
    SEVERITY_BLOCK,
    PlanReviewFinding,
    PlanReviewFindingWithConfidence,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_strategy_review_request import (
    ModelStrategyReviewRequest,
    StrategyFindings,
)

logger = logging.getLogger(__name__)

# Minimum number of models that must agree for a finding to be included.
_MIN_AGREEMENT = 2


class HandlerPanelVote:
    """Typed entry point for the panel_vote strategy."""

    async def handle(self, request: ModelStrategyReviewRequest) -> StrategyFindings:
        """Run S1 panel_vote strategy.

        All models in ``callers`` are invoked concurrently.  Findings are
        grouped by ``(category, location_normalized)``.  A group is kept when
        ≥ ``_MIN_AGREEMENT`` models raised it.

        Args:
            request: Typed request; its fields are:

            plan_text: The plan content to review.
            categories: Review categories to evaluate.
            callers: Mapping of model ID to async callable.
            weights: Per-model accuracy weight from
                ``plan_reviewer_model_accuracy``.  Models absent from this
                dict default to ``0.5``.

        Returns:
            List of ``PlanReviewFindingWithConfidence`` items where agreement
            count ≥ ``_MIN_AGREEMENT``.  Empty list if no findings pass.
        """
        if not request.callers:
            return []

        # Run all models concurrently with per-item exception capture.
        ordered_models = list(request.callers.keys())
        raw = await asyncio.gather(
            *[
                request.callers[m](request.plan_text, request.categories)
                for m in ordered_models
            ],
            return_exceptions=True,
        )
        results: dict[EnumReviewModel, list[PlanReviewFinding]] = {}
        for model, outcome in zip(ordered_models, raw, strict=False):
            if isinstance(outcome, BaseException):
                logger.exception(
                    "panel_vote: model %s call failed — treating as empty",
                    model,
                    exc_info=outcome,
                )
                results[model] = []
            else:
                results[model] = outcome

        total_weight = sum(request.weights.get(m, 0.5) for m in request.callers)
        if total_weight == 0.0:
            total_weight = float(len(request.callers))

        # Group findings by (category, location_normalized).
        # key → list of (model, finding) pairs
        groups: dict[
            tuple[EnumPlanReviewCategory, str],
            list[tuple[EnumReviewModel, PlanReviewFinding]],
        ] = defaultdict(list)

        for model, findings in results.items():
            for finding in findings:
                key = (finding.category, finding.location_normalized)
                groups[key].append((model, finding))

        # Filter to groups with ≥ MIN_AGREEMENT models agreeing.
        output: list[PlanReviewFindingWithConfidence] = []

        for (category, location_norm), model_findings in groups.items():
            agreeing_models = [m for m, _ in model_findings]
            if len(agreeing_models) < _MIN_AGREEMENT:
                continue

            # Confidence = sum of agreeing weights / sum of all participating weights
            agreeing_weight = sum(request.weights.get(m, 0.5) for m in agreeing_models)
            confidence = agreeing_weight / total_weight

            # Escalate severity: BLOCK if any agreeing model says BLOCK.
            severity = (
                SEVERITY_BLOCK
                if any(f.severity == SEVERITY_BLOCK for _, f in model_findings)
                else model_findings[0][1].severity
            )

            # Pick description/fix from the highest-accuracy agreeing model.
            best_model = max(
                agreeing_models,
                key=lambda m: request.weights.get(m, 0.5),
            )
            best_finding = next(f for m, f in model_findings if m == best_model)

            output.append(
                PlanReviewFindingWithConfidence(
                    category=category,
                    location=best_finding.location,
                    location_normalized=location_norm,
                    severity=severity,
                    description=best_finding.description,
                    suggested_fix=best_finding.suggested_fix,
                    patch=best_finding.patch,
                    confidence=min(confidence, 1.0),
                    sources=agreeing_models,
                )
            )

        logger.debug(
            "panel_vote: %d groups, %d passed ≥%d agreement threshold",
            len(groups),
            len(output),
            _MIN_AGREEMENT,
        )
        return output


__all__ = ["HandlerPanelVote"]
