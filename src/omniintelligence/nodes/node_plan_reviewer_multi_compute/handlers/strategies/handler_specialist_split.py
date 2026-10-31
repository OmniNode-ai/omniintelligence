# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""S2 — specialist_split strategy handler for NodePlanReviewerMultiCompute.

Categories are assigned to models by domain strength.  Each model reviews
only its assigned categories.  All four invocations run concurrently.
Findings are merged directly — no majority vote is needed because each
category has exactly one owner.

Category-model assignment: R1/R5 -> qwen3-coder, R4/R6 -> deepseek-r1,
R2/R3 -> gemini-flash, tiebreaker (all, if empty) -> glm-4.

The ``glm-4`` tiebreaker model is only invoked when any other model
returns an empty findings list for its assigned categories.

Ticket: OMN-3288
"""

from __future__ import annotations

import asyncio
import logging

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
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_strategy_review_request import (
    ModelStrategyReviewRequest,
    StrategyFindings,
)

logger = logging.getLogger(__name__)

# Domain-strength assignment: model → list of owned categories.
_SPECIALIST_MAP: dict[EnumReviewModel, list[EnumPlanReviewCategory]] = {
    EnumReviewModel.QWEN3_CODER: [
        EnumPlanReviewCategory.R1_COUNTS,
        EnumPlanReviewCategory.R5_IDEMPOTENCY,
    ],
    EnumReviewModel.DEEPSEEK_R1: [
        EnumPlanReviewCategory.R4_INTEGRATION_TRAPS,
        EnumPlanReviewCategory.R6_VERIFICATION,
    ],
    EnumReviewModel.GEMINI_FLASH: [
        EnumPlanReviewCategory.R2_ACCEPTANCE_CRITERIA,
        EnumPlanReviewCategory.R3_SCOPE,
    ],
    # GLM-4 is the tiebreaker — called only when another model returns empty.
    EnumReviewModel.GLM_4: list(EnumPlanReviewCategory),
}


class HandlerSpecialistSplit:
    """Typed entry point for the specialist_split strategy."""

    async def handle(self, request: ModelStrategyReviewRequest) -> StrategyFindings:
        """Run S2 specialist_split strategy.

        Each specialist model is invoked concurrently for its assigned
        categories (filtered to those present in ``categories``).

        The ``glm-4`` tiebreaker is invoked **after** the three specialist
        results arrive, and only for the categories where its assigned
        specialist returned no findings.

        Confidence for each finding = the source model's accuracy weight
        divided by the sum of all participating model weights.

        Args:
            request: Typed request; its fields are:

            plan_text: The plan content to review.
            categories: Review categories to evaluate (may be a subset of all).
            callers: Mapping of model ID to async callable.
            weights: Per-model accuracy weight.  Missing keys default
                to ``0.5``.

        Returns:
            List of ``PlanReviewFindingWithConfidence`` items, one entry per
            raw finding (no deduplication across models because each category
            has exactly one owner).
        """
        if not request.callers:
            return []

        # Restrict each specialist to the intersection of its owned categories
        # and the requested categories.
        specialist_assignments: dict[EnumReviewModel, list[EnumPlanReviewCategory]] = {}
        for model, owned in _SPECIALIST_MAP.items():
            if model == EnumReviewModel.GLM_4:
                continue  # tiebreaker — handled separately
            assigned = [c for c in owned if c in request.categories]
            if assigned and model in request.callers:
                specialist_assignments[model] = assigned

        # Launch specialist calls concurrently with per-item exception capture.
        ordered_specialists = list(specialist_assignments.keys())
        raw = await asyncio.gather(
            *[
                request.callers[m](request.plan_text, specialist_assignments[m])
                for m in ordered_specialists
            ],
            return_exceptions=True,
        )
        specialist_results: dict[EnumReviewModel, list[PlanReviewFinding]] = {}
        for model, outcome in zip(ordered_specialists, raw, strict=False):
            if isinstance(outcome, BaseException):
                logger.exception(
                    "specialist_split: model %s call failed — treating as empty",
                    model,
                    exc_info=outcome,
                )
                specialist_results[model] = []
            else:
                specialist_results[model] = outcome

        # Determine which categories had empty output (need tiebreaker).
        covered_with_findings: set[EnumPlanReviewCategory] = set()
        for findings in specialist_results.values():
            for f in findings:
                covered_with_findings.add(f.category)

        tiebreaker_categories = [
            c for c in request.categories if c not in covered_with_findings
        ]

        tiebreaker_results: list[PlanReviewFinding] = []
        if tiebreaker_categories and EnumReviewModel.GLM_4 in request.callers:
            try:
                tiebreaker_results = await request.callers[EnumReviewModel.GLM_4](
                    request.plan_text, tiebreaker_categories
                )
            except Exception:
                logger.exception("specialist_split: glm-4 tiebreaker call failed")

        # Compute total weight across all models that actually ran.
        participating: set[EnumReviewModel] = set(specialist_assignments.keys())
        if tiebreaker_results:
            participating.add(EnumReviewModel.GLM_4)
        total_weight = sum(request.weights.get(m, 0.5) for m in participating)
        if total_weight == 0.0:
            total_weight = float(len(participating)) if participating else 1.0

        # Convert raw findings → PlanReviewFindingWithConfidence.
        output: list[PlanReviewFindingWithConfidence] = []

        def _convert(
            finding: PlanReviewFinding,
            source_model: EnumReviewModel,
        ) -> PlanReviewFindingWithConfidence:
            weight = request.weights.get(source_model, 0.5)
            confidence = min(weight / total_weight, 1.0)
            return PlanReviewFindingWithConfidence(
                category=finding.category,
                location=finding.location,
                location_normalized=finding.location_normalized,
                severity=finding.severity,
                description=finding.description,
                suggested_fix=finding.suggested_fix,
                patch=finding.patch,
                confidence=confidence,
                sources=[source_model],
            )

        for model, findings in specialist_results.items():
            for finding in findings:
                output.append(_convert(finding, model))

        for finding in tiebreaker_results:
            output.append(_convert(finding, EnumReviewModel.GLM_4))

        logger.debug(
            "specialist_split: %d findings from specialists, %d from tiebreaker",
            sum(len(v) for v in specialist_results.values()),
            len(tiebreaker_results),
        )
        return output


__all__ = ["HandlerSpecialistSplit"]
