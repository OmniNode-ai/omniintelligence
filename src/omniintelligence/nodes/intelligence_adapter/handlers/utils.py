"""Shared utility functions for handler transformations.

This module provides common utility functions used across multiple handler modules
for safe type conversions and value normalization. Consolidating these utilities
eliminates code duplication and ensures consistent behavior.

Constants:
    SCORE_MIN: Minimum valid score value (0.0)
    SCORE_MAX: Maximum valid score value (1.0)
    MAX_ISSUES: Maximum number of issues to report (1000)

Functions:
    _safe_float: Safely convert value to float with bounds clamping
    _safe_bool: Safely convert value to boolean
    _safe_list: Safely convert value to list
    _safe_dict: Safely convert value to dict

Example:
    from omniintelligence.nodes.intelligence_adapter.handlers.utils import (
        _safe_float,
        _safe_bool,
        SCORE_MIN,
        SCORE_MAX,
    )

    # Convert with bounds checking
    score = _safe_float(raw_score, default=0.0, min_val=SCORE_MIN, max_val=SCORE_MAX)
"""

from __future__ import annotations

from typing import Any

# Score range constants - used for quality scores, compliance scores, etc.
SCORE_MIN: float = 0.0
SCORE_MAX: float = 1.0

# Maximum number of issues to include in results (prevents memory issues)
MAX_ISSUES: int = 1000


def _safe_float(
    value: Any,
    default: float = 0.0,
    min_val: float = SCORE_MIN,
    max_val: float = SCORE_MAX,
) -> float:
    """Safely convert value to float with bounds clamping.

    Args:
        value: Value to convert to float.
        default: Default value if conversion fails.
        min_val: Minimum allowed value (clamps below this).
        max_val: Maximum allowed value (clamps above this).

    Returns:
        Float value clamped to [min_val, max_val], or default if conversion fails.

    Example:
        >>> _safe_float(0.85)
        0.85
        >>> _safe_float(None)
        0.0
        >>> _safe_float(1.5, max_val=1.0)
        1.0
        >>> _safe_float("invalid")
        0.0
    """
    if value is None:
        return default

    try:
        float_val = float(value)
        # Clamp to valid range
        return max(min_val, min(max_val, float_val))
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool = True) -> bool:
    """Safely convert value to boolean.

    Handles various input types:
    - bool: returned as-is
    - None: returns default
    - int/float: 0 is False, non-zero is True
    - str: "true", "1", "yes" (case-insensitive) are True

    Args:
        value: Value to convert to boolean.
        default: Default value if conversion fails or value is None.

    Returns:
        Boolean value.

    Example:
        >>> _safe_bool(True)
        True
        >>> _safe_bool(1)
        True
        >>> _safe_bool("yes")
        True
        >>> _safe_bool(None, default=False)
        False
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    # For non-bool truthy/falsy values, convert explicitly
    # This handles cases like success=1 or success="true"
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    # Default to the provided default for unexpected types
    return default


def _safe_list(value: Any) -> list[Any]:
    """Safely convert value to list.

    Handles various input types:
    - None: returns empty list
    - list: returned as-is
    - tuple/set/frozenset: converted to list
    - other: wrapped in a single-element list

    Args:
        value: Value to convert to list.

    Returns:
        List value. Empty list if None.

    Example:
        >>> _safe_list(None)
        []
        >>> _safe_list([1, 2, 3])
        [1, 2, 3]
        >>> _safe_list((1, 2))
        [1, 2]
        >>> _safe_list("single")
        ['single']
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set, frozenset)):
        return list(value)
    # Single value - wrap in list
    return [value]


def _safe_dict(value: Any) -> dict[str, Any]:
    """Safely convert value to dict.

    Args:
        value: Value to convert to dict.

    Returns:
        Dict value. Empty dict if None or not a dict.

    Example:
        >>> _safe_dict(None)
        {}
        >>> _safe_dict({"key": "value"})
        {'key': 'value'}
        >>> _safe_dict("not a dict")
        {}
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    # Can't convert non-dict to dict - return empty
    return {}


__all__ = [
    "MAX_ISSUES",
    "SCORE_MAX",
    "SCORE_MIN",
    "_safe_bool",
    "_safe_dict",
    "_safe_float",
    "_safe_list",
]
