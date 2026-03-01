# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for handle_plan_reviewer_multi_compute (main dispatcher).

All LLM calls and DB interactions are mocked.  No real network or DB I/O
is performed in any test.

Ticket: OMN-3291
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.handler_confidence_scorer import (
    ProtocolDBConnection,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.handler_plan_reviewer_multi_compute import (
    handle_plan_reviewer_multi_compute,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_plan_review_category import (
    EnumPlanReviewCategory,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_strategy import (
    EnumReviewStrategy,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_review_finding import (
    SEVERITY_WARN,
    PlanReviewFinding,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_reviewer_multi_input import (
    ModelPlanReviewerMultiCommand,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PLAN = "## Plan\n1. Step one\n2. Step two\n3. Step three"


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


def _make_callers(
    findings: list[PlanReviewFinding] | None = None,
) -> dict[EnumReviewModel, AsyncMock]:
    """Return four mock callers; all return the same findings list."""
    findings = findings or []
    return {m: AsyncMock(return_value=findings) for m in EnumReviewModel}


def _make_db_conn_success() -> ProtocolDBConnection:
    """Return a mock DB connection that succeeds on fetch and execute."""
    conn = MagicMock(spec=ProtocolDBConnection)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=None)
    return conn  # type: ignore[return-value]


def _make_db_conn_failing() -> ProtocolDBConnection:
    """Return a mock DB connection that fails on execute."""
    conn = MagicMock(spec=ProtocolDBConnection)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(side_effect=RuntimeError("DB unavailable"))
    return conn  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Strategy dispatch
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_s1_panel_vote_dispatched() -> None:
    """S1_PANEL_VOTE strategy produces a valid output."""
    callers = _make_callers()
    cmd = ModelPlanReviewerMultiCommand(
        plan_text=_PLAN,
        strategy=EnumReviewStrategy.S1_PANEL_VOTE,
    )
    output = await handle_plan_reviewer_multi_compute(cmd, callers)
    assert output.strategy == EnumReviewStrategy.S1_PANEL_VOTE


@pytest.mark.unit
@pytest.mark.asyncio
async def test_s2_specialist_split_dispatched() -> None:
    """S2_SPECIALIST_SPLIT strategy produces a valid output."""
    callers = _make_callers()
    cmd = ModelPlanReviewerMultiCommand(
        plan_text=_PLAN,
        strategy=EnumReviewStrategy.S2_SPECIALIST_SPLIT,
    )
    output = await handle_plan_reviewer_multi_compute(cmd, callers)
    assert output.strategy == EnumReviewStrategy.S2_SPECIALIST_SPLIT


@pytest.mark.unit
@pytest.mark.asyncio
async def test_s3_sequential_critique_dispatched() -> None:
    """S3_SEQUENTIAL_CRITIQUE strategy produces a valid output when critic_caller provided."""
    drafter_finding = _make_finding(source_model=EnumReviewModel.QWEN3_CODER)
    callers = _make_callers([drafter_finding])
    critic_caller = AsyncMock(
        return_value={
            "confirmed": [drafter_finding.finding_id],
            "rejected": [],
            "added": [],
        }
    )
    cmd = ModelPlanReviewerMultiCommand(
        plan_text=_PLAN,
        strategy=EnumReviewStrategy.S3_SEQUENTIAL_CRITIQUE,
    )
    output = await handle_plan_reviewer_multi_compute(
        cmd, callers, critic_caller=critic_caller
    )
    assert output.strategy == EnumReviewStrategy.S3_SEQUENTIAL_CRITIQUE


@pytest.mark.unit
@pytest.mark.asyncio
async def test_s3_fallback_to_s4_when_critic_caller_missing() -> None:
    """S3 falls back to S4 independent_merge when critic_caller is not provided."""
    callers = _make_callers()
    cmd = ModelPlanReviewerMultiCommand(
        plan_text=_PLAN,
        strategy=EnumReviewStrategy.S3_SEQUENTIAL_CRITIQUE,
    )
    # No critic_caller passed.
    output = await handle_plan_reviewer_multi_compute(cmd, callers)
    # Falls back to S4 — output strategy is still S3 (command echo).
    assert output.strategy == EnumReviewStrategy.S3_SEQUENTIAL_CRITIQUE


@pytest.mark.unit
@pytest.mark.asyncio
async def test_s4_independent_merge_dispatched() -> None:
    """S4_INDEPENDENT_MERGE (default) strategy produces a valid output."""
    callers = _make_callers()
    cmd = ModelPlanReviewerMultiCommand(
        plan_text=_PLAN,
        strategy=EnumReviewStrategy.S4_INDEPENDENT_MERGE,
    )
    output = await handle_plan_reviewer_multi_compute(cmd, callers)
    assert output.strategy == EnumReviewStrategy.S4_INDEPENDENT_MERGE


# ---------------------------------------------------------------------------
# Output fields
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_models_used_reflects_active_callers() -> None:
    """models_used in output matches the keys of model_callers."""
    callers = _make_callers()
    cmd = ModelPlanReviewerMultiCommand(plan_text=_PLAN)
    output = await handle_plan_reviewer_multi_compute(cmd, callers)
    assert set(output.models_used) == set(EnumReviewModel)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_model_ids_filter_limits_active_callers() -> None:
    """When model_ids is specified, only those models are used."""
    callers = _make_callers()
    cmd = ModelPlanReviewerMultiCommand(
        plan_text=_PLAN,
        model_ids=[EnumReviewModel.QWEN3_CODER, EnumReviewModel.DEEPSEEK_R1],
    )
    output = await handle_plan_reviewer_multi_compute(cmd, callers)
    assert set(output.models_used) == {
        EnumReviewModel.QWEN3_CODER,
        EnumReviewModel.DEEPSEEK_R1,
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_findings_count_matches_findings_length() -> None:
    """findings_count is always equal to len(findings)."""
    # Make two models agree on the same finding → panel_vote includes it.
    f_q = _make_finding(source_model=EnumReviewModel.QWEN3_CODER)
    f_d = _make_finding(source_model=EnumReviewModel.DEEPSEEK_R1)
    callers: dict[EnumReviewModel, AsyncMock] = {
        EnumReviewModel.QWEN3_CODER: AsyncMock(return_value=[f_q]),
        EnumReviewModel.DEEPSEEK_R1: AsyncMock(return_value=[f_d]),
        EnumReviewModel.GEMINI_FLASH: AsyncMock(return_value=[]),
        EnumReviewModel.GLM_4: AsyncMock(return_value=[]),
    }
    cmd = ModelPlanReviewerMultiCommand(
        plan_text=_PLAN,
        strategy=EnumReviewStrategy.S1_PANEL_VOTE,
    )
    output = await handle_plan_reviewer_multi_compute(cmd, callers)
    assert output.findings_count == len(output.findings)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_id_echoed_in_output() -> None:
    """run_id from the command is echoed in the output."""
    callers = _make_callers()
    cmd = ModelPlanReviewerMultiCommand(
        plan_text=_PLAN,
        run_id="OMN-1234",
    )
    output = await handle_plan_reviewer_multi_compute(cmd, callers)
    assert output.run_id == "OMN-1234"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_id_none_echoed_in_output() -> None:
    """run_id=None from the command is echoed as None in output."""
    callers = _make_callers()
    cmd = ModelPlanReviewerMultiCommand(plan_text=_PLAN, run_id=None)
    output = await handle_plan_reviewer_multi_compute(cmd, callers)
    assert output.run_id is None


# ---------------------------------------------------------------------------
# DB write behavior
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_db_write_success_strategy_run_stored_true() -> None:
    """When DB write succeeds, strategy_run_stored=True and strategy_run_id is set."""
    from uuid import UUID

    callers = _make_callers()
    db = _make_db_conn_success()
    cmd = ModelPlanReviewerMultiCommand(plan_text=_PLAN)
    output = await handle_plan_reviewer_multi_compute(cmd, callers, db_conn=db)
    assert output.strategy_run_stored is True
    assert isinstance(output.strategy_run_id, UUID)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_db_unavailable_strategy_run_stored_false() -> None:
    """When DB write fails, strategy_run_stored=False and no exception is raised."""
    callers = _make_callers()
    db = _make_db_conn_failing()
    cmd = ModelPlanReviewerMultiCommand(plan_text=_PLAN)
    output = await handle_plan_reviewer_multi_compute(cmd, callers, db_conn=db)
    assert output.strategy_run_stored is False
    assert output.strategy_run_id is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_db_conn_strategy_run_stored_false() -> None:
    """With db_conn=None, strategy_run_stored=False and result is still valid."""
    callers = _make_callers()
    cmd = ModelPlanReviewerMultiCommand(plan_text=_PLAN)
    output = await handle_plan_reviewer_multi_compute(cmd, callers, db_conn=None)
    assert output.strategy_run_stored is False
    assert isinstance(output.findings, list)
