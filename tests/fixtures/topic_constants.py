# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Shared topic name constants for omniintelligence tests.

This module provides topic suffix constants following ONEX naming conventions.
These constants are shared between unit and integration tests to ensure
consistency and avoid cross-layer dependencies.

Topic Naming Convention:
    {env}.{topic_suffix}

Where topic_suffix follows:
    onex.{type}.{domain}.{event-name}.{version}

Types:
    - cmd: Command/request events (inputs)
    - evt: Domain events (outputs)

Example:
    Full topic name: "test.onex.cmd.omniintelligence.claude-hook-event.v1"
    - env: "test"
    - topic_suffix: "onex.cmd.omniintelligence.claude-hook-event.v1"
"""

TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1: str = "onex.cmd.omniintelligence.claude-hook-event.v1"
"""Topic suffix for Claude Code hook events (INPUT).

Full topic: {env}.onex.cmd.omniintelligence.claude-hook-event.v1
"""

TOPIC_SUFFIX_INTENT_CLASSIFIED_V1: str = "onex.evt.omniintelligence.intent-classified.v1"
"""Topic suffix for intent classification events (OUTPUT).

Full topic: {env}.onex.evt.omniintelligence.intent-classified.v1
"""

TOPIC_SUFFIX_SESSION_OUTCOME_V1: str = "onex.cmd.omniintelligence.session-outcome.v1"
"""Topic suffix for session outcome events (INPUT).

Full topic: {env}.onex.cmd.omniintelligence.session-outcome.v1

This topic receives outcome events when Claude Code sessions complete.
Consumed by node_pattern_feedback_effect for rolling metric updates.

Reference: OMN-1763
"""

__all__ = [
    "TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1",
    "TOPIC_SUFFIX_INTENT_CLASSIFIED_V1",
    "TOPIC_SUFFIX_SESSION_OUTCOME_V1",
]
