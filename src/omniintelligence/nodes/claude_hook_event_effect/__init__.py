# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Claude Hook Event Effect node.

This module exports the unified Claude Code hook event handler node and
its supporting models.

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
"""

from omniintelligence.nodes.claude_hook_event_effect.models import (
    EnumClaudeHookEventType,
    EnumHookProcessingStatus,
    ModelClaudeHookEvent,
    ModelClaudeHookResult,
    ModelIntentResult,
)
from omniintelligence.nodes.claude_hook_event_effect.node import (
    NodeClaudeHookEventEffect,
)

__all__ = [
    # Input models
    "EnumClaudeHookEventType",
    # Output models
    "EnumHookProcessingStatus",
    "ModelClaudeHookEvent",
    "ModelClaudeHookResult",
    "ModelIntentResult",
    # Node
    "NodeClaudeHookEventEffect",
]
