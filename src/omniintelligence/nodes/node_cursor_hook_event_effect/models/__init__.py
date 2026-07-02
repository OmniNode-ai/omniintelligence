# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Models for Cursor Hook Event Effect node."""

# Platform-neutral output/result models reused from the Claude hook node.
from omniintelligence.nodes.node_claude_hook_event_effect.models.enum_hook_processing_status import (
    EnumHookProcessingStatus,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models.model_claude_hook_result import (
    ModelClaudeHookResult,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models.model_intent_result import (
    ModelIntentResult,
)
from omniintelligence.nodes.node_cursor_hook_event_effect.models.model_input import (
    EnumClaudeCodeHookEventType,
    EnumCursorHookEventType,
    ModelCursorHookEvent,
    ModelCursorHookEventPayload,
)

__all__ = [
    # Input models
    "EnumClaudeCodeHookEventType",
    "EnumCursorHookEventType",
    "ModelCursorHookEvent",
    "ModelCursorHookEventPayload",
    # Output/result models (platform-neutral, reused)
    "EnumHookProcessingStatus",
    "ModelClaudeHookResult",
    "ModelIntentResult",
]
