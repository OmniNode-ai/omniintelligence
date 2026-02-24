# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Injection context enum for pattern injection tracking.

Ticket: OMN-1670
"""

from enum import Enum


class EnumInjectionContext(str, Enum):
    """Valid contexts where pattern injection can occur.

    This is a subset of Claude Code hook event types, limited to the
    lifecycle points where pattern injection is semantically valid.

    Attributes:
        SESSION_START: Injection at session initialization
        USER_PROMPT_SUBMIT: Injection when user submits a prompt
        PRE_TOOL_USE: Injection before tool execution
        SUBAGENT_START: Injection when a subagent spawns

    Example:
        >>> from omniintelligence.enums import EnumInjectionContext
        >>> context = EnumInjectionContext.SESSION_START
        >>> assert context.value == "SessionStart"

    Note:
        Values match the CHECK constraint in migration 007_create_pattern_injections.sql.
        If you add values here, update the SQL constraint too.

    See Also:
        - omnibase_core.enums.hooks.claude_code.EnumClaudeCodeHookEventType
        - deployment/database/migrations/007_create_pattern_injections.sql
    """

    SESSION_START = "SessionStart"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    PRE_TOOL_USE = "PreToolUse"
    SUBAGENT_START = "SubagentStart"


__all__ = ["EnumInjectionContext"]
