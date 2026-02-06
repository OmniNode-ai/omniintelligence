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
# Kafka Topic Suffixes (TEMP_BOOTSTRAP)
# =============================================================================
# TEMP_BOOTSTRAP: These constants are temporary until runtime injection from
# contract.yaml is wired. Delete when OMN-1546 completes.
#
# Topic naming follows ONEX convention:
#   {env}.onex.{type}.{domain}.{event-name}.{version}
#
# These constants define the SUFFIX (everything after env prefix).
# Full topic is constructed as: f"{env_prefix}.{suffix}"
# =============================================================================

TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1: str = (
    "onex.cmd.omniintelligence.claude-hook-event.v1"
)
"""
TEMP_BOOTSTRAP: Topic suffix for Claude Code hook events (INPUT).

Full topic at runtime: {env}.onex.cmd.omniintelligence.claude-hook-event.v1

omniclaude publishes Claude Code hook events to this topic.
RuntimeHostProcess routes them to NodeClaudeHookEventEffect.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_INTENT_CLASSIFIED_V1: str = (
    "onex.evt.omniintelligence.intent-classified.v1"
)
"""
TEMP_BOOTSTRAP: Topic suffix for intent classification events (OUTPUT).

Full topic at runtime: {env}.onex.evt.omniintelligence.intent-classified.v1

NodeClaudeHookEventEffect publishes classified intents to this topic.
omnimemory consumes for graph storage.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_STORED_V1: str = "onex.evt.omniintelligence.pattern-stored.v1"
"""
TEMP_BOOTSTRAP: Topic suffix for pattern storage events (OUTPUT).

Full topic at runtime: {env}.onex.evt.omniintelligence.pattern-stored.v1

NodePatternStorageEffect publishes when a pattern is stored in the database.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_PROMOTED_V1: str = "onex.evt.omniintelligence.pattern-promoted.v1"
"""
TEMP_BOOTSTRAP: Topic suffix for pattern promotion events (OUTPUT).

Full topic at runtime: {env}.onex.evt.omniintelligence.pattern-promoted.v1

NodePatternStorageEffect publishes when a pattern is promoted
to validated status based on rolling window success metrics.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_DEPRECATED_V1: str = (
    "onex.evt.omniintelligence.pattern-deprecated.v1"
)
"""
TEMP_BOOTSTRAP: Topic suffix for pattern deprecation events (OUTPUT).

Full topic at runtime: {env}.onex.evt.omniintelligence.pattern-deprecated.v1

NodePatternDemotionEffect publishes when a validated pattern is deprecated,
e.g., due to rolling-window success metrics, failure streaks, or manual disable,
subject to cooldown/threshold gates.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_LIFECYCLE_TRANSITIONED_V1: str = (
    "onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1"
)
"""
TEMP_BOOTSTRAP: Topic suffix for pattern lifecycle transition events (OUTPUT).

Full topic at runtime: {env}.onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1

NodePatternLifecycleEffect publishes when a pattern status transition is applied,
providing the single source of truth for pattern status changes with full audit trail.

This is the unified lifecycle event that replaces individual promotion/demotion events
for comprehensive lifecycle tracking.

Reference: OMN-1805
Deletion ticket: OMN-1546
"""

# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "MAX_PATTERN_MATCH_RESULTS",
    "PERCENTAGE_MULTIPLIER",
    "TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1",
    "TOPIC_SUFFIX_INTENT_CLASSIFIED_V1",
    "TOPIC_SUFFIX_PATTERN_DEPRECATED_V1",
    "TOPIC_SUFFIX_PATTERN_LIFECYCLE_TRANSITIONED_V1",
    "TOPIC_SUFFIX_PATTERN_PROMOTED_V1",
    "TOPIC_SUFFIX_PATTERN_STORED_V1",
]
