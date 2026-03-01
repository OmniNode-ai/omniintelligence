# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Plan review finding models for NodePlanReviewerMultiCompute.

Defines the per-model finding type (``PlanReviewFinding``) and the
merged finding type with confidence scoring
(``PlanReviewFindingWithConfidence``).

Ticket: OMN-3288
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_plan_review_category import (
    EnumPlanReviewCategory,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)


class EnumFindingSeverity(str):
    """Finding severity values.

    Using plain constants instead of an Enum so that string literals
    produced by LLM output parsing (``"BLOCK"``, ``"WARN"``) compare
    equal without an explicit conversion step.

    Attributes:
        BLOCK: Blocking finding — must be fixed before the plan is accepted.
        WARN: Warning finding — should be addressed but does not block.
    """

    BLOCK = "BLOCK"
    WARN = "WARN"


SEVERITY_BLOCK = "BLOCK"
SEVERITY_WARN = "WARN"
_VALID_SEVERITIES = frozenset({"BLOCK", "WARN"})


class PlanReviewFinding(BaseModel):
    """A single finding produced by one LLM model during plan review.

    Findings are immutable after creation.  They flow from a strategy
    handler's per-model call into the merge/vote logic that produces
    ``PlanReviewFindingWithConfidence`` items in the final output.

    Attributes:
        finding_id: Unique identifier for this finding (UUID4).
        category: Review category (R1-R6) this finding belongs to.
        location: Free-text location descriptor (e.g. ``"Step 3"``,
            ``"Acceptance criteria bullet 2"``).
        location_normalized: Lower-cased, whitespace-stripped ``location``
            used for deduplication in S4 independent_merge.
        severity: ``"BLOCK"`` or ``"WARN"``.
        description: Human-readable description of the issue.
        suggested_fix: Human-readable suggestion for how to resolve it.
        patch: Optional raw text patch / diff for auto-remediation.
        source_model: The model that produced this finding.

    Example::

        finding = PlanReviewFinding(
            category=EnumPlanReviewCategory.R1_COUNTS,
            location="Step 3",
            severity="BLOCK",
            description="Step 3 lists 4 sub-tasks but the summary says 3.",
            suggested_fix="Update the summary count to 4.",
            source_model=EnumReviewModel.QWEN3_CODER,
        )
    """

    model_config = {"frozen": True, "extra": "ignore"}

    finding_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this finding.",
    )
    category: EnumPlanReviewCategory = Field(
        description="Review category (R1-R6).",
    )
    location: str = Field(
        description="Free-text location descriptor.",
        min_length=1,
    )
    location_normalized: str = Field(
        description="Normalised location used for deduplication (lower-cased, stripped).",
        min_length=1,
    )
    severity: str = Field(
        description='Finding severity: "BLOCK" or "WARN".',
    )
    description: str = Field(
        description="Human-readable description of the issue.",
        min_length=1,
    )
    suggested_fix: str = Field(
        description="Human-readable suggestion for resolving the issue.",
        min_length=1,
    )
    patch: str | None = Field(
        default=None,
        description="Optional raw text patch / diff for auto-remediation.",
    )
    source_model: EnumReviewModel = Field(
        description="The model that produced this finding.",
    )

    @classmethod
    def create(
        cls,
        *,
        category: EnumPlanReviewCategory,
        location: str,
        severity: str,
        description: str,
        suggested_fix: str,
        source_model: EnumReviewModel,
        patch: str | None = None,
    ) -> PlanReviewFinding:
        """Construct a finding, auto-computing ``location_normalized``.

        Args:
            category: Review category.
            location: Raw location descriptor from the LLM.
            severity: ``"BLOCK"`` or ``"WARN"``.
            description: Issue description.
            suggested_fix: Suggested resolution.
            source_model: Model that raised this finding.
            patch: Optional patch text.

        Returns:
            A new frozen ``PlanReviewFinding``.
        """
        return cls(
            category=category,
            location=location,
            location_normalized=location.strip().lower(),
            severity=severity,
            description=description,
            suggested_fix=suggested_fix,
            source_model=source_model,
            patch=patch,
        )


class PlanReviewFindingWithConfidence(BaseModel):
    """A merged finding with aggregate confidence and source list.

    Produced by strategy handlers after the per-model findings are
    combined via voting, merging, or sequential critique.

    Attributes:
        finding_id: Unique identifier for this merged finding.
        category: Review category (R1-R6).
        location: Location descriptor (from the primary source finding).
        location_normalized: Normalised location for deduplication.
        severity: ``"BLOCK"`` (if any source says BLOCK) or ``"WARN"``.
        description: Issue description.
        suggested_fix: Suggested resolution.
        patch: Optional patch from the highest-accuracy source model.
        confidence: Aggregate confidence in range [0.0, 1.0].
        sources: List of models that raised this finding.

    Example::

        merged = PlanReviewFindingWithConfidence(
            category=EnumPlanReviewCategory.R1_COUNTS,
            location="Step 3",
            location_normalized="step 3",
            severity="BLOCK",
            description="Step count mismatch.",
            suggested_fix="Fix the count.",
            confidence=0.75,
            sources=[EnumReviewModel.QWEN3_CODER, EnumReviewModel.DEEPSEEK_R1],
        )
    """

    model_config = {"frozen": True, "extra": "ignore"}

    finding_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this merged finding.",
    )
    category: EnumPlanReviewCategory = Field(
        description="Review category (R1-R6).",
    )
    location: str = Field(
        description="Location descriptor.",
        min_length=1,
    )
    location_normalized: str = Field(
        description="Normalised location for deduplication.",
        min_length=1,
    )
    severity: str = Field(
        description='Severity: "BLOCK" or "WARN".',
    )
    description: str = Field(
        description="Human-readable description of the issue.",
        min_length=1,
    )
    suggested_fix: str = Field(
        description="Human-readable suggestion.",
        min_length=1,
    )
    patch: str | None = Field(
        default=None,
        description="Optional patch from highest-accuracy source model.",
    )
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Aggregate confidence in [0.0, 1.0].",
    )
    sources: list[EnumReviewModel] = Field(
        description="Models that raised this finding.",
        min_length=1,
    )


__all__ = [
    "SEVERITY_BLOCK",
    "SEVERITY_WARN",
    "EnumFindingSeverity",
    "PlanReviewFinding",
    "PlanReviewFindingWithConfidence",
]
