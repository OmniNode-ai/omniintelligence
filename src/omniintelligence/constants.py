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
# Exports
# =============================================================================

__all__ = [
    "MAX_PATTERN_MATCH_RESULTS",
    "PERCENTAGE_MULTIPLIER",
]
