# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Model selector module with DecisionRecord emission.

Provides ModelSelector — the primary producer of DecisionRecord events.
Every model selection emits a DecisionRecord with full scoring breakdown.

Ticket: OMN-2466
"""

from omniintelligence.model_selector.decision_emitter import (
    DecisionEmitter,
    DecisionEmitterBase,
    MockDecisionEmitter,
)
from omniintelligence.model_selector.selector import (
    CandidateScore,
    ModelSelector,
    SelectionResult,
)

__all__ = [
    "CandidateScore",
    "DecisionEmitter",
    "DecisionEmitterBase",
    "MockDecisionEmitter",
    "ModelSelector",
    "SelectionResult",
]
