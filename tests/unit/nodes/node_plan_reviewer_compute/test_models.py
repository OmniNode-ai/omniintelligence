# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for Plan Reviewer Compute Node models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_plan_reviewer_compute.models import (
    EnumPlanReviewCategory,
    EnumPlanReviewSeverity,
    ModelPlanReviewerComputeCommand,
    ModelPlanReviewerComputeOutput,
    PlanReviewFinding,
    PlanReviewPatch,
)


class TestEnumPlanReviewCategory:
    """All six enum values must be present and stable."""

    def test_all_six_categories_exist(self) -> None:
        values = {c.value for c in EnumPlanReviewCategory}
        assert values == {"R1", "R2", "R3", "R4", "R5", "R6"}

    def test_category_is_string_subclass(self) -> None:
        assert isinstance(EnumPlanReviewCategory.R1, str)


class TestEnumPlanReviewSeverity:
    def test_block_and_warn_exist(self) -> None:
        assert EnumPlanReviewSeverity.BLOCK.value == "BLOCK"
        assert EnumPlanReviewSeverity.WARN.value == "WARN"


class TestModelPlanReviewerComputeCommand:
    def test_requires_plan_text(self) -> None:
        with pytest.raises(ValidationError):
            ModelPlanReviewerComputeCommand()  # type: ignore[call-arg]

    def test_defaults_to_all_categories(self) -> None:
        cmd = ModelPlanReviewerComputeCommand(plan_text="Task 1: do the thing.")
        assert set(cmd.review_categories) == set(EnumPlanReviewCategory)

    def test_accepts_subset_of_categories(self) -> None:
        cmd = ModelPlanReviewerComputeCommand(
            plan_text="Task 1.",
            review_categories=[EnumPlanReviewCategory.R1, EnumPlanReviewCategory.R3],
        )
        assert cmd.review_categories == [
            EnumPlanReviewCategory.R1,
            EnumPlanReviewCategory.R3,
        ]

    def test_frozen(self) -> None:
        cmd = ModelPlanReviewerComputeCommand(plan_text="Task 1.")
        with pytest.raises(ValidationError):
            cmd.plan_text = "mutated"  # type: ignore[misc]

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            ModelPlanReviewerComputeCommand(plan_text="x", unknown_field="y")  # type: ignore[call-arg]


class TestPlanReviewFinding:
    def test_valid_finding(self) -> None:
        f = PlanReviewFinding(
            category=EnumPlanReviewCategory.R1,
            severity=EnumPlanReviewSeverity.BLOCK,
            issue="Count mismatch: says 4 tickets but lists 5.",
            fix_description='Change "4 tickets" to "5 tickets".',
            location="Introduction",
        )
        assert f.category == EnumPlanReviewCategory.R1
        assert f.severity == EnumPlanReviewSeverity.BLOCK
        assert f.location == "Introduction"

    def test_location_is_optional(self) -> None:
        f = PlanReviewFinding(
            category=EnumPlanReviewCategory.R2,
            severity=EnumPlanReviewSeverity.WARN,
            issue="Vague criterion.",
            fix_description="Replace with testable assertion.",
        )
        assert f.location is None


class TestPlanReviewPatch:
    def test_valid_patch(self) -> None:
        import hashlib

        before = "This plan has 4 tickets."
        before_hash = hashlib.sha256(before.encode()).hexdigest()
        patch = PlanReviewPatch(
            location="Introduction",
            before_snippet_hash=before_hash,
            before_snippet=before,
            after_snippet="This plan has 5 tickets.",
            finding_ref=EnumPlanReviewCategory.R1,
        )
        assert patch.before_snippet_hash == before_hash
        assert len(patch.before_snippet_hash) == 64

    def test_hash_must_be_64_chars(self) -> None:
        with pytest.raises(ValidationError):
            PlanReviewPatch(
                location="x",
                before_snippet_hash="tooshort",
                before_snippet="x",
                after_snippet="y",
                finding_ref=EnumPlanReviewCategory.R1,
            )


class TestModelPlanReviewerComputeOutput:
    def test_empty_output_is_valid(self) -> None:
        out = ModelPlanReviewerComputeOutput()
        assert out.findings == []
        assert out.patches == []
        assert out.plan_text_revised is None
        assert out.categories_clean == []
        assert out.categories_with_findings == []

    def test_plan_text_revised_is_optional(self) -> None:
        out = ModelPlanReviewerComputeOutput(plan_text_revised=None)
        assert out.plan_text_revised is None

    def test_frozen(self) -> None:
        out = ModelPlanReviewerComputeOutput()
        with pytest.raises(ValidationError):
            out.findings = []  # type: ignore[misc]
