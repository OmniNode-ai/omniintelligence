# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for S1 panel_vote strategy handler.

All LLM calls are mocked.  Network I/O is never performed.

Ticket: OMN-3288
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.strategies.handler_panel_vote import (
    handle_panel_vote,
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
) -> PlanReviewFinding:
    return PlanReviewFinding.create(
        category=category,
        location=location,
        severity=severity,
        description="Test finding description.",
        suggested_fix="Fix it.",
        source_model=source_model,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_finding_raised_by_one_model_excluded() -> None:
    """A finding raised by exactly 1 model must NOT appear in output."""
    sole_finding = _make_finding(source_model=EnumReviewModel.QWEN3_CODER)

    callers = {
        EnumReviewModel.QWEN3_CODER: AsyncMock(return_value=[sole_finding]),
        EnumReviewModel.DEEPSEEK_R1: AsyncMock(return_value=[]),
        EnumReviewModel.GEMINI_FLASH: AsyncMock(return_value=[]),
        EnumReviewModel.GLM_4: AsyncMock(return_value=[]),
    }

    result = await handle_panel_vote(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)

    assert result == [], (
        "Finding raised by exactly 1 model should be excluded from panel_vote output"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_finding_raised_by_two_models_included() -> None:
    """A finding raised by 2 models on the same (category, location) IS included."""
    f_qwen = _make_finding(source_model=EnumReviewModel.QWEN3_CODER)
    f_deepseek = _make_finding(source_model=EnumReviewModel.DEEPSEEK_R1)

    callers = {
        EnumReviewModel.QWEN3_CODER: AsyncMock(return_value=[f_qwen]),
        EnumReviewModel.DEEPSEEK_R1: AsyncMock(return_value=[f_deepseek]),
        EnumReviewModel.GEMINI_FLASH: AsyncMock(return_value=[]),
        EnumReviewModel.GLM_4: AsyncMock(return_value=[]),
    }

    result = await handle_panel_vote(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)

    assert len(result) == 1
    merged = result[0]
    assert merged.category == EnumPlanReviewCategory.R1_COUNTS
    assert EnumReviewModel.QWEN3_CODER in merged.sources
    assert EnumReviewModel.DEEPSEEK_R1 in merged.sources


@pytest.mark.unit
@pytest.mark.asyncio
async def test_confidence_weighted_fraction_two_of_four() -> None:
    """Confidence = sum(agreeing weights) / sum(all weights).

    Two models agree out of four, all equal weight 0.5:
    confidence = (0.5 + 0.5) / (4 * 0.5) = 1.0 / 2.0 = 0.5
    """
    f_qwen = _make_finding(source_model=EnumReviewModel.QWEN3_CODER)
    f_deepseek = _make_finding(source_model=EnumReviewModel.DEEPSEEK_R1)

    callers = {
        EnumReviewModel.QWEN3_CODER: AsyncMock(return_value=[f_qwen]),
        EnumReviewModel.DEEPSEEK_R1: AsyncMock(return_value=[f_deepseek]),
        EnumReviewModel.GEMINI_FLASH: AsyncMock(return_value=[]),
        EnumReviewModel.GLM_4: AsyncMock(return_value=[]),
    }

    result = await handle_panel_vote(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)

    assert len(result) == 1
    assert result[0].confidence == pytest.approx(0.5)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_confidence_all_four_models_agree() -> None:
    """When all 4 equal-weight models agree, confidence = 1.0."""
    callers = {
        m: AsyncMock(return_value=[_make_finding(source_model=m)])
        for m in EnumReviewModel
    }

    result = await handle_panel_vote(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)

    assert len(result) == 1
    assert result[0].confidence == pytest.approx(1.0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_severity_escalates_to_block_if_any_source_blocks() -> None:
    """Severity must be BLOCK if any agreeing model says BLOCK."""
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

    result = await handle_panel_vote(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)

    assert len(result) == 1
    assert result[0].severity == SEVERITY_BLOCK


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_callers_returns_empty() -> None:
    """No callers → empty result."""
    result = await handle_panel_vote(_PLAN, _CATEGORIES, {}, {})
    assert result == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_model_treated_as_empty() -> None:
    """A model that raises an exception contributes zero findings."""

    async def _fail(
        _plan: str, _cats: list[EnumPlanReviewCategory]
    ) -> list[PlanReviewFinding]:
        raise RuntimeError("network error")

    good_finding = _make_finding(source_model=EnumReviewModel.DEEPSEEK_R1)

    callers = {
        EnumReviewModel.QWEN3_CODER: _fail,
        EnumReviewModel.DEEPSEEK_R1: AsyncMock(return_value=[good_finding]),
        EnumReviewModel.GEMINI_FLASH: AsyncMock(return_value=[]),
        EnumReviewModel.GLM_4: AsyncMock(return_value=[]),
    }

    # Only deepseek raised the finding — 1/4 agreement → excluded.
    result = await handle_panel_vote(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)
    assert result == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_distinct_locations_not_merged() -> None:
    """Findings at different locations are not merged even if same category."""
    f1 = _make_finding(
        location="Step 1",
        source_model=EnumReviewModel.QWEN3_CODER,
    )
    f2 = _make_finding(
        location="Step 2",
        source_model=EnumReviewModel.DEEPSEEK_R1,
    )
    # Each location only has 1 model agreeing → neither should appear.
    callers = {
        EnumReviewModel.QWEN3_CODER: AsyncMock(return_value=[f1]),
        EnumReviewModel.DEEPSEEK_R1: AsyncMock(return_value=[f2]),
        EnumReviewModel.GEMINI_FLASH: AsyncMock(return_value=[]),
        EnumReviewModel.GLM_4: AsyncMock(return_value=[]),
    }

    result = await handle_panel_vote(_PLAN, _CATEGORIES, callers, _EQUAL_WEIGHTS)
    assert result == []
