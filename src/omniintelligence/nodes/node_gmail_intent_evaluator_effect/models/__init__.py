# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Models for Gmail Intent Evaluator Effect node.

Reference:
    - OMN-2788: Add ModelGmailIntentEvaluatorConfig + ModelGmailIntentEvaluationResult
"""

from omniintelligence.nodes.node_gmail_intent_evaluator_effect.models.model_gmail_intent_evaluation_result import (
    ModelGmailIntentEvaluationResult,
    ModelMemoryHit,
)
from omniintelligence.nodes.node_gmail_intent_evaluator_effect.models.model_gmail_intent_evaluator_config import (
    ModelGmailIntentEvaluatorConfig,
)

__all__ = [
    "ModelGmailIntentEvaluationResult",
    "ModelGmailIntentEvaluatorConfig",
    "ModelMemoryHit",
]
