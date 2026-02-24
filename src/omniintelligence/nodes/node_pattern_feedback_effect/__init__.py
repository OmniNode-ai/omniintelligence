# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Pattern Feedback Effect node - OMN-1678.

This node records session outcomes and updates rolling window metrics
for pattern learning feedback loops.

Architecture:
    - Declarative effect node (100% contract-driven)
    - Handler functions with explicit protocol dependencies
    - External DI: callers provide repository protocol to handlers

Related Tickets:
    - OMN-1678: Rolling window metric updates for session outcomes
    - OMN-1757: Refactor to declarative pattern
"""

from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
    ROLLING_WINDOW_SIZE,
    record_session_outcome,
    update_pattern_rolling_metrics,
)
from omniintelligence.nodes.node_pattern_feedback_effect.models import (
    ClaudeCodeSessionOutcome,
    ClaudeSessionOutcome,
    EnumOutcomeRecordingStatus,
    ModelSessionOutcomeResult,
    SessionOutcomeInput,
)
from omniintelligence.nodes.node_pattern_feedback_effect.node import (
    NodePatternFeedbackEffect,
)

__all__ = [
    "ROLLING_WINDOW_SIZE",
    "ClaudeCodeSessionOutcome",
    "ClaudeSessionOutcome",
    "EnumOutcomeRecordingStatus",
    "ModelSessionOutcomeResult",
    "NodePatternFeedbackEffect",
    "SessionOutcomeInput",
    "record_session_outcome",
    "update_pattern_rolling_metrics",
]
