# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for R1-R6 finding serializer.

TDD: Tests written first for OMN-6166.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_plan_reviewer_multi_compute.models import (
    EnumPlanReviewCategory,
    EnumReviewModel,
    PlanReviewFinding,
    PlanReviewFindingWithConfidence,
)
from omniintelligence.review_pairing.models import (
    FindingSeverity,
    ReviewFindingObserved,
)
from omniintelligence.review_pairing.serializer_r1r6 import (
    serialize_external_finding,
    serialize_merged_finding,
    serialize_plan_finding,
)


@pytest.mark.unit
class TestSerializePlanFinding:
    """Tests for serialize_plan_finding."""

    def test_basic_conversion(self) -> None:
        finding = PlanReviewFinding.create(
            category=EnumPlanReviewCategory.R1_COUNTS,
            location="Step 3",
            severity="BLOCK",
            description="Step count mismatch.",
            suggested_fix="Fix the count.",
            source_model=EnumReviewModel.QWEN3_CODER,
        )
        result = serialize_plan_finding(finding, "qwen3-coder")
        assert result.category == "R1_counts"
        assert result.location == "Step 3"
        assert result.description == "Step count mismatch."
        assert result.severity == "BLOCK"
        assert result.source_model == "qwen3-coder"
        assert result.raw_finding is None

    def test_all_categories_map(self) -> None:
        for cat in EnumPlanReviewCategory:
            finding = PlanReviewFinding.create(
                category=cat,
                location="Test",
                severity="WARN",
                description="Test description",
                suggested_fix="Fix it",
                source_model=EnumReviewModel.DEEPSEEK_R1,
            )
            result = serialize_plan_finding(finding, "deepseek-r1")
            assert result.category == cat.value

    def test_finding_id_is_uuid(self) -> None:
        finding = PlanReviewFinding.create(
            category=EnumPlanReviewCategory.R3_SCOPE,
            location="Step 1",
            severity="WARN",
            description="Scope unclear",
            suggested_fix="Clarify scope",
            source_model=EnumReviewModel.QWEN3_CODER,
        )
        result = serialize_plan_finding(finding, "qwen3-coder")
        assert result.finding_id is not None


@pytest.mark.unit
class TestSerializeExternalFinding:
    """Tests for serialize_external_finding."""

    def test_codex_rule_id(self) -> None:
        finding = ReviewFindingObserved(
            finding_id=uuid4(),
            repo="OmniNode-ai/omniintelligence",
            pr_id=100,
            rule_id="ai-reviewer:codex:architecture",
            severity=FindingSeverity.ERROR,
            file_path="src/main.py",
            line_start=42,
            tool_name="ai-reviewer",
            tool_version="1.0",
            normalized_message="Missing error handling in API endpoint",
            raw_message="Missing error handling",
            commit_sha_observed="abc1234",
            observed_at=datetime.now(tz=timezone.utc),
        )
        result = serialize_external_finding(finding)
        assert result.category == "architecture"
        assert result.location == "src/main.py"
        assert result.description == "Missing error handling in API endpoint"
        assert result.severity == "error"
        assert result.source_model == "codex"
        assert result.raw_finding == finding

    def test_unknown_rule_id_format(self) -> None:
        finding = ReviewFindingObserved(
            finding_id=uuid4(),
            repo="OmniNode-ai/omniintelligence",
            pr_id=100,
            rule_id="ruff:E501",
            severity=FindingSeverity.WARNING,
            file_path="src/main.py",
            line_start=10,
            tool_name="ruff",
            tool_version="0.4.0",
            normalized_message="Line too long",
            raw_message="Line too long (120 > 88)",
            commit_sha_observed="def5678",
            observed_at=datetime.now(tz=timezone.utc),
        )
        result = serialize_external_finding(finding)
        assert result.category == "unknown"
        assert result.source_model == "ruff"

    def test_preserves_finding_id(self) -> None:
        fid = uuid4()
        finding = ReviewFindingObserved(
            finding_id=fid,
            repo="OmniNode-ai/omniintelligence",
            pr_id=100,
            rule_id="ai-reviewer:codex:security",
            severity=FindingSeverity.ERROR,
            file_path="src/auth.py",
            line_start=1,
            tool_name="ai-reviewer",
            tool_version="1.0",
            normalized_message="SQL injection risk",
            raw_message="SQL injection",
            commit_sha_observed="aaa1111",
            observed_at=datetime.now(tz=timezone.utc),
        )
        result = serialize_external_finding(finding)
        assert result.finding_id == fid


@pytest.mark.unit
class TestSerializeMergedFinding:
    """Tests for serialize_merged_finding."""

    def test_explodes_to_per_source(self) -> None:
        finding = PlanReviewFindingWithConfidence(
            category=EnumPlanReviewCategory.R4_INTEGRATION_TRAPS,
            location="Step 5",
            location_normalized="step 5",
            severity="BLOCK",
            description="Integration risk",
            suggested_fix="Add integration test",
            confidence=0.8,
            sources=[EnumReviewModel.QWEN3_CODER, EnumReviewModel.DEEPSEEK_R1],
        )
        results = serialize_merged_finding(finding)
        assert len(results) == 2
        assert results[0].source_model == EnumReviewModel.QWEN3_CODER.value
        assert results[1].source_model == EnumReviewModel.DEEPSEEK_R1.value
        assert results[0].category == "R4_integration_traps"
        assert results[0].description == "Integration risk"

    def test_single_source(self) -> None:
        finding = PlanReviewFindingWithConfidence(
            category=EnumPlanReviewCategory.R2_ACCEPTANCE_CRITERIA,
            location="Step 1",
            location_normalized="step 1",
            severity="WARN",
            description="Missing acceptance criteria",
            suggested_fix="Add criteria",
            confidence=0.6,
            sources=[EnumReviewModel.QWEN3_CODER],
        )
        results = serialize_merged_finding(finding)
        assert len(results) == 1
        assert results[0].source_model == EnumReviewModel.QWEN3_CODER.value
