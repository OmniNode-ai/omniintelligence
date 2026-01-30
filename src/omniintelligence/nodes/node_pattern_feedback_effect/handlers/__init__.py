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

Usage:
    from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
        ProtocolPatternRepository,
        record_session_outcome,
        update_pattern_rolling_metrics,
    )

    # Record outcome and update metrics
    result = await record_session_outcome(
        session_id=uuid,
        success=True,
        repository=db_connection,
    )

Reference:
    - OMN-1678: Rolling window metric updates with decay approximation
    - OMN-1677: Pattern feedback effect node foundation
"""

from omniintelligence.nodes.node_pattern_feedback_effect.handlers.handler_session_outcome import (
    ROLLING_WINDOW_SIZE,
    ProtocolPatternRepository,
    record_session_outcome,
    update_pattern_rolling_metrics,
)

__all__ = [
    "ROLLING_WINDOW_SIZE",
    "ProtocolPatternRepository",
    "record_session_outcome",
    "update_pattern_rolling_metrics",
]
