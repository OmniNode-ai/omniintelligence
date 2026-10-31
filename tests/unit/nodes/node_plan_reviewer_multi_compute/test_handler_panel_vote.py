# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for S1 panel_vote strategy handler.

All LLM calls are mocked.  Network I/O is never performed.

Ticket: OMN-3288
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.strategies.handler_panel_vote import (
    HandlerPanelVote,
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
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_strategy_review_request import (
    ModelStrategyReviewRequest,
)

_PLAN = "Sample plan text for testing."
_CATEGORIES = list(EnumPlanReviewCategory)
_EQUAL_WEIGHTS: dict[EnumReviewModel, float] = {
    EnumReviewModel.CODE_DRAFTER: 0.5,
    EnumReviewModel.DEEP_REASONER: 0.5,
    EnumReviewModel.FAST_REVIEWER: 0.5,
    EnumReviewModel.TIEBREAKER: 0.5,
}


def _make_finding(
    *,
    category: EnumPlanReviewCategory = EnumPlanReviewCategory.R1_COUNTS,
    location: str = "Step 3",
    severity: str = SEVERITY_WARN,
    source_model: EnumReviewModel = EnumReviewModel.CODE_DRAFTER,
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
    sole_finding = _make_finding(source_model=EnumReviewModel.CODE_DRAFTER)

    callers = {
        EnumReviewModel.CODE_DRAFTER: AsyncMock(return_value=[sole_finding]),
        EnumReviewModel.DEEP_REASONER: AsyncMock(return_value=[]),
        EnumReviewModel.FAST_REVIEWER: AsyncMock(return_value=[]),
        EnumReviewModel.TIEBREAKER: AsyncMock(return_value=[]),
    }

    result = await HandlerPanelVote().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=_CATEGORIES,
            callers=callers,
            weights=_EQUAL_WEIGHTS,
        )
    )

    assert result == [], (
        "Finding raised by exactly 1 model should be excluded from panel_vote output"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_finding_raised_by_two_models_included() -> None:
    """A finding raised by 2 models on the same (category, location) IS included."""
    f_qwen = _make_finding(source_model=EnumReviewModel.CODE_DRAFTER)
    f_deepseek = _make_finding(source_model=EnumReviewModel.DEEP_REASONER)

    callers = {
        EnumReviewModel.CODE_DRAFTER: AsyncMock(return_value=[f_qwen]),
        EnumReviewModel.DEEP_REASONER: AsyncMock(return_value=[f_deepseek]),
        EnumReviewModel.FAST_REVIEWER: AsyncMock(return_value=[]),
        EnumReviewModel.TIEBREAKER: AsyncMock(return_value=[]),
    }

    result = await HandlerPanelVote().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=_CATEGORIES,
            callers=callers,
            weights=_EQUAL_WEIGHTS,
        )
    )

    assert len(result) == 1
    merged = result[0]
    assert merged.category == EnumPlanReviewCategory.R1_COUNTS
    assert EnumReviewModel.CODE_DRAFTER in merged.sources
    assert EnumReviewModel.DEEP_REASONER in merged.sources


@pytest.mark.unit
@pytest.mark.asyncio
async def test_confidence_weighted_fraction_two_of_four() -> None:
    """Confidence = sum(agreeing weights) / sum(all weights).

    Two models agree out of four, all equal weight 0.5:
    confidence = (0.5 + 0.5) / (4 * 0.5) = 1.0 / 2.0 = 0.5
    """
    f_qwen = _make_finding(source_model=EnumReviewModel.CODE_DRAFTER)
    f_deepseek = _make_finding(source_model=EnumReviewModel.DEEP_REASONER)

    callers = {
        EnumReviewModel.CODE_DRAFTER: AsyncMock(return_value=[f_qwen]),
        EnumReviewModel.DEEP_REASONER: AsyncMock(return_value=[f_deepseek]),
        EnumReviewModel.FAST_REVIEWER: AsyncMock(return_value=[]),
        EnumReviewModel.TIEBREAKER: AsyncMock(return_value=[]),
    }

    result = await HandlerPanelVote().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=_CATEGORIES,
            callers=callers,
            weights=_EQUAL_WEIGHTS,
        )
    )

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

    result = await HandlerPanelVote().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=_CATEGORIES,
            callers=callers,
            weights=_EQUAL_WEIGHTS,
        )
    )

    assert len(result) == 1
    assert result[0].confidence == pytest.approx(1.0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_severity_escalates_to_block_if_any_source_blocks() -> None:
    """Severity must be BLOCK if any agreeing model says BLOCK."""
    f_warn = _make_finding(
        severity=SEVERITY_WARN,
        source_model=EnumReviewModel.CODE_DRAFTER,
    )
    f_block = _make_finding(
        severity=SEVERITY_BLOCK,
        source_model=EnumReviewModel.DEEP_REASONER,
    )

    callers = {
        EnumReviewModel.CODE_DRAFTER: AsyncMock(return_value=[f_warn]),
        EnumReviewModel.DEEP_REASONER: AsyncMock(return_value=[f_block]),
        EnumReviewModel.FAST_REVIEWER: AsyncMock(return_value=[]),
        EnumReviewModel.TIEBREAKER: AsyncMock(return_value=[]),
    }

    result = await HandlerPanelVote().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=_CATEGORIES,
            callers=callers,
            weights=_EQUAL_WEIGHTS,
        )
    )

    assert len(result) == 1
    assert result[0].severity == SEVERITY_BLOCK


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_callers_returns_empty() -> None:
    """No callers → empty result."""
    result = await HandlerPanelVote().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=_CATEGORIES,
            callers={},
            weights={},
        )
    )
    assert result == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_model_treated_as_empty() -> None:
    """A model that raises an exception contributes zero findings."""

    async def _fail(
        _plan: str, _cats: list[EnumPlanReviewCategory]
    ) -> list[PlanReviewFinding]:
        raise RuntimeError("network error")

    good_finding = _make_finding(source_model=EnumReviewModel.DEEP_REASONER)

    callers = {
        EnumReviewModel.CODE_DRAFTER: _fail,
        EnumReviewModel.DEEP_REASONER: AsyncMock(return_value=[good_finding]),
        EnumReviewModel.FAST_REVIEWER: AsyncMock(return_value=[]),
        EnumReviewModel.TIEBREAKER: AsyncMock(return_value=[]),
    }

    # Only deepseek raised the finding — 1/4 agreement → excluded.
    result = await HandlerPanelVote().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=_CATEGORIES,
            callers=callers,
            weights=_EQUAL_WEIGHTS,
        )
    )
    assert result == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_distinct_locations_not_merged() -> None:
    """Findings at different locations are not merged even if same category."""
    f1 = _make_finding(
        location="Step 1",
        source_model=EnumReviewModel.CODE_DRAFTER,
    )
    f2 = _make_finding(
        location="Step 2",
        source_model=EnumReviewModel.DEEP_REASONER,
    )
    # Each location only has 1 model agreeing → neither should appear.
    callers = {
        EnumReviewModel.CODE_DRAFTER: AsyncMock(return_value=[f1]),
        EnumReviewModel.DEEP_REASONER: AsyncMock(return_value=[f2]),
        EnumReviewModel.FAST_REVIEWER: AsyncMock(return_value=[]),
        EnumReviewModel.TIEBREAKER: AsyncMock(return_value=[]),
    }

    result = await HandlerPanelVote().handle(
        ModelStrategyReviewRequest(
            plan_text=_PLAN,
            categories=_CATEGORIES,
            callers=callers,
            weights=_EQUAL_WEIGHTS,
        )
    )
    assert result == []
