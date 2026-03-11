# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for S4 independent_merge strategy handler.

All LLM calls are mocked.  Network I/O is never performed.

Ticket: OMN-3288
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.strategies.handler_independent_merge import (
    handle_independent_merge,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_plan_review_category import (
    EnumPlanReviewCategory,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_review_finding import (
    SEVERITY_BLOCK,
    SEVERITY_WARN,
    PlanReviewFinding,
)

_PLAN = "Sample plan text for testing."
_CATEGORIES = list(EnumPlanReviewCategory)
_EQUAL_WEIGHTS: dict[EnumReviewModel, float] = {
    EnumReviewModel.QWEN3_CODER: 0.5,
    EnumReviewModel.DEEPSEEK_R1: 0.5,
    EnumReviewModel.GEMINI_FLASH: 0.5,
    EnumReviewModel.GLM_4: 0.5,
}


def _make_finding(
    *,
    category: EnumPlanReviewCategory = EnumPlanReviewCategory.R1_COUNTS,
    location: str = "Step 3",
    severity: str = SEVERITY_WARN,
    source_model: EnumReviewModel = EnumReviewModel.QWEN3_CODER,
    patch: str | None = None,
) -> PlanReviewFinding:
    return PlanReviewFinding.create(
        category=category,
        location=location,
        severity=severity,
        description="Test finding.",
        suggested_fix="Fix it.",
        source_model=source_model,
        patch=patch,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_block_severity_escalates_if_any_source_blocks() -> None:
    """If any model raises a finding as BLOCK, merged severity must be BLOCK."""
    f_warn = _make_finding(
        severity=SEVERITY_WARN,
        source_model=EnumReviewModel.QWEN3_CODER,
    )
    f_block = _make_finding(
        severity=SEVERITY_BLOCK,
        source_model=EnumReviewModel.DEEPSEEK_R1,
    )
    callers = {
        EnumReviewModel.QWEN3_CODER: AsyncMock(return_value=[f_warn]),
        EnumReviewModel.DEEPSEEK_R1: AsyncMock(return_value=[f_block]),
        EnumReviewModel.GEMINI_FLASH: AsyncMock(return_value=[]),
        EnumReviewModel.GLM_4: AsyncMock(return_value=[]),
    }

    result = await handle_independent_merge(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)

    assert len(result) == 1
    assert result[0].severity == SEVERITY_BLOCK, (
        "Merged severity must be BLOCK when any source says BLOCK"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_confidence_formula_two_of_four() -> None:
    """Confidence = sum(source weights) / sum(all weights).

    2 sources agreeing out of 4 equal-weight models:
    confidence = (0.5 + 0.5) / (4 * 0.5) = 0.5
    """
    f_qwen = _make_finding(source_model=EnumReviewModel.QWEN3_CODER)
    f_deepseek = _make_finding(source_model=EnumReviewModel.DEEPSEEK_R1)

    callers = {
        EnumReviewModel.QWEN3_CODER: AsyncMock(return_value=[f_qwen]),
        EnumReviewModel.DEEPSEEK_R1: AsyncMock(return_value=[f_deepseek]),
        EnumReviewModel.GEMINI_FLASH: AsyncMock(return_value=[]),
        EnumReviewModel.GLM_4: AsyncMock(return_value=[]),
    }

    result = await handle_independent_merge(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)

    assert len(result) == 1
    assert result[0].confidence == pytest.approx(0.5)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_confidence_single_source() -> None:
    """Single source: confidence = weight[source] / total_weight.

    2 callers with equal weight 0.5 each → total_weight = 1.0.
    1 source (qwen3, weight=0.5) → confidence = 0.5 / 1.0 = 0.5.
    """
    f_qwen = _make_finding(source_model=EnumReviewModel.QWEN3_CODER)
    weights = {
        EnumReviewModel.QWEN3_CODER: 0.5,
        EnumReviewModel.DEEPSEEK_R1: 0.5,
    }
    callers = {
        EnumReviewModel.QWEN3_CODER: AsyncMock(return_value=[f_qwen]),
        EnumReviewModel.DEEPSEEK_R1: AsyncMock(return_value=[]),
    }

    result = await handle_independent_merge(_PLAN, _CATEGORIES, callers, weights)

    assert len(result) == 1
    # total_weight = 0.5 + 0.5 = 1.0; source_weight = 0.5 → confidence = 0.5
    assert result[0].confidence == pytest.approx(0.5)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_confidence_all_four_agree() -> None:
    """All 4 models agreeing on the same finding → confidence = 1.0."""
    callers = {
        m: AsyncMock(return_value=[_make_finding(source_model=m)])
        for m in EnumReviewModel
    }

    result = await handle_independent_merge(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)

    assert len(result) == 1
    assert result[0].confidence == pytest.approx(1.0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deduplication_by_category_and_location_normalized() -> None:
    """Findings at the same (category, location_normalized) are merged into one."""
    f_qwen = _make_finding(
        location="  Step 3  ",  # whitespace variant
        source_model=EnumReviewModel.QWEN3_CODER,
    )
    f_deepseek = _make_finding(
        location="STEP 3",  # upper-case variant
        source_model=EnumReviewModel.DEEPSEEK_R1,
    )
    callers = {
        EnumReviewModel.QWEN3_CODER: AsyncMock(return_value=[f_qwen]),
        EnumReviewModel.DEEPSEEK_R1: AsyncMock(return_value=[f_deepseek]),
        EnumReviewModel.GEMINI_FLASH: AsyncMock(return_value=[]),
        EnumReviewModel.GLM_4: AsyncMock(return_value=[]),
    }

    result = await handle_independent_merge(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)

    assert len(result) == 1, "Same (category, location_normalized) must be deduplicated"
    assert set(result[0].sources) == {
        EnumReviewModel.QWEN3_CODER,
        EnumReviewModel.DEEPSEEK_R1,
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_distinct_locations_produce_separate_entries() -> None:
    """Findings at different locations are NOT merged."""
    f1 = _make_finding(location="Step 1", source_model=EnumReviewModel.QWEN3_CODER)
    f2 = _make_finding(location="Step 2", source_model=EnumReviewModel.DEEPSEEK_R1)
    callers = {
        EnumReviewModel.QWEN3_CODER: AsyncMock(return_value=[f1]),
        EnumReviewModel.DEEPSEEK_R1: AsyncMock(return_value=[f2]),
        EnumReviewModel.GEMINI_FLASH: AsyncMock(return_value=[]),
        EnumReviewModel.GLM_4: AsyncMock(return_value=[]),
    }

    result = await handle_independent_merge(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)

    assert len(result) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_single_model_finding_is_included() -> None:
    """Unlike panel_vote, S4 includes findings from a single model."""
    sole_finding = _make_finding(source_model=EnumReviewModel.QWEN3_CODER)
    callers = {
        EnumReviewModel.QWEN3_CODER: AsyncMock(return_value=[sole_finding]),
        EnumReviewModel.DEEPSEEK_R1: AsyncMock(return_value=[]),
        EnumReviewModel.GEMINI_FLASH: AsyncMock(return_value=[]),
        EnumReviewModel.GLM_4: AsyncMock(return_value=[]),
    }

    result = await handle_independent_merge(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)

    assert len(result) == 1, (
        "independent_merge must include all findings regardless of agreement count"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_callers_returns_empty() -> None:
    """No callers → empty result."""
    result = await handle_independent_merge(_PLAN, _CATEGORIES, {}, {})
    assert result == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_model_treated_as_empty() -> None:
    """A model that raises an exception contributes zero findings."""

    async def _fail(
        _plan: str, _cats: list[EnumPlanReviewCategory]
    ) -> list[PlanReviewFinding]:
        raise RuntimeError("model down")

    good_finding = _make_finding(source_model=EnumReviewModel.DEEPSEEK_R1)
    callers = {
        EnumReviewModel.QWEN3_CODER: _fail,
        EnumReviewModel.DEEPSEEK_R1: AsyncMock(return_value=[good_finding]),
        EnumReviewModel.GEMINI_FLASH: AsyncMock(return_value=[]),
        EnumReviewModel.GLM_4: AsyncMock(return_value=[]),
    }

    result = await handle_independent_merge(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)

    # deepseek's finding is still included (S4 includes single-model findings).
    assert len(result) == 1
    assert result[0].sources == [EnumReviewModel.DEEPSEEK_R1]
