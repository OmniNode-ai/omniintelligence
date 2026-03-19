# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Model selector module with DecisionRecord and episode event emission.

Provides ModelSelector — the primary producer of DecisionRecord events
and RL episode boundary events (OMN-5559).

Every model selection emits a DecisionRecord with full scoring breakdown
and an episode_started event capturing the pre-action observation.

Tickets: OMN-2466, OMN-5559
"""

from omniintelligence.model_selector.decision_emitter import (
    DecisionEmitter,
    DecisionEmitterBase,
    MockDecisionEmitter,
)
from omniintelligence.model_selector.episode_emitter import (
    EpisodeEmitter,
    EpisodeEmitterBase,
    MockEpisodeEmitter,
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
    "EpisodeEmitter",
    "EpisodeEmitterBase",
    "MockDecisionEmitter",
    "MockEpisodeEmitter",
    "ModelSelector",
    "SelectionResult",
]
