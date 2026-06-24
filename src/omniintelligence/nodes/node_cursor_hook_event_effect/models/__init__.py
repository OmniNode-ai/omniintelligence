# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Models for Cursor Hook Event Effect node.

Cursor's canonical input types (ModelCursorHookEvent, EnumCursorHookEventType)
are defined in omnibase_core and re-exported here. The processing result and
intent models are platform-neutral and reused from the Claude hook node to keep
the two dispatchers interchangeable without duplicating output schemas.
"""

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
    # Input models (canonical from omnibase_core)
    "EnumClaudeCodeHookEventType",
    "EnumCursorHookEventType",
    "ModelCursorHookEvent",
    "ModelCursorHookEventPayload",
    # Output/result models (platform-neutral, reused)
    "EnumHookProcessingStatus",
    "ModelClaudeHookResult",
    "ModelIntentResult",
]
