# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output models for Plan Reviewer Compute Node."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EnumPlanReviewCategory(str, Enum):
    """Six adversarial review categories for implementation plans."""

    R1 = "R1"  # Count Integrity
    R2 = "R2"  # Acceptance Criteria Strength
    R3 = "R3"  # Scope Violations
    R4 = "R4"  # Integration Traps
    R5 = "R5"  # Idempotency
    R6 = "R6"  # Verification Soundness


class EnumPlanReviewSeverity(str, Enum):
    """Severity of a plan review finding."""

    BLOCK = "BLOCK"  # Plan should not proceed without fixing
    WARN = "WARN"  # Fix recommended, not required


class PlanReviewFinding(BaseModel):
    """A single finding produced by one adversarial review category."""

    category: EnumPlanReviewCategory = Field(
        ...,
        description="Which review category produced this finding.",
    )
    severity: EnumPlanReviewSeverity = Field(
        ...,
        description="Whether this finding blocks plan execution (BLOCK) or is advisory (WARN).",
    )
    issue: str = Field(
        ...,
        min_length=1,
        description="Description of the problem found.",
    )
    fix_description: str = Field(
        ...,
        min_length=1,
        description="Concrete description of what the fix should do.",
    )
    location: str | None = Field(
        default=None,
        description="Task name, section header, or line range where the issue was found.",
    )

    model_config = {"frozen": True, "extra": "forbid"}


class PlanReviewPatch(BaseModel):
    """A text patch generated to fix a specific finding.

    Callers apply patches by verifying before_snippet_hash matches the
    SHA-256 of the original before_snippet, then replacing before_snippet
    with after_snippet at the indicated location.
    """

    location: str = Field(
        ...,
        min_length=1,
        description="Section header or line range pointer indicating where the patch applies.",
    )
    before_snippet_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 hex digest of before_snippet for integrity verification.",
    )
    before_snippet: str = Field(
        ...,
        min_length=1,
        description="Original text snippet to be replaced.",
    )
    after_snippet: str = Field(
        ...,
        min_length=1,
        description="Replacement text snippet.",
    )
    finding_ref: EnumPlanReviewCategory = Field(
        ...,
        description="Which finding category generated this patch.",
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelPlanReviewerComputeOutput(BaseModel):
    """Output model for plan review operations.

    Primary artifact: patches list. Each patch contains before/after snippets
    and a SHA-256 hash of the original for integrity. Callers should apply
    patches to reconstruct the revised plan rather than using plan_text_revised
    directly, to preserve auditability.
    """

    findings: list[PlanReviewFinding] = Field(
        default_factory=list,
        description="All findings produced by the adversarial review.",
    )
    patches: list[PlanReviewPatch] = Field(
        default_factory=list,
        description="Primary artifact. Text patches generated to fix findings.",
    )
    plan_text_revised: str | None = Field(
        default=None,
        description=(
            "Convenience field: plan text with all patches applied. "
            "Not the primary artifact — use patches for auditable application."
        ),
    )
    categories_clean: list[EnumPlanReviewCategory] = Field(
        default_factory=list,
        description="Review categories that produced no findings.",
    )
    categories_with_findings: list[EnumPlanReviewCategory] = Field(
        default_factory=list,
        description="Review categories that produced at least one finding.",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "EnumPlanReviewCategory",
    "EnumPlanReviewSeverity",
    "PlanReviewFinding",
    "PlanReviewPatch",
    "ModelPlanReviewerComputeOutput",
]
