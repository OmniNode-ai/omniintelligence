# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for NodeContextAuditAggregatorCompute.

Tests cover:
    - Empty input returns empty output
    - Single event with no violations
    - Single event with violations
    - Multiple events aggregated by correlation_id
    - Violation rate computation
    - Budget utilization computation
    - Scope adherence computation
    - Violations_by_rule breakdown
    - Global metrics across multiple correlation IDs
    - Zero-tolerance budget (budget_limit=0)
    - Over-budget detection
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

from pathlib import Path

from omniintelligence.audit.enum_io_audit_rule import EnumIOAuditRule
from omniintelligence.audit.model_audit_result import ModelAuditResult
from omniintelligence.audit.model_io_audit_violation import ModelIOAuditViolation
from omniintelligence.nodes.audit.node_context_audit_aggregator_compute import (
    ModelContextAuditAggregatorInput,
    ModelContextAuditAggregatorOutput,
    ModelContextAuditEvent,
    NodeContextAuditAggregatorCompute,
    _compute_budget_utilization,
    _compute_scope_adherence,
    _compute_violation_rate,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_violation(
    rule: EnumIOAuditRule = EnumIOAuditRule.ENV_ACCESS,
    file: str = "test.py",
    line: int = 1,
) -> ModelIOAuditViolation:
    return ModelIOAuditViolation(
        file=Path(file),
        line=line,
        column=0,
        rule=rule,
        message="test violation",
    )


def _clean_result(files_scanned: int = 3) -> ModelAuditResult:
    return ModelAuditResult(violations=[], files_scanned=files_scanned)


def _dirty_result(
    violations: list[ModelIOAuditViolation] | None = None,
    files_scanned: int = 3,
) -> ModelAuditResult:
    if violations is None:
        violations = [_make_violation()]
    return ModelAuditResult(violations=violations, files_scanned=files_scanned)


def _event(
    correlation_id: str = "corr-1",
    audit_result: ModelAuditResult | None = None,
    budget_limit: int = 0,
    scope_label: str = "",
) -> ModelContextAuditEvent:
    return ModelContextAuditEvent(
        correlation_id=correlation_id,
        audit_result=audit_result if audit_result is not None else _clean_result(),
        budget_limit=budget_limit,
        scope_label=scope_label,
    )


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------


class TestComputeViolationRate:
    def test_zero_files_returns_zero(self) -> None:
        assert _compute_violation_rate(0, 0) == 0.0

    def test_zero_violations(self) -> None:
        assert _compute_violation_rate(10, 0) == 0.0

    def test_all_files_violated(self) -> None:
        # 5 violations in 5 files → 1.0
        assert _compute_violation_rate(5, 5) == 1.0

    def test_partial_violations(self) -> None:
        # 2 violations in 4 files → 0.5
        assert _compute_violation_rate(4, 2) == 0.5

    def test_violations_exceed_files_capped(self) -> None:
        # More violations than files — rate is capped at 1.0
        assert _compute_violation_rate(3, 10) == 1.0


class TestComputeBudgetUtilization:
    def test_zero_budget_zero_violations_is_clean(self) -> None:
        assert _compute_budget_utilization(0, 0) == 0.0

    def test_zero_budget_with_violations_is_over(self) -> None:
        assert _compute_budget_utilization(3, 0) == 1.0

    def test_within_budget(self) -> None:
        # 2 violations / 10 budget = 0.2
        assert _compute_budget_utilization(2, 10) == 0.2

    def test_at_budget(self) -> None:
        assert _compute_budget_utilization(5, 5) == 1.0

    def test_over_budget_exceeds_one(self) -> None:
        assert _compute_budget_utilization(8, 4) == 2.0


class TestComputeScopeAdherence:
    def test_zero_events_returns_zero(self) -> None:
        assert _compute_scope_adherence(0, 0) == 0.0

    def test_all_clean(self) -> None:
        assert _compute_scope_adherence(5, 5) == 1.0

    def test_none_clean(self) -> None:
        assert _compute_scope_adherence(5, 0) == 0.0

    def test_partial(self) -> None:
        assert _compute_scope_adherence(4, 2) == 0.5


# ---------------------------------------------------------------------------
# Node integration tests
# ---------------------------------------------------------------------------


class TestNodeContextAuditAggregatorCompute:
    """Tests for the full compute node."""

    @pytest.fixture
    def node(self) -> NodeContextAuditAggregatorCompute:
        return NodeContextAuditAggregatorCompute()

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty_output(
        self, node: NodeContextAuditAggregatorCompute
    ) -> None:
        result = await node.execute_compute(ModelContextAuditAggregatorInput(events=[]))
        assert isinstance(result, ModelContextAuditAggregatorOutput)
        assert result.aggregates == []
        assert result.total_correlation_ids == 0
        assert result.global_violation_rate == 0.0
        assert result.global_scope_adherence == 0.0

    @pytest.mark.asyncio
    async def test_single_clean_event(
        self, node: NodeContextAuditAggregatorCompute
    ) -> None:
        events = [_event(correlation_id="corr-1", audit_result=_clean_result(5))]
        result = await node.execute_compute(
            ModelContextAuditAggregatorInput(events=events)
        )
        assert result.total_correlation_ids == 1
        agg = result.aggregates[0]
        assert agg.correlation_id == "corr-1"
        assert agg.total_events == 1
        assert agg.total_files_scanned == 5
        assert agg.total_violations == 0
        assert agg.violation_rate == 0.0
        assert agg.is_clean is True
        assert agg.over_budget is False
        assert agg.scope_adherence == 1.0

    @pytest.mark.asyncio
    async def test_single_event_with_violations(
        self, node: NodeContextAuditAggregatorCompute
    ) -> None:
        violations = [_make_violation(EnumIOAuditRule.NET_CLIENT)]
        events = [
            _event(
                correlation_id="corr-2",
                audit_result=_dirty_result(violations=violations, files_scanned=4),
                budget_limit=2,
            )
        ]
        result = await node.execute_compute(
            ModelContextAuditAggregatorInput(events=events)
        )
        agg = result.aggregates[0]
        assert agg.total_violations == 1
        assert agg.is_clean is False
        assert agg.over_budget is False  # 1 <= 2
        assert agg.violations_by_rule[EnumIOAuditRule.NET_CLIENT.value] == 1
        assert agg.violations_by_rule[EnumIOAuditRule.ENV_ACCESS.value] == 0
        assert agg.violations_by_rule[EnumIOAuditRule.FILE_IO.value] == 0

    @pytest.mark.asyncio
    async def test_multiple_events_same_correlation(
        self, node: NodeContextAuditAggregatorCompute
    ) -> None:
        events = [
            _event(
                correlation_id="corr-3",
                audit_result=_clean_result(2),
                scope_label="node_a",
            ),
            _event(
                correlation_id="corr-3",
                audit_result=_dirty_result(files_scanned=3),
                scope_label="node_b",
            ),
        ]
        result = await node.execute_compute(
            ModelContextAuditAggregatorInput(events=events)
        )
        assert result.total_correlation_ids == 1
        agg = result.aggregates[0]
        assert agg.total_events == 2
        assert agg.total_files_scanned == 5
        assert agg.total_violations == 1
        assert agg.is_clean is False
        # 1 clean event out of 2 → 0.5
        assert agg.scope_adherence == 0.5
        assert set(agg.scopes_seen) == {"node_a", "node_b"}

    @pytest.mark.asyncio
    async def test_multiple_correlation_ids_separated(
        self, node: NodeContextAuditAggregatorCompute
    ) -> None:
        events = [
            _event(correlation_id="corr-A", audit_result=_clean_result(2)),
            _event(
                correlation_id="corr-B",
                audit_result=_dirty_result(files_scanned=4),
            ),
        ]
        result = await node.execute_compute(
            ModelContextAuditAggregatorInput(events=events)
        )
        assert result.total_correlation_ids == 2
        corr_map = {a.correlation_id: a for a in result.aggregates}
        assert corr_map["corr-A"].is_clean is True
        assert corr_map["corr-B"].is_clean is False

    @pytest.mark.asyncio
    async def test_over_budget_flagged(
        self, node: NodeContextAuditAggregatorCompute
    ) -> None:
        violations = [
            _make_violation(EnumIOAuditRule.FILE_IO, file=f"f{i}.py") for i in range(5)
        ]
        events = [
            _event(
                correlation_id="corr-X",
                audit_result=_dirty_result(violations=violations, files_scanned=10),
                budget_limit=3,
            )
        ]
        result = await node.execute_compute(
            ModelContextAuditAggregatorInput(events=events)
        )
        agg = result.aggregates[0]
        assert agg.over_budget is True
        # budget_utilization = 5/3 ≈ 1.6667
        assert agg.budget_utilization > 1.0

    @pytest.mark.asyncio
    async def test_zero_tolerance_budget_with_violations(
        self, node: NodeContextAuditAggregatorCompute
    ) -> None:
        events = [
            _event(
                correlation_id="corr-Z",
                audit_result=_dirty_result(files_scanned=5),
                budget_limit=0,
            )
        ]
        result = await node.execute_compute(
            ModelContextAuditAggregatorInput(events=events)
        )
        agg = result.aggregates[0]
        assert agg.over_budget is True
        assert agg.budget_utilization == 1.0

    @pytest.mark.asyncio
    async def test_zero_tolerance_budget_clean(
        self, node: NodeContextAuditAggregatorCompute
    ) -> None:
        events = [
            _event(
                correlation_id="corr-ZZ",
                audit_result=_clean_result(3),
                budget_limit=0,
            )
        ]
        result = await node.execute_compute(
            ModelContextAuditAggregatorInput(events=events)
        )
        agg = result.aggregates[0]
        assert agg.is_clean is True
        assert agg.over_budget is False
        assert agg.budget_utilization == 0.0

    @pytest.mark.asyncio
    async def test_global_metrics_computed(
        self, node: NodeContextAuditAggregatorCompute
    ) -> None:
        # 2 events: 1 clean, 1 dirty across 2 correlation IDs
        events = [
            _event(correlation_id="g-1", audit_result=_clean_result(4)),
            _event(
                correlation_id="g-2",
                audit_result=_dirty_result(files_scanned=4),
            ),
        ]
        result = await node.execute_compute(
            ModelContextAuditAggregatorInput(events=events)
        )
        # 1 violation in 8 total files → rate = 1/8 = 0.125
        assert result.global_violation_rate == 0.125
        # 1 clean event out of 2 → 0.5
        assert result.global_scope_adherence == 0.5

    @pytest.mark.asyncio
    async def test_scope_labels_deduplicated(
        self, node: NodeContextAuditAggregatorCompute
    ) -> None:
        events = [
            _event(correlation_id="c", audit_result=_clean_result(), scope_label="s1"),
            _event(correlation_id="c", audit_result=_clean_result(), scope_label="s1"),
            _event(correlation_id="c", audit_result=_clean_result(), scope_label="s2"),
        ]
        result = await node.execute_compute(
            ModelContextAuditAggregatorInput(events=events)
        )
        agg = result.aggregates[0]
        assert agg.scopes_seen == ["s1", "s2"]

    @pytest.mark.asyncio
    async def test_violations_by_rule_all_rules_present(
        self, node: NodeContextAuditAggregatorCompute
    ) -> None:
        """All EnumIOAuditRule values should appear in violations_by_rule even if zero."""
        events = [_event(correlation_id="r", audit_result=_clean_result())]
        result = await node.execute_compute(
            ModelContextAuditAggregatorInput(events=events)
        )
        agg = result.aggregates[0]
        for rule in EnumIOAuditRule:
            assert rule.value in agg.violations_by_rule
