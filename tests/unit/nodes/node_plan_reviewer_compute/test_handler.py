# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the plan reviewer compute handler.

Tests the handler with a mocked LLM client — no real LLM calls.
"""

from __future__ import annotations

import hashlib
from typing import Any
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_plan_reviewer_compute.handlers.handler_plan_reviewer_compute import (
    _apply_patches,
    _parse_findings,
    _parse_patches,
    _sha256_hex,
    handle_plan_reviewer_compute,
)
from omniintelligence.nodes.node_plan_reviewer_compute.models import (
    EnumPlanReviewCategory,
    EnumPlanReviewSeverity,
    ModelPlanReviewerComputeCommand,
    ModelPlanReviewerComputeOutput,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GOOD_LLM_RESPONSE: dict[str, Any] = {
    "findings": [
        {
            "category": "R1",
            "severity": "BLOCK",
            "issue": "Says 4 tickets but lists 5 identifiers (1, 2, 3, 4a, 4b).",
            "fix_description": 'Change "4 tickets" to "5 tickets".',
            "location": "Introduction",
        }
    ],
    "patches": [
        {
            "location": "Introduction",
            "before_snippet": "This plan has 4 tickets.",
            "after_snippet": "This plan has 5 tickets.",
            "finding_ref": "R1",
        }
    ],
    "categories_clean": ["R2", "R3", "R4", "R5", "R6"],
    "categories_with_findings": ["R1"],
}

_PLAN_WITH_COUNT_ERROR = (
    "# Plan\n\nThis plan has 4 tickets.\n\n"
    "- Ticket 1: setup\n- Ticket 2: migration\n- Ticket 3: tests\n"
    "- Ticket 4a: docs\n- Ticket 4b: cleanup"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestSha256Hex:
    def test_known_value(self) -> None:
        text = "hello"
        expected = hashlib.sha256(b"hello").hexdigest()
        assert _sha256_hex(text) == expected

    def test_returns_64_chars(self) -> None:
        assert len(_sha256_hex("anything")) == 64


class TestParseFindings:
    def test_parses_valid_finding(self) -> None:
        findings = _parse_findings(_GOOD_LLM_RESPONSE["findings"])
        assert len(findings) == 1
        assert findings[0].category == EnumPlanReviewCategory.R1
        assert findings[0].severity == EnumPlanReviewSeverity.BLOCK
        assert findings[0].location == "Introduction"

    def test_skips_malformed_finding(self) -> None:
        raw = [
            {
                "category": "R1",
                "severity": "BLOCK",
                "issue": "ok",
                "fix_description": "fix",
            },
            {
                "category": "INVALID",
                "severity": "BLOCK",
                "issue": "x",
                "fix_description": "y",
            },
        ]
        findings = _parse_findings(raw)
        assert len(findings) == 1
        assert findings[0].category == EnumPlanReviewCategory.R1

    def test_empty_list_returns_empty(self) -> None:
        assert _parse_findings([]) == []


class TestParsePatches:
    def test_parses_valid_patch_and_computes_hash(self) -> None:
        raw = _GOOD_LLM_RESPONSE["patches"]
        patches = _parse_patches(raw)
        assert len(patches) == 1
        expected_hash = _sha256_hex("This plan has 4 tickets.")
        assert patches[0].before_snippet_hash == expected_hash
        assert patches[0].finding_ref == EnumPlanReviewCategory.R1

    def test_skips_patch_with_invalid_category(self) -> None:
        raw = [
            {
                "location": "x",
                "before_snippet": "old",
                "after_snippet": "new",
                "finding_ref": "NOT_REAL",
            }
        ]
        patches = _parse_patches(raw)
        assert patches == []


class TestApplyPatches:
    def test_applies_single_patch(self) -> None:
        plan = "This plan has 4 tickets.\nMore text."
        before = "This plan has 4 tickets."
        patches = _parse_patches(
            [
                {
                    "location": "intro",
                    "before_snippet": before,
                    "after_snippet": "This plan has 5 tickets.",
                    "finding_ref": "R1",
                }
            ]
        )
        result = _apply_patches(plan, patches)
        assert "5 tickets" in result
        assert "4 tickets" not in result

    def test_skips_patch_when_snippet_not_found(self) -> None:
        plan = "Different text entirely."
        patches = _parse_patches(
            [
                {
                    "location": "intro",
                    "before_snippet": "This plan has 4 tickets.",
                    "after_snippet": "This plan has 5 tickets.",
                    "finding_ref": "R1",
                }
            ]
        )
        result = _apply_patches(plan, patches)
        assert result == plan  # unchanged

    def test_applies_multiple_patches_sequentially(self) -> None:
        plan = "Count: 4 tickets. Status: passes tests."
        patches = _parse_patches(
            [
                {
                    "location": "count",
                    "before_snippet": "4 tickets",
                    "after_snippet": "5 tickets",
                    "finding_ref": "R1",
                },
                {
                    "location": "status",
                    "before_snippet": "passes tests",
                    "after_snippet": "exactly 3 tests pass asserting migration schema",
                    "finding_ref": "R2",
                },
            ]
        )
        result = _apply_patches(plan, patches)
        assert "5 tickets" in result
        assert "exactly 3 tests pass" in result


# ---------------------------------------------------------------------------
# Handler integration (mocked LLM)
# ---------------------------------------------------------------------------


class TestHandlePlanReviewerCompute:
    def _run(
        self,
        plan_text: str,
        mock_response: dict[str, Any] | None = None,
        llm_raises: Exception | None = None,
    ) -> ModelPlanReviewerComputeOutput:
        cmd = ModelPlanReviewerComputeCommand(plan_text=plan_text)
        response = mock_response or _GOOD_LLM_RESPONSE

        async def fake_llm(**_kwargs: object) -> dict[str, Any]:
            if llm_raises:
                raise llm_raises
            return response

        with patch(
            "omniintelligence.nodes.node_plan_reviewer_compute.handlers"
            ".handler_plan_reviewer_compute.call_plan_reviewer_llm",
            new=fake_llm,
        ):
            return handle_plan_reviewer_compute(cmd)

    def test_returns_typed_output(self) -> None:
        out = self._run(_PLAN_WITH_COUNT_ERROR)
        assert isinstance(out, ModelPlanReviewerComputeOutput)

    def test_findings_are_typed(self) -> None:
        out = self._run(_PLAN_WITH_COUNT_ERROR)
        assert len(out.findings) == 1
        assert out.findings[0].category == EnumPlanReviewCategory.R1
        assert out.findings[0].severity == EnumPlanReviewSeverity.BLOCK

    def test_patches_have_computed_hash(self) -> None:
        out = self._run(_PLAN_WITH_COUNT_ERROR)
        assert len(out.patches) == 1
        expected_hash = _sha256_hex("This plan has 4 tickets.")
        assert out.patches[0].before_snippet_hash == expected_hash

    def test_plan_text_revised_populated_when_patch_applies(self) -> None:
        out = self._run(_PLAN_WITH_COUNT_ERROR)
        assert out.plan_text_revised is not None
        assert "5 tickets" in out.plan_text_revised

    def test_categories_with_findings(self) -> None:
        out = self._run(_PLAN_WITH_COUNT_ERROR)
        assert EnumPlanReviewCategory.R1 in out.categories_with_findings

    def test_categories_clean(self) -> None:
        out = self._run(_PLAN_WITH_COUNT_ERROR)
        assert EnumPlanReviewCategory.R2 in out.categories_clean

    def test_llm_failure_returns_block_finding(self) -> None:
        out = self._run(
            "any plan",
            llm_raises=ConnectionError("connection refused"),
        )
        assert len(out.findings) == 1
        assert out.findings[0].severity == EnumPlanReviewSeverity.BLOCK
        assert "connection refused" in out.findings[0].issue

    def test_empty_findings_when_all_clean(self) -> None:
        clean_response: dict[str, Any] = {
            "findings": [],
            "patches": [],
            "categories_clean": ["R1", "R2", "R3", "R4", "R5", "R6"],
            "categories_with_findings": [],
        }
        out = self._run("A perfect plan.", mock_response=clean_response)
        assert out.findings == []
        assert out.patches == []
        assert out.plan_text_revised is None
        assert set(out.categories_clean) == set(EnumPlanReviewCategory)

    def test_all_enum_categories_covered_in_tests(self) -> None:
        """Ensure test coverage for every category value — regression guard."""
        covered = {
            EnumPlanReviewCategory.R1,
            EnumPlanReviewCategory.R2,
            EnumPlanReviewCategory.R3,
            EnumPlanReviewCategory.R4,
            EnumPlanReviewCategory.R5,
            EnumPlanReviewCategory.R6,
        }
        assert covered == set(EnumPlanReviewCategory)
