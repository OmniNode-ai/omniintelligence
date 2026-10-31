# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""S4 — independent_merge strategy handler for NodePlanReviewerMultiCompute.

All four models review the plan independently and in parallel.  Every
finding from every model is included in the output, deduplicated by
``(category, location_normalized)``.

For each deduplicated group:

* ``sources``    — list of all model IDs that raised the finding
* ``confidence`` — ``Σ(weight[m] for m in sources) / Σ(weight[m] for m in all)``
* ``severity``   — ``"BLOCK"`` if *any* source says ``"BLOCK"``; otherwise
                   the severity from the first source finding
* ``patch``      — taken from the source model with the highest accuracy
                   weight (``None`` if no source produced a patch)
* ``description`` / ``suggested_fix`` — from the highest-accuracy source

Unlike S1 ``panel_vote``, every finding is included regardless of how many
models agree.  The confidence score naturally reflects single-model findings
(lower) vs. unanimous findings (higher).

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


class HandlerIndependentMerge:
    """Typed entry point for the independent_merge strategy."""

    async def handle(self, request: ModelStrategyReviewRequest) -> StrategyFindings:
        """Run S4 independent_merge strategy.

        All models are invoked concurrently.  Their findings are deduplicated
        by ``(category, location_normalized)`` and merged into a single list.

        Args:
            request: Typed request; its fields are:

            plan_text: The plan content to review.
            categories: Review categories to evaluate.
            callers: Mapping of model ID to async callable.
            weights: Per-model accuracy weight.  Missing keys default
                to ``0.5``.

        Returns:
            List of ``PlanReviewFindingWithConfidence`` — one entry per unique
            ``(category, location_normalized)`` pair across all model outputs.
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
                    "independent_merge: model %s call failed — treating as empty",
                    model,
                    exc_info=outcome,
                )
                results[model] = []
            else:
                results[model] = outcome

        total_weight = sum(request.weights.get(m, 0.5) for m in request.callers)
        if total_weight == 0.0:
            total_weight = float(len(request.callers))

        # Group by (category, location_normalized).
        groups: dict[
            tuple[EnumPlanReviewCategory, str],
            list[tuple[EnumReviewModel, PlanReviewFinding]],
        ] = defaultdict(list)

        for model, findings in results.items():
            for finding in findings:
                key = (finding.category, finding.location_normalized)
                groups[key].append((model, finding))

        output: list[PlanReviewFindingWithConfidence] = []

        for (category, location_norm), model_findings in groups.items():
            source_models = [m for m, _ in model_findings]

            # Confidence = sum of source weights / sum of all participating weights.
            source_weight = sum(request.weights.get(m, 0.5) for m in source_models)
            confidence = min(source_weight / total_weight, 1.0)

            # Severity escalation: BLOCK if any source says BLOCK.
            severity = (
                SEVERITY_BLOCK
                if any(f.severity == SEVERITY_BLOCK for _, f in model_findings)
                else model_findings[0][1].severity
            )

            # Pick best source (highest accuracy weight) for description/fix/patch.
            best_model = max(
                source_models,
                key=lambda m: request.weights.get(m, 0.5),
            )
            best_finding = next(f for m, f in model_findings if m == best_model)

            # Use the patch from the best source, if any source produced one.
            patch: str | None = best_finding.patch
            if patch is None:
                patch = next(
                    (f.patch for _, f in model_findings if f.patch is not None),
                    None,
                )

            output.append(
                PlanReviewFindingWithConfidence(
                    category=category,
                    location=best_finding.location,
                    location_normalized=location_norm,
                    severity=severity,
                    description=best_finding.description,
                    suggested_fix=best_finding.suggested_fix,
                    patch=patch,
                    confidence=confidence,
                    sources=source_models,
                )
            )

        logger.debug(
            "independent_merge: %d raw findings → %d deduplicated",
            sum(len(v) for v in results.values()),
            len(output),
        )
        return output


__all__ = ["HandlerIndependentMerge"]
