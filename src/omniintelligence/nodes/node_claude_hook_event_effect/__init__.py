# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Claude Hook Event Effect node.

This module exports the unified Claude Code hook event handler node and
its supporting models.

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
"""

from omniintelligence.nodes.node_claude_hook_event_effect.handlers import (
    HandlerClaudeHookEvent,
    ProtocolIntentClassifier,
    ProtocolKafkaPublisher,
    route_hook_event,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models import (
    EnumClaudeCodeHookEventType,
    EnumHookProcessingStatus,
    ModelClaudeCodeHookEvent,
    ModelClaudeHookResult,
    ModelIntentResult,
)
from omniintelligence.nodes.node_claude_hook_event_effect.node import (
    NodeClaudeHookEventEffect,
)
from omniintelligence.nodes.node_claude_hook_event_effect.registry import (
    RegistryClaudeHookEventEffect,
)

__all__ = [
    # Input models (canonical from omnibase_core)
    "EnumClaudeCodeHookEventType",
    # Output models
    "EnumHookProcessingStatus",
    "ModelClaudeCodeHookEvent",
    "ModelClaudeHookResult",
    "ModelIntentResult",
    # Handler and protocols
    "HandlerClaudeHookEvent",
    "ProtocolIntentClassifier",
    "ProtocolKafkaPublisher",
    "route_hook_event",
    # Node
    "NodeClaudeHookEventEffect",
    # Registry
    "RegistryClaudeHookEventEffect",
]
