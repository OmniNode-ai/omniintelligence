# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input models for node_pattern_feedback_effect.

This module re-exports the canonical input type for the pattern feedback effect node.
The input is ClaudeSessionOutcome from omnibase_core, which represents the shared
schema for session outcome events across the platform.
"""

from omnibase_core.integrations.claude_code import (
    ClaudeCodeSessionOutcome,
    ClaudeSessionOutcome,
)

# Canonical input type for event-driven consumption
SessionOutcomeInput = ClaudeSessionOutcome


__all__ = [
    "ClaudeCodeSessionOutcome",  # Enum re-export
    "ClaudeSessionOutcome",  # Canonical input type
    "SessionOutcomeInput",  # Alias for ClaudeSessionOutcome
]
