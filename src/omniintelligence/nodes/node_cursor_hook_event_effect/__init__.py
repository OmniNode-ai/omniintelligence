# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Cursor Hook Event Effect node.

Exports the dedicated Cursor IDE hook event handler node and its supporting
models and handlers. Cursor is a first-class peer to Claude Code: it consumes
its own ``cursor-hook-event.v1`` topic with its own ModelCursorHookEvent input,
so Cursor events are processed as Cursor events (not Claude events) while reusing
the shared intelligence pipeline for interchangeable behavior.
"""

from omniintelligence.nodes.node_cursor_hook_event_effect.handlers import (
    HandlerCursorHookEvent,
    route_cursor_hook_event,
)
from omniintelligence.nodes.node_cursor_hook_event_effect.models import (
    EnumCursorHookEventType,
    ModelClaudeHookResult,
    ModelCursorHookEvent,
    ModelCursorHookEventPayload,
)
from omniintelligence.nodes.node_cursor_hook_event_effect.node import (
    NodeCursorHookEventEffect,
)

__all__ = [
    "EnumCursorHookEventType",
    "HandlerCursorHookEvent",
    "ModelClaudeHookResult",
    "ModelCursorHookEvent",
    "ModelCursorHookEventPayload",
    "NodeCursorHookEventEffect",
    "route_cursor_hook_event",
]
