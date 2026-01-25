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
# Kafka Topic Constants (ONEX Naming Convention)
# =============================================================================
# These constants follow the ONEX topic naming convention:
#   {env}.onex.{type}.{domain}.{event-name}.{version}
#
# Where:
#   - {env}: Environment prefix injected at runtime (dev, staging, prod)
#   - onex: Platform identifier
#   - {type}: evt (events) or cmd (commands)
#   - {domain}: Service domain (e.g., omniintelligence)
#   - {event-name}: Hyphenated event name
#   - {version}: Schema version
#
# IMPORTANT: These constants are TEMPORARY local definitions.
# When OMN-1537 lands, they will be imported from omnibase_core.topics.
# See OMN-1546 for the follow-up cleanup ticket.
# =============================================================================

ONEX_EVT_OMNIINTELLIGENCE_INTENT_CLASSIFIED_V1: str = (
    "onex.evt.omniintelligence.intent-classified.v1"
)
"""
Topic for intent classification events emitted by claude_hook_event_effect.

Full topic at runtime: {env}.onex.evt.omniintelligence.intent-classified.v1

Consumers:
    - omnimemory: Stores intent classifications in graph for session context

Event schema includes:
    - session_id: Claude Code session identifier
    - correlation_id: Distributed tracing ID
    - intent_category: Classified intent (e.g., code_generation, debugging)
    - confidence: Classification confidence score
    - timestamp: Event timestamp

Migration Note:
    This constant is a temporary local definition (OMN-1539).
    When OMN-1537 lands in omnibase_core, import from:
        from omnibase_core.topics.onex_intent_topics import (
            ONEX_EVT_OMNIINTELLIGENCE_INTENT_CLASSIFIED_V1,
        )
    See OMN-1546 for cleanup.
"""

# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "MAX_PATTERN_MATCH_RESULTS",
    "ONEX_EVT_OMNIINTELLIGENCE_INTENT_CLASSIFIED_V1",
    "PERCENTAGE_MULTIPLIER",
]
