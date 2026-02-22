# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Model selector module with DecisionRecord emission.

Provides ModelSelector — the primary consumer of DecisionRecord events.
Every model selection emits a DecisionRecord with full scoring breakdown.

Ticket: OMN-2466
"""

from omniintelligence.model_selector.decision_emitter import DecisionEmitter
from omniintelligence.model_selector.selector import CandidateScore, ModelSelector

__all__ = [
    "CandidateScore",
    "DecisionEmitter",
    "ModelSelector",
]
