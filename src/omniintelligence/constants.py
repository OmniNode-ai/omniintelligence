# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""
Shared Constants for OmniIntelligence.

This module defines constants used across multiple modules to avoid magic numbers
and improve code readability and maintainability.

Usage:
    from omniintelligence.constants import PERCENTAGE_MULTIPLIER

    hit_rate = (hits / total) * PERCENTAGE_MULTIPLIER
"""

# =============================================================================
# Percentage and Rate Calculations
# =============================================================================

PERCENTAGE_MULTIPLIER: int = 100
"""
Multiplier for converting ratios (0.0-1.0) to percentages (0-100).

Used in rate calculations such as cache hit rates, pass rates, and
completion percentages. Multiply a ratio by this constant to get a
percentage value.

Example:
    ratio = 0.75
    percentage = ratio * PERCENTAGE_MULTIPLIER  # 75.0
"""

# =============================================================================
# Pattern Matching Limits
# =============================================================================

MAX_PATTERN_MATCH_RESULTS: int = 100
"""
Maximum number of pattern match results that can be returned.

This limit prevents excessive memory usage and response sizes when
querying for pattern matches. Pattern matching operations should not
return more than this many results.

Used in:
    - ModelPatternContext.max_results validation
    - Pattern matching compute node operations
"""

# =============================================================================
# Kafka Topic Constants (TEMP_BOOTSTRAP)
# =============================================================================
# TEMP_BOOTSTRAP: These constants are temporary until runtime injection from
# contract.yaml is wired end-to-end. Delete when OMN-1546 completes.
#
# Topic naming follows ONEX convention:
#   onex.{type}.{domain}.{event-name}.{version}
#
# The dispatch engine reads canonical topics from contract.yaml and uses them
# directly (no env prefix). These constants match the contract declarations.
#
# NOTE: The TOPIC_SUFFIX_ prefix is a legacy naming artifact. The dispatch engine
# uses these as canonical topics (no prefix).
# The names will be removed entirely with OMN-1546; renaming is not worthwhile.
# =============================================================================

TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1: str = (
    "onex.cmd.omniintelligence.claude-hook-event.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for Claude Code hook events (INPUT).

Canonical topic: onex.cmd.omniintelligence.claude-hook-event.v1

omniclaude publishes Claude Code hook events to this topic.
RuntimeHostProcess routes them to NodeClaudeHookEventEffect.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_INTENT_CLASSIFIED_V1: str = (
    "onex.evt.omniintelligence.intent-classified.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for intent classification events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.intent-classified.v1

NodeClaudeHookEventEffect publishes classified intents to this topic.
omnimemory consumes for graph storage.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_STORED_V1: str = "onex.evt.omniintelligence.pattern-stored.v1"
"""
TEMP_BOOTSTRAP: Canonical topic for pattern storage events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.pattern-stored.v1

NodePatternStorageEffect publishes when a pattern is stored in the database.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_PROMOTED_V1: str = "onex.evt.omniintelligence.pattern-promoted.v1"
"""
TEMP_BOOTSTRAP: Canonical topic for pattern promotion events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.pattern-promoted.v1

NodePatternPromotionEffect publishes when a pattern is promoted
from candidate to active status based on confidence thresholds
and validation criteria.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_DEPRECATED_V1: str = (
    "onex.evt.omniintelligence.pattern-deprecated.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for pattern deprecation events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.pattern-deprecated.v1

NodePatternDemotionEffect publishes when a validated pattern is deprecated,
e.g., due to rolling-window success metrics, failure streaks, or manual disable,
subject to cooldown/threshold gates.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_TOOL_CONTENT_V1: str = "onex.cmd.omniintelligence.tool-content.v1"
"""
TEMP_BOOTSTRAP: Canonical topic for tool content events (INPUT).

Canonical topic: onex.cmd.omniintelligence.tool-content.v1

omniclaude publishes PostToolUse payloads with file contents and command
outputs to this topic. The claude hook event effect node consumes them
for intelligence analysis.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_LEARNING_CMD_V1: str = (
    "onex.cmd.omniintelligence.pattern-learning.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for pattern learning commands (INPUT).

Canonical topic: onex.cmd.omniintelligence.pattern-learning.v1

NodeClaudeHookEventEffect publishes this command when a session stops,
triggering pattern extraction in the intelligence orchestrator.

Reference: OMN-2210
Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_PROJECTION_V1: str = (
    "onex.evt.omniintelligence.pattern-projection.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for pattern projection snapshot events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.pattern-projection.v1

NodePatternProjectionEffect publishes a full materialized snapshot of all
validated patterns to this topic whenever a lifecycle change occurs
(pattern-promoted, pattern-lifecycle-transitioned).
Consumers (e.g. omniclaude) subscribe to receive the latest projection without
needing direct DB access.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_LIFECYCLE_TRANSITIONED_V1: str = (
    "onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for pattern lifecycle transition events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1

NodePatternLifecycleEffect publishes when a pattern status transition is applied,
providing the single source of truth for pattern status changes with full audit trail.

This is the unified lifecycle event that replaces individual promotion/demotion events
for comprehensive lifecycle tracking.

Reference: OMN-1805
Deletion ticket: OMN-1546
"""

TOPIC_PATTERN_LIFECYCLE_CMD_V1: str = (
    "onex.cmd.omniintelligence.pattern-lifecycle-transition.v1"
)
"""Canonical topic for pattern lifecycle transition commands (INPUT to reducer).

NodePatternPromotionEffect and NodePatternDemotionEffect publish lifecycle events
to this topic. The reducer consumes them, validates the transition against the
contract.yaml FSM, and the effect node applies the actual database update.

Reference: OMN-1805
"""

TOPIC_ROUTING_FEEDBACK_PROCESSED: str = (
    "onex.evt.omniintelligence.routing-feedback-processed.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for routing feedback processed events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.routing-feedback-processed.v1

NodeRoutingFeedbackEffect publishes after a successful upsert to
routing_feedback_scores. Consumers can use this to confirm that a routing
feedback event was fully processed.

This constant uses the canonical ONEX format (no env prefix) per OMN-2876.
Both the contract.yaml publish_topics and this Python constant use bare
canonical onex.* names — no {env}. prefix.

Reference: OMN-2366
Deletion ticket: OMN-1546
"""

# NOTE: The pattern.discovered topic string lives exclusively in
# node_pattern_storage_effect/contract.yaml (subscribe_topics).
# No Python constant is needed because RuntimeHostProcess reads
# the topic from the contract at startup.  Removed in OMN-2059 review.

TOPIC_RUN_EVALUATED_V1: str = "onex.evt.omniintelligence.run-evaluated.v1"
"""
TEMP_BOOTSTRAP: Canonical topic for objective evaluation result events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.run-evaluated.v1

NodeEvidenceCollectionEffect publishes a RunEvaluatedEvent after each agent
session is evaluated against an ObjectiveSpec. Consumers:
  - NodePolicyStateReducer (OMN-2557): Updates policy state.
  - omnidash: Displays objective scores in analytics dashboard.
  - omniintelligence audit: Stores full evaluation for replay verification.

Reference: OMN-2578
Deletion ticket: OMN-1546
"""

# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "MAX_PATTERN_MATCH_RESULTS",
    "PERCENTAGE_MULTIPLIER",
    "TOPIC_PATTERN_LIFECYCLE_CMD_V1",
    "TOPIC_ROUTING_FEEDBACK_PROCESSED",
    "TOPIC_RUN_EVALUATED_V1",
    "TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1",
    "TOPIC_SUFFIX_INTENT_CLASSIFIED_V1",
    "TOPIC_SUFFIX_PATTERN_DEPRECATED_V1",
    "TOPIC_SUFFIX_PATTERN_LEARNING_CMD_V1",
    "TOPIC_SUFFIX_PATTERN_LIFECYCLE_TRANSITIONED_V1",
    "TOPIC_SUFFIX_PATTERN_PROJECTION_V1",
    "TOPIC_SUFFIX_PATTERN_PROMOTED_V1",
    "TOPIC_SUFFIX_PATTERN_STORED_V1",
    "TOPIC_SUFFIX_TOOL_CONTENT_V1",
]
