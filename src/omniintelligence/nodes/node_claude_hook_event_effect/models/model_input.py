# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Re-export Claude Code hook event types from omnibase_core.

The canonical types for Claude Code hooks are defined in omnibase_core.
This module re-exports them for convenience.

See: omnibase_core.enums.hooks.claude_code
See: omnibase_core.models.hooks.claude_code

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
    - OMN-1474: Move Claude Code hook input types to omnibase_core
"""

from omnibase_core.enums.hooks.claude_code import EnumClaudeCodeHookEventType
from omnibase_core.models.hooks.claude_code import (
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
)

__all__ = [
    "EnumClaudeCodeHookEventType",
    "ModelClaudeCodeHookEvent",
    "ModelClaudeCodeHookEventPayload",
]
