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

__all__ = [
    "TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1",
    "TOPIC_SUFFIX_INTENT_CLASSIFIED_V1",
]
