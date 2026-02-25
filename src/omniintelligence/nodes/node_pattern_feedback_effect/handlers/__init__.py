# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handlers for node_pattern_feedback_effect.

This module exports handler functions for the pattern feedback effect node,
which records session outcomes and updates pattern rolling metrics.

Handler Pattern:
    Each handler is an async function that:
    - Accepts a repository protocol for database operations
    - Performs pattern feedback recording with rolling window updates
    - Returns typed result models
    - Delegates I/O to the injected repository

Rolling Window Metrics:
    The session outcome handler updates rolling_20 counters that approximate
    the last 20 injections using decay logic. See handler_session_outcome.py
    for the decay approximation algorithm.

Contribution Heuristics:
    When recording outcomes, contribution heuristics are computed to attribute
    session outcomes to individual patterns. See heuristics.py for the pure
    functions that compute weights.

Usage:
    from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
        ProtocolPatternRepository,
        record_session_outcome,
        update_pattern_rolling_metrics,
        apply_heuristic,
    )

    # Record outcome and update metrics (includes heuristic computation)
    result = await record_session_outcome(
        session_id=uuid,
        success=True,
        repository=db_connection,
        heuristic_method=EnumHeuristicMethod.EQUAL_SPLIT,
    )

Reference:
    - OMN-1679: FEEDBACK-004 contribution heuristic for outcome attribution
    - OMN-1678: Rolling window metric updates with decay approximation
    - OMN-1677: Pattern feedback effect node foundation
"""

from omniintelligence.nodes.node_pattern_feedback_effect.handlers.handler_attribution_binder import (
    AttributionBindingResult,
    BindSessionResult,
    compute_evidence_tier,
    handle_attribution_binding,
)
from omniintelligence.nodes.node_pattern_feedback_effect.handlers.handler_session_outcome import (
    ROLLING_WINDOW_SIZE,
    compute_and_store_heuristics,
    event_to_handler_args,
    record_session_outcome,
    update_effectiveness_scores,
    update_pattern_rolling_metrics,
)
from omniintelligence.nodes.node_pattern_feedback_effect.handlers.heuristics import (
    ContributionWeights,
    apply_heuristic,
    compute_equal_split,
    compute_first_match,
    compute_recency_weighted,
)

__all__ = [
    "AttributionBindingResult",
    "BindSessionResult",
    "ROLLING_WINDOW_SIZE",
    "ContributionWeights",
    "apply_heuristic",
    "handle_attribution_binding",
    "compute_and_store_heuristics",
    "compute_equal_split",
    "compute_evidence_tier",
    "compute_first_match",
    "compute_recency_weighted",
    "event_to_handler_args",
    "record_session_outcome",
    "update_effectiveness_scores",
    "update_pattern_rolling_metrics",
]
