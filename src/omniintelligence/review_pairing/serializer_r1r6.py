# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""R1-R6 Finding Serializer for calibration alignment.

Converts R1-R6 PlanReviewFinding / PlanReviewFindingWithConfidence and
external ModelReviewFindingObserved into ModelCalibrationFindingTuple for use
in the alignment engine.

Reference: OMN-6166
"""

from __future__ import annotations

from uuid import uuid4

from omniintelligence.nodes.node_plan_reviewer_multi_compute.models import (
    PlanReviewFinding,
    PlanReviewFindingWithConfidence,
)
from omniintelligence.review_pairing.models import ModelReviewFindingObserved
from omniintelligence.review_pairing.models_calibration import (
    ModelCalibrationFindingTuple,
)


def serialize_plan_finding(
    finding: PlanReviewFinding,
    source_model_key: str,
) -> ModelCalibrationFindingTuple:
    """Convert a single R1-R6 PlanReviewFinding to ModelCalibrationFindingTuple.

    Args:
        finding: The raw per-model finding from plan review.
        source_model_key: Model key string (e.g. "qwen3-coder"). Provided
            by the caller since PlanReviewFinding.source_model is an enum.

    Returns:
        A ModelCalibrationFindingTuple with raw_finding=None (R1-R6 findings
        are not ModelReviewFindingObserved).
    """
    return ModelCalibrationFindingTuple(
        category=finding.category.value,
        location=finding.location,
        description=finding.description,
        severity=finding.severity,
        source_model=source_model_key,
        finding_id=finding.finding_id,
        raw_finding=None,
    )


def serialize_external_finding(
    finding: ModelReviewFindingObserved,
) -> ModelCalibrationFindingTuple:
    """Convert a ModelReviewFindingObserved to ModelCalibrationFindingTuple.

    Extracts category and source_model from the rule_id field.
    Expected format: ``ai-reviewer:{model}:{category}``.
    Falls back to category="unknown" and source_model={tool_name}
    for non-matching rule_id formats.

    Args:
        finding: The external review finding.

    Returns:
        A ModelCalibrationFindingTuple with raw_finding set to the original finding.
    """
    parts = finding.rule_id.split(":")
    if len(parts) >= 3 and parts[0] == "ai-reviewer":
        source_model = parts[1]
        category = parts[2]
    else:
        source_model = finding.tool_name
        category = "unknown"

    return ModelCalibrationFindingTuple(
        category=category,
        location=finding.file_path,
        description=finding.normalized_message,
        severity=finding.severity.value,
        source_model=source_model,
        finding_id=finding.finding_id,
        raw_finding=finding,
    )


def serialize_merged_finding(
    finding: PlanReviewFindingWithConfidence,
) -> list[ModelCalibrationFindingTuple]:
    """Explode a merged finding into one ModelCalibrationFindingTuple per source model.

    Preserves per-model provenance for calibration by creating a separate
    tuple for each model in finding.sources.

    Args:
        finding: The merged finding with confidence and sources list.

    Returns:
        List of ModelCalibrationFindingTuple, one per source model.
    """
    results: list[ModelCalibrationFindingTuple] = []
    for source in finding.sources:
        results.append(
            ModelCalibrationFindingTuple(
                category=finding.category.value,
                location=finding.location,
                description=finding.description,
                severity=finding.severity,
                source_model=source.value,
                finding_id=uuid4(),
                raw_finding=None,
            )
        )
    return results
