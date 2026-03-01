# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
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
from collections.abc import Awaitable, Callable

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

logger = logging.getLogger(__name__)

# Type alias: a caller receives (plan_text, categories) and returns findings.
ModelCaller = Callable[
    [str, list[EnumPlanReviewCategory]],
    Awaitable[list[PlanReviewFinding]],
]


async def handle_independent_merge(
    plan_text: str,
    categories: list[EnumPlanReviewCategory],
    model_callers: dict[EnumReviewModel, ModelCaller],
    accuracy_weights: dict[EnumReviewModel, float],
) -> list[PlanReviewFindingWithConfidence]:
    """Run S4 independent_merge strategy.

    All models are invoked concurrently.  Their findings are deduplicated
    by ``(category, location_normalized)`` and merged into a single list.

    Args:
        plan_text: The plan content to review.
        categories: Review categories to evaluate.
        model_callers: Mapping of model ID to async callable.
        accuracy_weights: Per-model accuracy weight.  Missing keys default
            to ``0.5``.

    Returns:
        List of ``PlanReviewFindingWithConfidence`` — one entry per unique
        ``(category, location_normalized)`` pair across all model outputs.
    """
    if not model_callers:
        return []

    # Run all models concurrently with per-item exception capture.
    ordered_models = list(model_callers.keys())
    raw = await asyncio.gather(
        *[model_callers[m](plan_text, categories) for m in ordered_models],
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

    total_weight = sum(accuracy_weights.get(m, 0.5) for m in model_callers)
    if total_weight == 0.0:
        total_weight = float(len(model_callers))

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
        source_weight = sum(accuracy_weights.get(m, 0.5) for m in source_models)
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
            key=lambda m: accuracy_weights.get(m, 0.5),
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


__all__ = ["ModelCaller", "handle_independent_merge"]
