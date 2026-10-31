# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for S2 specialist_split strategy handler.

All LLM calls are mocked.  Network I/O is never performed.

Ticket: OMN-3288
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.strategies.handler_specialist_split import (
    _SPECIALIST_MAP,
    HandlerSpecialistSplit,
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
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_strategy_review_request import (
    ModelStrategyReviewRequest,
)

_PLAN = "Sample plan text for testing."
_ALL_CATEGORIES = list(EnumPlanReviewCategory)
_EQUAL_WEIGHTS: dict[EnumReviewModel, float] = {
    EnumReviewModel.CODE_DRAFTER: 0.5,
    EnumReviewModel.DEEP_REASONER: 0.5,
    EnumReviewModel.FAST_REVIEWER: 0.5,
    EnumReviewModel.TIEBREAKER: 0.5,
}


def _make_finding(
    *,
    category: EnumPlanReviewCategory,
    source_model: EnumReviewModel,
    location: str = "Step 1",
    severity: str = SEVERITY_WARN,
) -> PlanReviewFinding:
    return PlanReviewFinding.create(
        category=category,
        location=location,
        severity=severity,
        description="A test finding.",
        suggested_fix="Fix it.",
        source_model=source_model,
    )


def _make_empty_callers() -> dict[EnumReviewModel, AsyncMock]:
    return {m: AsyncMock(return_value=[]) for m in EnumReviewModel}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_r1_category_owned_by_qwen3() -> None:
    """R1 (counts) findings must have sources = [code-drafter]."""
    r1_finding = _make_finding(
        category=EnumPlanReviewCategory.R1_COUNTS,
        source_model=EnumReviewModel.CODE_DRAFTER,
    )
    callers = _make_empty_callers()
    callers[EnumReviewModel.CODE_DRAFTER] = AsyncMock(return_value=[r1_finding])

    result = await HandlerSpecialistSplit().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=_ALL_CATEGORIES,
            callers=callers,
            weights=_EQUAL_WEIGHTS,
        )
    )

    r1_results = [f for f in result if f.category == EnumPlanReviewCategory.R1_COUNTS]
    assert len(r1_results) == 1
    assert r1_results[0].sources == [EnumReviewModel.CODE_DRAFTER]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_r5_category_owned_by_qwen3() -> None:
    """R5 (idempotency) findings must have sources = [code-drafter]."""
    r5_finding = _make_finding(
        category=EnumPlanReviewCategory.R5_IDEMPOTENCY,
        source_model=EnumReviewModel.CODE_DRAFTER,
    )
    callers = _make_empty_callers()
    callers[EnumReviewModel.CODE_DRAFTER] = AsyncMock(return_value=[r5_finding])

    result = await HandlerSpecialistSplit().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=_ALL_CATEGORIES,
            callers=callers,
            weights=_EQUAL_WEIGHTS,
        )
    )

    r5_results = [
        f for f in result if f.category == EnumPlanReviewCategory.R5_IDEMPOTENCY
    ]
    assert len(r5_results) == 1
    assert r5_results[0].sources == [EnumReviewModel.CODE_DRAFTER]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_r4_category_owned_by_deepseek() -> None:
    """R4 (integration traps) findings must have sources = [deep-reasoner]."""
    r4_finding = _make_finding(
        category=EnumPlanReviewCategory.R4_INTEGRATION_TRAPS,
        source_model=EnumReviewModel.DEEP_REASONER,
    )
    callers = _make_empty_callers()
    callers[EnumReviewModel.DEEP_REASONER] = AsyncMock(return_value=[r4_finding])

    result = await HandlerSpecialistSplit().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=_ALL_CATEGORIES,
            callers=callers,
            weights=_EQUAL_WEIGHTS,
        )
    )

    r4_results = [
        f for f in result if f.category == EnumPlanReviewCategory.R4_INTEGRATION_TRAPS
    ]
    assert len(r4_results) == 1
    assert r4_results[0].sources == [EnumReviewModel.DEEP_REASONER]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_r2_r3_owned_by_gemini() -> None:
    """R2 and R3 findings must have sources = [fast-reviewer]."""
    r2_finding = _make_finding(
        category=EnumPlanReviewCategory.R2_ACCEPTANCE_CRITERIA,
        source_model=EnumReviewModel.FAST_REVIEWER,
    )
    r3_finding = _make_finding(
        category=EnumPlanReviewCategory.R3_SCOPE,
        source_model=EnumReviewModel.FAST_REVIEWER,
    )
    callers = _make_empty_callers()
    callers[EnumReviewModel.FAST_REVIEWER] = AsyncMock(
        return_value=[r2_finding, r3_finding]
    )

    result = await HandlerSpecialistSplit().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=_ALL_CATEGORIES,
            callers=callers,
            weights=_EQUAL_WEIGHTS,
        )
    )

    for cat in (
        EnumPlanReviewCategory.R2_ACCEPTANCE_CRITERIA,
        EnumPlanReviewCategory.R3_SCOPE,
    ):
        matches = [f for f in result if f.category == cat]
        assert len(matches) == 1
        assert matches[0].sources == [EnumReviewModel.FAST_REVIEWER], (
            f"Category {cat} should be owned by fast-reviewer"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tiebreaker_glm4_invoked_when_specialist_returns_empty() -> None:
    """tiebreaker is invoked for categories where the primary specialist returned nothing."""
    r6_tiebreaker = _make_finding(
        category=EnumPlanReviewCategory.R6_VERIFICATION,
        source_model=EnumReviewModel.TIEBREAKER,
    )
    callers = _make_empty_callers()
    # deepseek (owner of R6) returns empty — tiebreaker should cover it.
    callers[EnumReviewModel.DEEP_REASONER] = AsyncMock(return_value=[])
    callers[EnumReviewModel.TIEBREAKER] = AsyncMock(return_value=[r6_tiebreaker])

    result = await HandlerSpecialistSplit().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=[EnumPlanReviewCategory.R6_VERIFICATION],
            callers=callers,
            weights=_EQUAL_WEIGHTS,
        )
    )

    r6_results = [
        f for f in result if f.category == EnumPlanReviewCategory.R6_VERIFICATION
    ]
    assert len(r6_results) == 1
    assert r6_results[0].sources == [EnumReviewModel.TIEBREAKER]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tiebreaker_not_invoked_when_all_specialists_have_findings() -> None:
    """tiebreaker must NOT be invoked when every category has at least one finding."""
    callers = _make_empty_callers()
    # Give each specialist a finding in its category.
    callers[EnumReviewModel.CODE_DRAFTER] = AsyncMock(
        return_value=[
            _make_finding(
                category=EnumPlanReviewCategory.R1_COUNTS,
                source_model=EnumReviewModel.CODE_DRAFTER,
            )
        ]
    )
    callers[EnumReviewModel.DEEP_REASONER] = AsyncMock(
        return_value=[
            _make_finding(
                category=EnumPlanReviewCategory.R4_INTEGRATION_TRAPS,
                source_model=EnumReviewModel.DEEP_REASONER,
            )
        ]
    )
    callers[EnumReviewModel.FAST_REVIEWER] = AsyncMock(
        return_value=[
            _make_finding(
                category=EnumPlanReviewCategory.R2_ACCEPTANCE_CRITERIA,
                source_model=EnumReviewModel.FAST_REVIEWER,
            )
        ]
    )
    glm_mock = AsyncMock(return_value=[])
    callers[EnumReviewModel.TIEBREAKER] = glm_mock

    # Only request R1, R4, R2 — all covered by specialists.
    await HandlerSpecialistSplit().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=[
                EnumPlanReviewCategory.R1_COUNTS,
                EnumPlanReviewCategory.R4_INTEGRATION_TRAPS,
                EnumPlanReviewCategory.R2_ACCEPTANCE_CRITERIA,
            ],
            callers=callers,
            weights=_EQUAL_WEIGHTS,
        )
    )

    glm_mock.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_callers_returns_empty() -> None:
    """No callers → empty result."""
    result = await HandlerSpecialistSplit().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=_ALL_CATEGORIES,
            callers={},
            weights={},
        )
    )
    assert result == []


@pytest.mark.unit
def test_specialist_map_covers_all_categories_excluding_glm4() -> None:
    """All R-categories are owned by at least one non-GLM4 specialist."""
    covered: set[EnumPlanReviewCategory] = set()
    for model, cats in _SPECIALIST_MAP.items():
        if model == EnumReviewModel.TIEBREAKER:
            continue
        covered.update(cats)
    assert covered == set(EnumPlanReviewCategory)
