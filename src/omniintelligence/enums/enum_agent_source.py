# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Agent source for hook-derived intelligence events."""

from __future__ import annotations

from enum import Enum, unique


@unique
class EnumAgentSource(str, Enum):
    """Frontend dispatcher that produced a hook event."""

    CLAUDE = "claude"
    CURSOR = "cursor"


__all__ = ["EnumAgentSource"]
