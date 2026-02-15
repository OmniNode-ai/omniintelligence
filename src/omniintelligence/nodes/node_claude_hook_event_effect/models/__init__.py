# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Models for Claude Hook Event Effect node.

This module exports all models used by the NodeClaudeHookEventEffect,
including input, output, and supporting models.

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
"""

from omniintelligence.nodes.node_claude_hook_event_effect.models.model_input import (
    EnumClaudeCodeHookEventType,
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models.model_output import (
    EnumHookProcessingStatus,
    EnumKafkaEmissionStatus,
    ModelClaudeHookResult,
    ModelIntentResult,
    ModelPatternLearningCommand,
)

__all__ = [
    # Input models (canonical from omnibase_core)
    "EnumClaudeCodeHookEventType",
    # Output models (local to omniintelligence)
    "EnumHookProcessingStatus",
    "EnumKafkaEmissionStatus",
    "ModelClaudeCodeHookEvent",
    "ModelClaudeCodeHookEventPayload",
    "ModelClaudeHookResult",
    "ModelIntentResult",
    "ModelPatternLearningCommand",
]
