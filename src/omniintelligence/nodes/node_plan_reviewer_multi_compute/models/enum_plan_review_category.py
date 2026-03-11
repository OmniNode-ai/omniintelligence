# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Review category enum for NodePlanReviewerMultiCompute.

Defines the R1-R6 plan review categories used by all four review strategies.
These map to the R1-R6 behavioral spec in the writing-plans skill (omniclaude PR #412).

Ticket: OMN-3288
"""

from __future__ import annotations

from enum import Enum


class EnumPlanReviewCategory(str, Enum):
    """Plan review categories (R1-R6) for the multi-LLM plan reviewer.

    Each value corresponds to one aspect of plan quality being evaluated.

    Attributes:
        R1_COUNTS: Step/task count accuracy — correct number of items.
        R2_ACCEPTANCE_CRITERIA: Acceptance criteria coverage and quality.
        R3_SCOPE: Scope definition and boundary clarity.
        R4_INTEGRATION_TRAPS: Integration risks and correctness proofs.
        R5_IDEMPOTENCY: Idempotency and reproducibility of operations.
        R6_VERIFICATION: Verification and testability of outcomes.

    Example:
        >>> from omniintelligence.nodes.node_plan_reviewer_multi_compute.models import (
        ...     EnumPlanReviewCategory,
        ... )
        >>> cat = EnumPlanReviewCategory.R1_COUNTS
        >>> assert cat.value == "R1_counts"

    Note:
        Values match the ``category`` field in ``PlanReviewFinding``.
        The specialist_split strategy assigns categories to specific models
        based on domain strength (see plan doc 2026-02-28-plan-reviewer-multi-llm.md).
    """

    R1_COUNTS = "R1_counts"
    R2_ACCEPTANCE_CRITERIA = "R2_acceptance_criteria"
    R3_SCOPE = "R3_scope"
    R4_INTEGRATION_TRAPS = "R4_integration_traps"
    R5_IDEMPOTENCY = "R5_idempotency"
    R6_VERIFICATION = "R6_verification"


__all__ = ["EnumPlanReviewCategory"]
