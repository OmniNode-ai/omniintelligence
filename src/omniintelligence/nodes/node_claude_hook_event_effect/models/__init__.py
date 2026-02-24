# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Models for Claude Hook Event Effect node.

This module exports all models used by the NodeClaudeHookEventEffect,
including input, output, and supporting models.

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
"""

from omniintelligence.nodes.node_claude_hook_event_effect.models.enum_hook_processing_status import (
    EnumHookProcessingStatus,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models.enum_kafka_emission_status import (
    EnumKafkaEmissionStatus,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models.model_claude_hook_result import (
    ModelClaudeHookResult,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models.model_input import (
    EnumClaudeCodeHookEventType,
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models.model_intent_result import (
    ModelIntentResult,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models.model_pattern_learning_command import (
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
