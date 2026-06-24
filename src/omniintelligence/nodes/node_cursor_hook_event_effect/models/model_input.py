# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input models for the Cursor Hook Event Effect node.

Cursor's canonical input types live in ``omnibase_core`` (peer to Claude Code's
hook models) and are re-exported here so the node and its contract can reference
a node-local module path. ``EnumClaudeCodeHookEventType`` is re-exported too
because Cursor events are mapped onto the canonical Claude lifecycle (via
``EnumCursorHookEventType.to_claude_equivalent``) before the shared intelligence
pipeline processes them.
"""

from __future__ import annotations

from omnibase_core.enums.hooks.claude_code.enum_claude_code_hook_event_type import (
    EnumClaudeCodeHookEventType,
)
from omnibase_core.enums.hooks.cursor.enum_cursor_hook_event_type import (
    EnumCursorHookEventType,
)
from omnibase_core.models.hooks.cursor.model_cursor_hook_event import (
    ModelCursorHookEvent,
)
from omnibase_core.models.hooks.cursor.model_cursor_hook_event_payload import (
    ModelCursorHookEventPayload,
)

__all__ = [
    "EnumClaudeCodeHookEventType",
    "EnumCursorHookEventType",
    "ModelCursorHookEvent",
    "ModelCursorHookEventPayload",
]
