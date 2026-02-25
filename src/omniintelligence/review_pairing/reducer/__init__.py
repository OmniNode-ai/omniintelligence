# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern Candidate Reducer: cluster, promote, and lifecycle state machine.

Public API:

    from omniintelligence.review_pairing.reducer import (
        PatternLifecycleState,
        PatternClusterKey,
        PatternCandidate,
        PromotionGateResult,
        PatternCandidateReducer,
    )

Reference: OMN-2568
"""

from omniintelligence.review_pairing.reducer.reducer import (
    PatternCandidate,
    PatternCandidateReducer,
    PatternClusterKey,
    PatternLifecycleState,
    PromotionGateResult,
)

__all__ = [
    "PatternCandidate",
    "PatternCandidateReducer",
    "PatternClusterKey",
    "PatternLifecycleState",
    "PromotionGateResult",
]
