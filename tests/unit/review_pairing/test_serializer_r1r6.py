# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for R1-R6 and external finding serializers.

Reference: OMN-6166 (epic OMN-6164)
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

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
    def test_basic_serialization(self) -> None:
        finding = PlanReviewFinding.create(
            category=EnumPlanReviewCategory.R1_COUNTS,
            location="Step 3",
            severity="BLOCK",
            description="Step count mismatch",
            suggested_fix="Update count",
            source_model=EnumReviewModel.QWEN3_CODER,
        )
        result = serialize_plan_finding(finding, "qwen3-coder")
        assert result.category == EnumPlanReviewCategory.R1_COUNTS.value
        assert result.location == "Step 3"
        assert result.description == "Step count mismatch"
        assert result.severity == "BLOCK"
        assert result.source_model == "qwen3-coder"
        assert result.finding_id == finding.finding_id
        assert result.raw_finding is None

    def test_preserves_finding_id(self) -> None:
        finding = PlanReviewFinding.create(
            category=EnumPlanReviewCategory.R3_SCOPE,
            location="Task 1",
            severity="WARN",
            description="Scope unclear",
            suggested_fix="Clarify scope",
            source_model=EnumReviewModel.DEEPSEEK_R1,
        )
        result = serialize_plan_finding(finding, "deepseek-r1")
        assert result.finding_id == finding.finding_id


@pytest.mark.unit
class TestSerializeMergedFinding:
    def test_explodes_to_per_model(self) -> None:
        finding = PlanReviewFindingWithConfidence(
            category=EnumPlanReviewCategory.R1_COUNTS,
            location="Step 3",
            location_normalized="step 3",
            severity="BLOCK",
            description="Step count mismatch",
            suggested_fix="Fix count",
            confidence=0.75,
            sources=[EnumReviewModel.QWEN3_CODER, EnumReviewModel.DEEPSEEK_R1],
        )
        results = serialize_merged_finding(finding)
        assert len(results) == 2
        assert results[0].source_model == EnumReviewModel.QWEN3_CODER.value
        assert results[1].source_model == EnumReviewModel.DEEPSEEK_R1.value

    def test_single_source(self) -> None:
        finding = PlanReviewFindingWithConfidence(
            category=EnumPlanReviewCategory.R6_VERIFICATION,
            location="Task 5",
            location_normalized="task 5",
            severity="WARN",
            description="No tests specified",
            suggested_fix="Add test plan",
            confidence=0.5,
            sources=[EnumReviewModel.DEEPSEEK_R1],
        )
        results = serialize_merged_finding(finding)
        assert len(results) == 1


@pytest.mark.unit
class TestSerializeExternalFinding:
    def _make_finding(
        self,
        rule_id: str = "ai-reviewer:codex:architecture",
    ) -> ReviewFindingObserved:
        return ReviewFindingObserved(
            finding_id=uuid4(),
            repo="OmniNode-ai/omniintelligence",
            pr_id=1,
            rule_id=rule_id,
            severity=FindingSeverity.ERROR,
            file_path="src/main.py",
            line_start=10,
            line_end=20,
            tool_name="ai-reviewer",
            tool_version="1.0",
            normalized_message="Missing error handling in retry logic",
            raw_message="Missing error handling",
            commit_sha_observed="abc1234",
            observed_at=datetime.now(timezone.utc),
        )

    def test_codex_finding(self) -> None:
        finding = self._make_finding("ai-reviewer:codex:architecture")
        result = serialize_external_finding(finding)
        assert result.category == "architecture"
        assert result.source_model == "codex"
        assert result.location == "src/main.py"
        assert result.description == "Missing error handling in retry logic"
        assert result.severity == "error"
        assert result.finding_id == finding.finding_id
        assert result.raw_finding is finding

    def test_deepseek_finding(self) -> None:
        finding = self._make_finding("ai-reviewer:deepseek-r1:performance")
        result = serialize_external_finding(finding)
        assert result.category == "performance"
        assert result.source_model == "deepseek-r1"

    def test_unknown_format_defaults(self) -> None:
        finding = self._make_finding("ruff:E501")
        result = serialize_external_finding(finding)
        assert result.category == "E501"
        assert result.source_model == "ruff"

    def test_single_token_rule_id(self) -> None:
        finding = self._make_finding("unknown-tool")
        result = serialize_external_finding(finding)
        assert result.category == "unknown"
        assert result.source_model == "unknown-tool"

    def test_missing_model_raises(self) -> None:
        finding = self._make_finding("ai-reviewer::category")
        with pytest.raises(ValueError, match="missing model"):
            serialize_external_finding(finding)
