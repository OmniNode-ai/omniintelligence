# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for S3 sequential_critique strategy handler.

All LLM calls are mocked.  Network I/O is never performed.

Ticket: OMN-3288
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.strategies.handler_sequential_critique import (
    _CRITIC,
    _DRAFTER,
    handle_sequential_critique,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_plan_review_category import (
    EnumPlanReviewCategory,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_review_finding import (
    SEVERITY_WARN,
    PlanReviewFinding,
)

_PLAN = "Sample plan text for testing."
_CATEGORIES = list(EnumPlanReviewCategory)
_EQUAL_WEIGHTS: dict[EnumReviewModel, float] = {
    EnumReviewModel.QWEN3_CODER: 0.5,
    EnumReviewModel.DEEPSEEK_R1: 0.5,
}


def _make_finding(
    *,
    category: EnumPlanReviewCategory = EnumPlanReviewCategory.R1_COUNTS,
    location: str = "Step 1",
    severity: str = SEVERITY_WARN,
    source_model: EnumReviewModel = EnumReviewModel.QWEN3_CODER,
) -> PlanReviewFinding:
    return PlanReviewFinding.create(
        category=category,
        location=location,
        severity=severity,
        description="Test finding.",
        suggested_fix="Fix it.",
        source_model=source_model,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rejected_finding_absent_from_output() -> None:
    """A finding marked rejected by the critic must NOT appear in output."""
    drafter_finding = _make_finding(source_model=_DRAFTER)
    drafter_mock = AsyncMock(return_value=[drafter_finding])
    # Critic rejects the drafter's finding.
    critic_mock = AsyncMock(
        return_value={
            "confirmed": [],
            "rejected": [drafter_finding.finding_id],
            "added": [],
        }
    )

    result = await handle_sequential_critique(
        _PLAN,
        _CATEGORIES,
        drafter_mock,
        critic_mock,
        _EQUAL_WEIGHTS,
    )

    assert result == [], "Rejected finding should not appear in output"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_confirmed_finding_present_in_output() -> None:
    """A finding confirmed by the critic IS in the output."""
    drafter_finding = _make_finding(source_model=_DRAFTER)
    drafter_mock = AsyncMock(return_value=[drafter_finding])
    critic_mock = AsyncMock(
        return_value={
            "confirmed": [drafter_finding.finding_id],
            "rejected": [],
            "added": [],
        }
    )

    result = await handle_sequential_critique(
        _PLAN,
        _CATEGORIES,
        drafter_mock,
        critic_mock,
        _EQUAL_WEIGHTS,
    )

    assert len(result) == 1
    assert result[0].category == drafter_finding.category
    assert _DRAFTER in result[0].sources


@pytest.mark.unit
@pytest.mark.asyncio
async def test_added_finding_present_with_critic_as_source() -> None:
    """A finding in 'added' is in the output with source = critic model."""
    added_finding = _make_finding(
        category=EnumPlanReviewCategory.R4_INTEGRATION_TRAPS,
        source_model=_CRITIC,
    )
    drafter_mock = AsyncMock(return_value=[])
    critic_mock = AsyncMock(
        return_value={
            "confirmed": [],
            "rejected": [],
            "added": [added_finding],
        }
    )

    result = await handle_sequential_critique(
        _PLAN,
        _CATEGORIES,
        drafter_mock,
        critic_mock,
        _EQUAL_WEIGHTS,
    )

    assert len(result) == 1
    assert result[0].category == EnumPlanReviewCategory.R4_INTEGRATION_TRAPS
    assert _CRITIC in result[0].sources


@pytest.mark.unit
@pytest.mark.asyncio
async def test_confirmed_and_added_both_present() -> None:
    """Output = confirmed drafter findings + critic-added findings."""
    drafter_finding = _make_finding(
        category=EnumPlanReviewCategory.R1_COUNTS,
        source_model=_DRAFTER,
    )
    added_finding = _make_finding(
        category=EnumPlanReviewCategory.R6_VERIFICATION,
        source_model=_CRITIC,
    )
    drafter_mock = AsyncMock(return_value=[drafter_finding])
    critic_mock = AsyncMock(
        return_value={
            "confirmed": [drafter_finding.finding_id],
            "rejected": [],
            "added": [added_finding],
        }
    )

    result = await handle_sequential_critique(
        _PLAN,
        _CATEGORIES,
        drafter_mock,
        critic_mock,
        _EQUAL_WEIGHTS,
    )

    assert len(result) == 2
    categories = {f.category for f in result}
    assert EnumPlanReviewCategory.R1_COUNTS in categories
    assert EnumPlanReviewCategory.R6_VERIFICATION in categories


@pytest.mark.unit
@pytest.mark.asyncio
async def test_drafter_failure_returns_empty() -> None:
    """When the drafter fails, output is empty (no findings to confirm)."""

    async def _fail_drafter(
        _plan: str, _cats: list[EnumPlanReviewCategory]
    ) -> list[PlanReviewFinding]:
        raise RuntimeError("drafter down")

    critic_mock = AsyncMock(return_value={"confirmed": [], "rejected": [], "added": []})

    result = await handle_sequential_critique(
        _PLAN,
        _CATEGORIES,
        _fail_drafter,
        critic_mock,
        _EQUAL_WEIGHTS,
    )

    assert result == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_failure_treats_all_drafter_findings_as_confirmed() -> None:
    """When the critic fails, all drafter findings are treated as confirmed."""
    drafter_finding = _make_finding(source_model=_DRAFTER)
    drafter_mock = AsyncMock(return_value=[drafter_finding])

    async def _fail_critic(
        _plan: str, _findings: list[PlanReviewFinding]
    ) -> dict[str, object]:
        raise RuntimeError("critic down")

    result = await handle_sequential_critique(
        _PLAN,
        _CATEGORIES,
        drafter_mock,
        _fail_critic,
        _EQUAL_WEIGHTS,
    )

    assert len(result) == 1
    assert result[0].category == drafter_finding.category


@pytest.mark.unit
def test_drafter_is_qwen3_critic_is_deepseek() -> None:
    """Fixed role assignment: drafter = qwen3-coder, critic = deepseek-r1."""
    assert _DRAFTER == EnumReviewModel.QWEN3_CODER
    assert _CRITIC == EnumReviewModel.DEEPSEEK_R1
