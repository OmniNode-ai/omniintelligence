# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Review strategy enum for NodePlanReviewerMultiCompute.

Defines the four multi-LLM review strategies. The strategy value is stored
in the ``strategy`` column of ``plan_reviewer_strategy_runs`` (migration 020).

Ticket: OMN-3284

Note:
    Values are frozen. Any addition or rename requires:
    1. A new DB migration to update the ``strategy`` column CHECK constraint
       (if one is added in future).
    2. A version bump on the node contract.
"""

from __future__ import annotations

from enum import Enum


class EnumReviewStrategy(str, Enum):
    """Multi-LLM review strategy.

    Strategies determine how multiple model outputs are combined into a
    single review verdict.

    Attributes:
        S1_PANEL_VOTE: All models review independently; majority vote
            determines the final verdict. Equal weight per model.
        S2_SPECIALIST_SPLIT: Each model reviews a different category
            subset; results are merged without voting.
        S3_SEQUENTIAL_CRITIQUE: Models review in sequence; each model
            sees prior findings and may critique or confirm them.
        S4_INDEPENDENT_MERGE: All models review independently; findings
            are union-merged without vote aggregation.

    Example:
        >>> from omniintelligence.nodes.node_plan_reviewer_multi_compute.models import (
        ...     EnumReviewStrategy,
        ... )
        >>> strategy = EnumReviewStrategy.S1_PANEL_VOTE
        >>> assert strategy.value == "panel_vote"

    Note:
        Values match the ``strategy`` column in
        ``plan_reviewer_strategy_runs`` (migration 020).
    """

    S1_PANEL_VOTE = "panel_vote"
    S2_SPECIALIST_SPLIT = "specialist_split"
    S3_SEQUENTIAL_CRITIQUE = "sequential_critique"
    S4_INDEPENDENT_MERGE = "independent_merge"


__all__ = ["EnumReviewStrategy"]
