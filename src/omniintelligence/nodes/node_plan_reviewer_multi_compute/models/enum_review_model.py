# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
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
    """LLM model identifiers for the multi-LLM plan reviewer.

    Each value matches a row in ``plan_reviewer_model_accuracy`` seeded
    by migration 020.

    Attributes:
        QWEN3_CODER: Qwen3-Coder model (code-optimized, long context).
        DEEPSEEK_R1: DeepSeek-R1 reasoning model (deep analysis).
        GEMINI_FLASH: Gemini Flash model (fast, balanced).
        GLM_4: GLM-4 model (multilingual, general purpose).

    Example:
        >>> from omniintelligence.nodes.node_plan_reviewer_multi_compute.models import (
        ...     EnumReviewModel,
        ... )
        >>> model = EnumReviewModel.QWEN3_CODER
        >>> assert model.value == "qwen3-coder"

    Note:
        Values match the ``model_id`` column in
        ``plan_reviewer_model_accuracy`` (migration 020).
        If you add a value here, add a corresponding INSERT to the migration.
    """

    QWEN3_CODER = "qwen3-coder"
    DEEPSEEK_R1 = "deepseek-r1"
    GEMINI_FLASH = "gemini-flash"
    GLM_4 = "glm-4"


__all__ = ["EnumReviewModel"]
