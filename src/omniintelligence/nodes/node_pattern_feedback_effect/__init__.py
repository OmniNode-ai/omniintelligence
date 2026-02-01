# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Feedback Effect node - OMN-1678.

This node records session outcomes and updates rolling window metrics
for pattern learning feedback loops.

Architecture:
    - Thin shell effect node (declarative pattern)
    - Registry-based dependency injection
    - Handler functions with explicit dependencies
"""

from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
    ROLLING_WINDOW_SIZE,
    ProtocolPatternRepository,
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
from omniintelligence.nodes.node_pattern_feedback_effect.registry import (
    RegistryPatternFeedbackEffect,
)

__all__ = [
    # Constants
    "ROLLING_WINDOW_SIZE",
    # Models (input re-exported from omnibase_core)
    "ClaudeCodeSessionOutcome",
    "ClaudeSessionOutcome",
    "SessionOutcomeInput",
    # Models (output)
    "EnumOutcomeRecordingStatus",
    "ModelSessionOutcomeResult",
    # Node
    "NodePatternFeedbackEffect",
    # Handlers
    "ProtocolPatternRepository",
    "record_session_outcome",
    "update_pattern_rolling_metrics",
    # Registry
    "RegistryPatternFeedbackEffect",
]
