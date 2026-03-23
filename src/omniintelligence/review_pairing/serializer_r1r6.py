# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Serializers for converting R1-R6 and external review findings to CalibrationFindingTuple.

Reference: OMN-6166 (epic OMN-6164)
"""

from __future__ import annotations

from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_review_finding import (
    PlanReviewFinding,
    PlanReviewFindingWithConfidence,
)
from omniintelligence.review_pairing.models import ReviewFindingObserved
from omniintelligence.review_pairing.models_calibration import (
    CalibrationFindingTuple,
)


def serialize_plan_finding(
    finding: PlanReviewFinding,
    source_model_key: str,
) -> CalibrationFindingTuple:
    """Convert a single PlanReviewFinding to CalibrationFindingTuple.

    Args:
        finding: Raw per-model finding where the source is known externally.
        source_model_key: Model key string provided by the caller.

    Returns:
        CalibrationFindingTuple with category from the enum value.
    """
    return CalibrationFindingTuple(
        category=finding.category.value,
        location=finding.location,
        description=finding.description,
        severity=finding.severity,
        source_model=source_model_key,
        finding_id=finding.finding_id,
        raw_finding=None,
    )


def serialize_merged_finding(
    finding: PlanReviewFindingWithConfidence,
) -> list[CalibrationFindingTuple]:
    """Explode a merged finding into one CalibrationFindingTuple per source model.

    This preserves per-model provenance for calibration. Each tuple gets
    source_model set to the individual model key from finding.sources.

    Args:
        finding: Merged finding with confidence scores and sources list.

    Returns:
        List of CalibrationFindingTuple, one per source model.
    """
    return [
        CalibrationFindingTuple(
            category=finding.category.value,
            location=finding.location,
            description=finding.description,
            severity=finding.severity,
            source_model=source.value,
            raw_finding=None,
        )
        for source in finding.sources
    ]


def serialize_external_finding(
    finding: ReviewFindingObserved,
) -> CalibrationFindingTuple:
    """Convert an external ReviewFindingObserved to CalibrationFindingTuple.

    Extracts category from rule_id (format ai-reviewer:{model}:{category}).
    Uses normalized_message for description, file_path for location.

    Args:
        finding: External review finding from CI/linter/AI reviewer.

    Returns:
        CalibrationFindingTuple with source_model extracted from rule_id.

    Raises:
        ValueError: If rule_id has ai-reviewer prefix but missing model.
    """
    category = _extract_category(finding.rule_id)
    source_model = _extract_source_model(finding.rule_id)

    return CalibrationFindingTuple(
        category=category,
        location=finding.file_path,
        description=finding.normalized_message,
        severity=finding.severity.value,
        source_model=source_model,
        finding_id=finding.finding_id,
        raw_finding=finding,
    )


def _extract_category(rule_id: str) -> str:
    """Extract category from rule_id.

    Expected format: ai-reviewer:{model}:{category}
    Falls back to 'unknown' for unrecognized formats.
    """
    parts = rule_id.split(":")
    if len(parts) >= 3 and parts[0] == "ai-reviewer":
        return parts[2]
    if len(parts) >= 2:
        return parts[1]
    return "unknown"


def _extract_source_model(rule_id: str) -> str:
    """Extract source model from rule_id.

    Expected format: ai-reviewer:{model}:{category}

    Raises:
        ValueError: If rule_id has ai-reviewer prefix but no model component.
    """
    parts = rule_id.split(":")
    if len(parts) >= 2 and parts[0] == "ai-reviewer":
        if not parts[1]:
            raise ValueError(
                f"rule_id '{rule_id}' has ai-reviewer prefix but missing model"
            )
        return parts[1]
    return rule_id.split(":")[0] if ":" in rule_id else rule_id
