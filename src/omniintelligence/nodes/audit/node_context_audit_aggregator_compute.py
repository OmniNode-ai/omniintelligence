# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Context Audit Aggregator Compute Node.

Aggregates context audit events by correlation_id and computes efficiency
metrics including violation rates, budget utilization, and scope adherence.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Final

from pydantic import BaseModel, Field

from omniintelligence.audit.enum_io_audit_rule import EnumIOAuditRule
from omniintelligence.audit.model_audit_result import ModelAuditResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VIOLATION_RATE_PRECISION: Final[int] = 4


# ---------------------------------------------------------------------------
# Input / Output models
# ---------------------------------------------------------------------------


class ModelContextAuditEvent(BaseModel):
    """A single context audit event with correlation tracking.

    Attributes:
        correlation_id: Groups related audit events into a single logical run.
        audit_result: The result produced by the I/O auditor for this event.
        budget_limit: Maximum number of allowed violations for this context.
        scope_label: Logical scope identifier (e.g. node name, module path).
    """

    correlation_id: str = Field(
        ...,
        min_length=1,
        description="Correlation ID grouping related audit events",
    )
    audit_result: ModelAuditResult = Field(
        ...,
        description="Audit result for this event",
    )
    budget_limit: int = Field(
        default=0,
        ge=0,
        description="Maximum violations allowed (0 = zero-tolerance)",
    )
    scope_label: str = Field(
        default="",
        description="Logical scope label for grouping (e.g. node name or module)",
    )

    model_config = {"frozen": True, "arbitrary_types_allowed": True}


class ModelAggregatedAuditMetrics(BaseModel):
    """Per-correlation-id aggregated audit metrics.

    Attributes:
        correlation_id: The correlation ID these metrics belong to.
        total_events: Number of audit events aggregated.
        total_files_scanned: Sum of files_scanned across all events.
        total_violations: Total violation count across all events.
        violation_rate: Fraction of scanned files with at least one violation.
        budget_utilization: Fraction of budget consumed (violations / budget_limit).
            Returns 1.0 when budget_limit is 0 and violations > 0 (over budget).
            Returns 0.0 when budget_limit is 0 and violations == 0 (within budget).
        scope_adherence: Fraction of events with zero violations.
        violations_by_rule: Breakdown of violations by rule type.
        scopes_seen: Unique scope labels observed in this correlation group.
        is_clean: True when total_violations == 0.
        over_budget: True when violations exceed budget_limit.
    """

    correlation_id: str = Field(..., description="Correlation ID for this aggregate")
    total_events: int = Field(
        default=0, ge=0, description="Number of events aggregated"
    )
    total_files_scanned: int = Field(default=0, ge=0, description="Total files scanned")
    total_violations: int = Field(default=0, ge=0, description="Total violations found")
    violation_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of scanned files with at least one violation",
    )
    budget_utilization: float = Field(
        default=0.0,
        ge=0.0,
        description="Fraction of violation budget consumed (can exceed 1.0 when over budget)",
    )
    scope_adherence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of events with zero violations",
    )
    violations_by_rule: dict[str, int] = Field(
        default_factory=dict,
        description="Violation count keyed by rule name",
    )
    scopes_seen: list[str] = Field(
        default_factory=list,
        description="Unique scope labels observed in this correlation group",
    )
    is_clean: bool = Field(default=True, description="True when no violations found")
    over_budget: bool = Field(
        default=False, description="True when violations exceed budget_limit"
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelContextAuditAggregatorInput(BaseModel):
    """Input model for the context audit aggregator compute node.

    Attributes:
        events: List of audit events to aggregate.
    """

    events: list[ModelContextAuditEvent] = Field(
        default_factory=list,
        description="Audit events to aggregate by correlation_id",
    )

    model_config = {"frozen": True, "arbitrary_types_allowed": True}


class ModelContextAuditAggregatorOutput(BaseModel):
    """Output model for the context audit aggregator compute node.

    Attributes:
        aggregates: Per-correlation-id aggregated metrics.
        total_correlation_ids: Number of distinct correlation IDs processed.
        global_violation_rate: Aggregate violation rate across all events.
        global_scope_adherence: Aggregate scope adherence across all events.
    """

    aggregates: list[ModelAggregatedAuditMetrics] = Field(
        default_factory=list,
        description="Aggregated metrics per correlation_id",
    )
    total_correlation_ids: int = Field(
        default=0, ge=0, description="Number of distinct correlation IDs"
    )
    global_violation_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall violation rate across all events",
    )
    global_scope_adherence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall scope adherence across all events",
    )

    model_config = {"frozen": True, "extra": "forbid"}


# ---------------------------------------------------------------------------
# Pure aggregation helpers
# ---------------------------------------------------------------------------


def _compute_violation_rate(total_files: int, total_violations: int) -> float:
    """Compute fraction of scanned files that have at least one violation.

    This is an approximation: we use min(violations, files) / files because
    we only have total counts, not per-file breakdowns.

    Args:
        total_files: Total number of files scanned.
        total_violations: Total number of violations found.

    Returns:
        Float in [0.0, 1.0].
    """
    if total_files == 0:
        return 0.0
    capped = min(total_violations, total_files)
    return round(capped / total_files, _VIOLATION_RATE_PRECISION)


def _compute_budget_utilization(total_violations: int, cumulative_budget: int) -> float:
    """Compute fraction of cumulative budget consumed.

    When cumulative_budget is 0 and violations > 0 the node is over budget,
    so we return 1.0.  When both are 0 the node is clean, so we return 0.0.

    Args:
        total_violations: Total violations found.
        cumulative_budget: Sum of budget_limit across all events in the group.

    Returns:
        Float >= 0.0 (may exceed 1.0 when over budget).
    """
    if cumulative_budget == 0:
        return 1.0 if total_violations > 0 else 0.0
    return round(total_violations / cumulative_budget, _VIOLATION_RATE_PRECISION)


def _compute_scope_adherence(total_events: int, clean_events: int) -> float:
    """Compute fraction of events with zero violations.

    Args:
        total_events: Total event count.
        clean_events: Events with zero violations.

    Returns:
        Float in [0.0, 1.0].
    """
    if total_events == 0:
        return 0.0
    return round(clean_events / total_events, _VIOLATION_RATE_PRECISION)


def _aggregate_events(
    events: list[ModelContextAuditEvent],
) -> list[ModelAggregatedAuditMetrics]:
    """Aggregate a list of audit events by correlation_id.

    Args:
        events: Audit events to aggregate.

    Returns:
        List of per-correlation-id aggregated metrics.
    """
    groups: dict[str, list[ModelContextAuditEvent]] = defaultdict(list)
    for event in events:
        groups[event.correlation_id].append(event)

    results: list[ModelAggregatedAuditMetrics] = []
    for correlation_id, group in groups.items():
        total_events = len(group)
        total_files = sum(e.audit_result.files_scanned for e in group)
        total_violations = sum(len(e.audit_result.violations) for e in group)
        cumulative_budget = sum(e.budget_limit for e in group)
        clean_events = sum(1 for e in group if e.audit_result.is_clean)

        # Violations by rule
        violations_by_rule: dict[str, int] = defaultdict(int)
        for event in group:
            for v in event.audit_result.violations:
                violations_by_rule[v.rule.value] += 1
        # Ensure all known rules present
        for rule in EnumIOAuditRule:
            if rule.value not in violations_by_rule:
                violations_by_rule[rule.value] = 0

        scopes_seen = sorted({e.scope_label for e in group if e.scope_label})

        violation_rate = _compute_violation_rate(total_files, total_violations)
        budget_utilization = _compute_budget_utilization(
            total_violations, cumulative_budget
        )
        scope_adherence = _compute_scope_adherence(total_events, clean_events)

        results.append(
            ModelAggregatedAuditMetrics(
                correlation_id=correlation_id,
                total_events=total_events,
                total_files_scanned=total_files,
                total_violations=total_violations,
                violation_rate=violation_rate,
                budget_utilization=budget_utilization,
                scope_adherence=scope_adherence,
                violations_by_rule=dict(violations_by_rule),
                scopes_seen=scopes_seen,
                is_clean=(total_violations == 0),
                over_budget=(total_violations > cumulative_budget),
            )
        )

    return results


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


class NodeContextAuditAggregatorCompute:
    """Compute node that aggregates context audit events by correlation_id.

    This node is a pure computation node following the ONEX 4-node architecture.
    It has no I/O side effects — all inputs are passed directly and all results
    are returned as typed output models.

    Aggregation produces per-correlation-id metrics:
        - violation_rate: fraction of scanned files with violations
        - budget_utilization: violations / cumulative budget_limit
        - scope_adherence: fraction of events with zero violations
    """

    async def execute_compute(
        self,
        input_data: ModelContextAuditAggregatorInput,
    ) -> ModelContextAuditAggregatorOutput:
        """Aggregate audit events and compute efficiency metrics.

        Args:
            input_data: Input containing the list of audit events to aggregate.

        Returns:
            ModelContextAuditAggregatorOutput with per-correlation-id aggregates
            and global summary metrics.
        """
        if not input_data.events:
            return ModelContextAuditAggregatorOutput()

        aggregates = _aggregate_events(input_data.events)

        total_events = len(input_data.events)
        total_files = sum(a.total_files_scanned for a in aggregates)
        total_violations = sum(a.total_violations for a in aggregates)
        clean_events = sum(1 for e in input_data.events if e.audit_result.is_clean)

        global_violation_rate = _compute_violation_rate(total_files, total_violations)
        global_scope_adherence = _compute_scope_adherence(total_events, clean_events)

        return ModelContextAuditAggregatorOutput(
            aggregates=aggregates,
            total_correlation_ids=len(aggregates),
            global_violation_rate=global_violation_rate,
            global_scope_adherence=global_scope_adherence,
        )


__all__ = [
    "NodeContextAuditAggregatorCompute",
    "ModelContextAuditAggregatorInput",
    "ModelContextAuditAggregatorOutput",
    "ModelContextAuditEvent",
    "ModelAggregatedAuditMetrics",
]
