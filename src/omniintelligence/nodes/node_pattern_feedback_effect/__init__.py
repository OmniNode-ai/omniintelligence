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
    EnumOutcomeRecordingStatus,
    ModelSessionOutcomeRequest,
    ModelSessionOutcomeResult,
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
    # Models
    "EnumOutcomeRecordingStatus",
    "ModelSessionOutcomeRequest",
    "ModelSessionOutcomeResult",
    # Node
    "NodePatternFeedbackEffect",
    # Handlers
    "ProtocolPatternRepository",
    # Registry
    "RegistryPatternFeedbackEffect",
    "record_session_outcome",
    "update_pattern_rolling_metrics",
]
