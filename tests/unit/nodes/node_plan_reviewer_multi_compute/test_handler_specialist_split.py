# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
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
    handle_specialist_split,
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
_ALL_CATEGORIES = list(EnumPlanReviewCategory)
_EQUAL_WEIGHTS: dict[EnumReviewModel, float] = {
    EnumReviewModel.QWEN3_CODER: 0.5,
    EnumReviewModel.DEEPSEEK_R1: 0.5,
    EnumReviewModel.GEMINI_FLASH: 0.5,
    EnumReviewModel.GLM_4: 0.5,
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
    """R1 (counts) findings must have sources = [qwen3-coder]."""
    r1_finding = _make_finding(
        category=EnumPlanReviewCategory.R1_COUNTS,
        source_model=EnumReviewModel.QWEN3_CODER,
    )
    callers = _make_empty_callers()
    callers[EnumReviewModel.QWEN3_CODER] = AsyncMock(return_value=[r1_finding])

    result = await handle_specialist_split(
        _PLAN, _ALL_CATEGORIES, callers, _EQUAL_WEIGHTS
    )

    r1_results = [f for f in result if f.category == EnumPlanReviewCategory.R1_COUNTS]
    assert len(r1_results) == 1
    assert r1_results[0].sources == [EnumReviewModel.QWEN3_CODER]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_r5_category_owned_by_qwen3() -> None:
    """R5 (idempotency) findings must have sources = [qwen3-coder]."""
    r5_finding = _make_finding(
        category=EnumPlanReviewCategory.R5_IDEMPOTENCY,
        source_model=EnumReviewModel.QWEN3_CODER,
    )
    callers = _make_empty_callers()
    callers[EnumReviewModel.QWEN3_CODER] = AsyncMock(return_value=[r5_finding])

    result = await handle_specialist_split(
        _PLAN, _ALL_CATEGORIES, callers, _EQUAL_WEIGHTS
    )

    r5_results = [
        f for f in result if f.category == EnumPlanReviewCategory.R5_IDEMPOTENCY
    ]
    assert len(r5_results) == 1
    assert r5_results[0].sources == [EnumReviewModel.QWEN3_CODER]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_r4_category_owned_by_deepseek() -> None:
    """R4 (integration traps) findings must have sources = [deepseek-r1]."""
    r4_finding = _make_finding(
        category=EnumPlanReviewCategory.R4_INTEGRATION_TRAPS,
        source_model=EnumReviewModel.DEEPSEEK_R1,
    )
    callers = _make_empty_callers()
    callers[EnumReviewModel.DEEPSEEK_R1] = AsyncMock(return_value=[r4_finding])

    result = await handle_specialist_split(
        _PLAN, _ALL_CATEGORIES, callers, _EQUAL_WEIGHTS
    )

    r4_results = [
        f for f in result if f.category == EnumPlanReviewCategory.R4_INTEGRATION_TRAPS
    ]
    assert len(r4_results) == 1
    assert r4_results[0].sources == [EnumReviewModel.DEEPSEEK_R1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_r2_r3_owned_by_gemini() -> None:
    """R2 and R3 findings must have sources = [gemini-flash]."""
    r2_finding = _make_finding(
        category=EnumPlanReviewCategory.R2_ACCEPTANCE_CRITERIA,
        source_model=EnumReviewModel.GEMINI_FLASH,
    )
    r3_finding = _make_finding(
        category=EnumPlanReviewCategory.R3_SCOPE,
        source_model=EnumReviewModel.GEMINI_FLASH,
    )
    callers = _make_empty_callers()
    callers[EnumReviewModel.GEMINI_FLASH] = AsyncMock(
        return_value=[r2_finding, r3_finding]
    )

    result = await handle_specialist_split(
        _PLAN, _ALL_CATEGORIES, callers, _EQUAL_WEIGHTS
    )

    for cat in (
        EnumPlanReviewCategory.R2_ACCEPTANCE_CRITERIA,
        EnumPlanReviewCategory.R3_SCOPE,
    ):
        matches = [f for f in result if f.category == cat]
        assert len(matches) == 1
        assert matches[0].sources == [EnumReviewModel.GEMINI_FLASH], (
            f"Category {cat} should be owned by gemini-flash"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tiebreaker_glm4_invoked_when_specialist_returns_empty() -> None:
    """glm-4 is invoked for categories where the primary specialist returned nothing."""
    r6_tiebreaker = _make_finding(
        category=EnumPlanReviewCategory.R6_VERIFICATION,
        source_model=EnumReviewModel.GLM_4,
    )
    callers = _make_empty_callers()
    # deepseek (owner of R6) returns empty — glm-4 should cover it.
    callers[EnumReviewModel.DEEPSEEK_R1] = AsyncMock(return_value=[])
    callers[EnumReviewModel.GLM_4] = AsyncMock(return_value=[r6_tiebreaker])

    result = await handle_specialist_split(
        _PLAN,
        [EnumPlanReviewCategory.R6_VERIFICATION],
        callers,
        _EQUAL_WEIGHTS,
    )

    r6_results = [
        f for f in result if f.category == EnumPlanReviewCategory.R6_VERIFICATION
    ]
    assert len(r6_results) == 1
    assert r6_results[0].sources == [EnumReviewModel.GLM_4]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tiebreaker_not_invoked_when_all_specialists_have_findings() -> None:
    """glm-4 must NOT be invoked when every category has at least one finding."""
    callers = _make_empty_callers()
    # Give each specialist a finding in its category.
    callers[EnumReviewModel.QWEN3_CODER] = AsyncMock(
        return_value=[
            _make_finding(
                category=EnumPlanReviewCategory.R1_COUNTS,
                source_model=EnumReviewModel.QWEN3_CODER,
            )
        ]
    )
    callers[EnumReviewModel.DEEPSEEK_R1] = AsyncMock(
        return_value=[
            _make_finding(
                category=EnumPlanReviewCategory.R4_INTEGRATION_TRAPS,
                source_model=EnumReviewModel.DEEPSEEK_R1,
            )
        ]
    )
    callers[EnumReviewModel.GEMINI_FLASH] = AsyncMock(
        return_value=[
            _make_finding(
                category=EnumPlanReviewCategory.R2_ACCEPTANCE_CRITERIA,
                source_model=EnumReviewModel.GEMINI_FLASH,
            )
        ]
    )
    glm_mock = AsyncMock(return_value=[])
    callers[EnumReviewModel.GLM_4] = glm_mock

    # Only request R1, R4, R2 — all covered by specialists.
    await handle_specialist_split(
        _PLAN,
        [
            EnumPlanReviewCategory.R1_COUNTS,
            EnumPlanReviewCategory.R4_INTEGRATION_TRAPS,
            EnumPlanReviewCategory.R2_ACCEPTANCE_CRITERIA,
        ],
        callers,
        _EQUAL_WEIGHTS,
    )

    glm_mock.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_callers_returns_empty() -> None:
    """No callers → empty result."""
    result = await handle_specialist_split(_PLAN, _ALL_CATEGORIES, {}, {})
    assert result == []


@pytest.mark.unit
def test_specialist_map_covers_all_categories_excluding_glm4() -> None:
    """All R-categories are owned by at least one non-GLM4 specialist."""
    covered: set[EnumPlanReviewCategory] = set()
    for model, cats in _SPECIALIST_MAP.items():
        if model == EnumReviewModel.GLM_4:
            continue
        covered.update(cats)
    assert covered == set(EnumPlanReviewCategory)
