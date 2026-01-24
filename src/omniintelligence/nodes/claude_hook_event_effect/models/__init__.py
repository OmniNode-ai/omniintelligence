# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Models for Claude Hook Event Effect node.

This module exports all models used by the NodeClaudeHookEventEffect,
including input, output, and supporting models.

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
"""

from omniintelligence.nodes.claude_hook_event_effect.models.model_input import (
    # Canonical names from omnibase_core
    EnumClaudeCodeHookEventType,
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
    # Backward compatibility aliases
    EnumClaudeHookEventType,
    ModelClaudeHookEvent,
)
from omniintelligence.nodes.claude_hook_event_effect.models.model_output import (
    EnumHookProcessingStatus,
    ModelClaudeHookResult,
    ModelIntentResult,
)

__all__ = [
    # Input models (canonical from omnibase_core)
    "EnumClaudeCodeHookEventType",
    # Input models (backward compatibility aliases)
    "EnumClaudeHookEventType",
    # Output models (local to omniintelligence)
    "EnumHookProcessingStatus",
    "ModelClaudeCodeHookEvent",
    "ModelClaudeCodeHookEventPayload",
    "ModelClaudeHookEvent",
    "ModelClaudeHookResult",
    "ModelIntentResult",
]
