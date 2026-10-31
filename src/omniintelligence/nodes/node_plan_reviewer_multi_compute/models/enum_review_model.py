# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Review model enum for NodePlanReviewerMultiCompute.

Defines the four LLM model identifiers used by the multi-LLM plan reviewer.
Values are stored in the ``model_id`` column of ``plan_reviewer_model_accuracy``
and in the ``models_used`` array of ``plan_reviewer_strategy_runs``
(migration 020).

Ticket: OMN-3284

Note:
    Values are frozen. Adding a new model requires:
    1. A new INSERT into ``plan_reviewer_model_accuracy`` (via migration or
       seed script) with a default score_correctness of 0.5.
    2. A version bump on the node contract.
"""

from __future__ import annotations

from enum import Enum


class EnumReviewModel(str, Enum):
    """Reviewer slot identifiers for the multi-LLM plan reviewer.

    Each value matches a row in ``plan_reviewer_model_accuracy`` seeded
    by migration 020 and renamed to slot names by migration 029.

    Attributes:
        CODE_DRAFTER: Code-optimized, long-context slot (drafter).
        DEEP_REASONER: Reasoning slot (deep analysis, critic).
        FAST_REVIEWER: Fast, balanced slot.
        TIEBREAKER: Multilingual, general-purpose slot.

    Example:
        >>> from omniintelligence.nodes.node_plan_reviewer_multi_compute.models import (
        ...     EnumReviewModel,
        ... )
        >>> model = EnumReviewModel.CODE_DRAFTER
        >>> assert model.value == "code-drafter"

    Note:
        A value names a reviewer slot, not a model: the model that fills a slot
        is bound by the deployment overlay, so code names no model.
        Values match the ``model_id`` column in
        ``plan_reviewer_model_accuracy`` (migration 020).
        If you add a value here, add a corresponding INSERT to the migration.
    """

    CODE_DRAFTER = "code-drafter"
    DEEP_REASONER = "deep-reasoner"
    FAST_REVIEWER = "fast-reviewer"
    TIEBREAKER = "tiebreaker"


__all__ = ["EnumReviewModel"]
