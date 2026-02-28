# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Integration tests for NodePlanReviewerCompute.

These tests make real LLM calls against the known-bad smoke plan from the
writing-plans skill adversarial review specification. They verify that the
node correctly identifies R1, R2, R3, R4, R6 and returns structured patches.

Run with:
    pytest tests/integration/nodes/node_plan_reviewer_compute/ -v -m integration

Requirements:
    - LLM_CODER_URL must be reachable (or set in environment)
    - Tests are skipped if LLM is unavailable
"""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.integration

from omniintelligence.nodes.node_plan_reviewer_compute.models import (
    EnumPlanReviewCategory,
    EnumPlanReviewSeverity,
    ModelPlanReviewerComputeCommand,
    ModelPlanReviewerComputeOutput,
)
from omniintelligence.nodes.node_plan_reviewer_compute.node import (
    NodePlanReviewerCompute,
)

# ---------------------------------------------------------------------------
# Known-bad smoke plan from writing-plans/SKILL.md specification
# ---------------------------------------------------------------------------

_SMOKE_PLAN = """\
# Smoke Test Plan

This plan creates **4 tickets** (Tickets 1, 2, 3, 4a, 4b).

## Ticket 1: Setup
Acceptance criteria: setup complete.
Verification: pytest passes.

## Ticket 2: DB-only migration
Acceptance criteria: kill switch enforced via FEATURE_FLAG env var check
in Python handler.
Verification: pytest passes.
Contract module: omnibase_infra.nodes.foo.models.

## Ticket 3: Tests
No mention of models/__init__.py.
Verification: pytest passes.

## Ticket 4a: Docs
No acceptance criteria.

## Ticket 4b: Cleanup
No acceptance criteria.
"""

# Expected: R1, R2, R3, R4, R6 are caught. R5 is clean.
_EXPECTED_CAUGHT = {
    EnumPlanReviewCategory.R1,
    EnumPlanReviewCategory.R2,
    EnumPlanReviewCategory.R3,
    EnumPlanReviewCategory.R4,
    EnumPlanReviewCategory.R6,
}


def _llm_reachable() -> bool:
    llm_url = os.getenv("LLM_CODER_URL", "http://192.168.86.201:8000")
    try:
        httpx.get(f"{llm_url}/health", timeout=3.0)
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def review_output() -> ModelPlanReviewerComputeOutput:
    """Run the node once and share the result across tests in this module."""
    if not _llm_reachable():
        pytest.skip("LLM_CODER_URL not reachable — skipping integration tests")

    cmd = ModelPlanReviewerComputeCommand(plan_text=_SMOKE_PLAN)
    node = NodePlanReviewerCompute(container=None)  # type: ignore[arg-type]
    import asyncio

    return asyncio.run(node.compute(cmd))


class TestSmokeplanCategoryDetection:
    """Verify all expected categories are caught on the known-bad smoke plan."""

    def test_r1_caught(self, review_output: ModelPlanReviewerComputeOutput) -> None:
        """R1: '4 tickets' but 5 identifiers listed."""
        caught = {f.category for f in review_output.findings}
        assert EnumPlanReviewCategory.R1 in caught, (
            f"R1 not found in findings. Found categories: {caught}"
        )

    def test_r2_caught(self, review_output: ModelPlanReviewerComputeOutput) -> None:
        """R2: 'pytest passes' is weak and vague."""
        caught = {f.category for f in review_output.findings}
        assert EnumPlanReviewCategory.R2 in caught, (
            f"R2 not found in findings. Found categories: {caught}"
        )

    def test_r3_caught(self, review_output: ModelPlanReviewerComputeOutput) -> None:
        """R3: DB-only Ticket 2 claims Python runtime behavior."""
        caught = {f.category for f in review_output.findings}
        assert EnumPlanReviewCategory.R3 in caught, (
            f"R3 not found in findings. Found categories: {caught}"
        )

    def test_r4_caught(self, review_output: ModelPlanReviewerComputeOutput) -> None:
        """R4: Contract module path unverified, no re-export step."""
        caught = {f.category for f in review_output.findings}
        assert EnumPlanReviewCategory.R4 in caught, (
            f"R4 not found in findings. Found categories: {caught}"
        )

    def test_r6_caught(self, review_output: ModelPlanReviewerComputeOutput) -> None:
        """R6: 'pytest passes' is weak-only proof for a DB migration."""
        caught = {f.category for f in review_output.findings}
        assert EnumPlanReviewCategory.R6 in caught, (
            f"R6 not found in findings. Found categories: {caught}"
        )


class TestSmokeplanOutputShape:
    """Verify the output model shape and patch integrity."""

    def test_output_is_typed(
        self, review_output: ModelPlanReviewerComputeOutput
    ) -> None:
        assert isinstance(review_output, ModelPlanReviewerComputeOutput)

    def test_patches_non_empty_for_findings(
        self, review_output: ModelPlanReviewerComputeOutput
    ) -> None:
        if review_output.findings:
            # At least some findings should have patches
            assert len(review_output.patches) > 0, (
                "Findings were returned but no patches produced"
            )

    def test_patches_have_valid_hashes(
        self, review_output: ModelPlanReviewerComputeOutput
    ) -> None:
        import hashlib

        for patch in review_output.patches:
            expected = hashlib.sha256(patch.before_snippet.encode()).hexdigest()
            assert patch.before_snippet_hash == expected, (
                f"Hash mismatch for patch at {patch.location!r}"
            )

    def test_findings_have_block_or_warn_severity(
        self, review_output: ModelPlanReviewerComputeOutput
    ) -> None:
        for finding in review_output.findings:
            assert finding.severity in {
                EnumPlanReviewSeverity.BLOCK,
                EnumPlanReviewSeverity.WARN,
            }

    def test_categories_not_in_both_lists(
        self, review_output: ModelPlanReviewerComputeOutput
    ) -> None:
        clean_set = set(review_output.categories_clean)
        dirty_set = set(review_output.categories_with_findings)
        overlap = clean_set & dirty_set
        assert not overlap, f"Categories appear in both clean and dirty: {overlap}"

    def test_plan_text_revised_applies_patches(
        self, review_output: ModelPlanReviewerComputeOutput
    ) -> None:
        if review_output.plan_text_revised and review_output.patches:
            # Verify none of the before_snippets survive verbatim in the revised plan
            for patch in review_output.patches:
                if patch.before_snippet in _SMOKE_PLAN:
                    # Only check snippets that were actually in the original
                    assert (
                        patch.after_snippet in review_output.plan_text_revised
                        or patch.before_snippet not in review_output.plan_text_revised
                    ), f"Patch at {patch.location!r} appears unapplied in revised plan"
