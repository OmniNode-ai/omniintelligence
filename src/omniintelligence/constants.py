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

TOPIC_SUFFIX_INTENT_CLASSIFIED_V1: str = "onex.evt.omniintelligence.intent-classified.v1"
"""
TEMP_BOOTSTRAP: Topic suffix for intent classification events.

Full topic at runtime: {env}.onex.evt.omniintelligence.intent-classified.v1

This constant is temporary (OMN-1539). When runtime injection from contract.yaml
is wired, this will be removed and the topic will be resolved from:
  - contract.yaml published_events[].topic_suffix
  - Runtime config provides env prefix

Deletion ticket: OMN-1546
"""

# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "MAX_PATTERN_MATCH_RESULTS",
    "PERCENTAGE_MULTIPLIER",
    "TOPIC_SUFFIX_INTENT_CLASSIFIED_V1",
]
