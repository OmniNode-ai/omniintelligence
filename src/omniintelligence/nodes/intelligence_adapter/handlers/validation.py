"""Validation utilities for handler return values.

This module provides validation functions for handler transform results,
ensuring that return values conform to the expected structure and types
before being used by downstream processing.

The validation helps catch:
- Unexpected return types (not dict)
- Missing required keys
- Wrong types for scalar values (success, scores)
- Wrong types for collection values (lists, dicts)

Example:
    from omniintelligence.nodes.intelligence_adapter.handlers.validation import (
        validate_handler_result,
    )

    raw_result = transform_quality_response(api_response)
    validated = validate_handler_result(raw_result, "assess_code_quality")
    # validated is guaranteed to be a dict with all expected keys and proper types
"""

from __future__ import annotations

import logging
from typing import Any, cast

from omniintelligence.nodes.intelligence_adapter.handlers.protocols import (
    ValidatedHandlerResponse,
)

logger = logging.getLogger(__name__)


# Required keys and their expected types/defaults
REQUIRED_KEYS: dict[str, tuple[type | tuple[type, ...], Any]] = {
    "success": (bool, True),
    "quality_score": ((int, float), 0.0),
    "onex_compliance": ((int, float), 0.0),
    "complexity_score": ((int, float), 0.0),
    "issues": (list, []),
    "recommendations": (list, []),
    "patterns": (list, []),
    "result_data": (dict, {}),
}


def _safe_bool(value: Any, default: bool = True) -> bool:
    """Safely convert value to boolean.

    Args:
        value: Value to convert.
        default: Default if conversion fails.

    Returns:
        Boolean value.
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


def _safe_float(
    value: Any,
    default: float = 0.0,
    min_val: float = 0.0,
    max_val: float = 1.0,
) -> float:
    """Safely convert value to float with bounds clamping.

    Args:
        value: Value to convert.
        default: Default if conversion fails.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.

    Returns:
        Float value clamped to [min_val, max_val].
    """
    if value is None:
        return default

    try:
        float_val = float(value)
        # Clamp to valid range
        return max(min_val, min(max_val, float_val))
    except (TypeError, ValueError):
        return default


def _safe_list(value: Any) -> list[Any]:
    """Safely convert value to list.

    Args:
        value: Value to convert.

    Returns:
        List value. Empty list if None or not a list.
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
        value: Value to convert.

    Returns:
        Dict value. Empty dict if None or not a dict.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    # Can't convert non-dict to dict - return empty
    return {}


def validate_handler_result(
    result: Any,
    operation_type: str,
    *,
    log_issues: bool = True,
) -> ValidatedHandlerResponse:
    """Validate and normalize handler transform result.

    Ensures that transform handlers return valid dictionaries with expected keys
    and proper types. Provides defensive defaults if the result is None, not a
    dict, or has missing/invalid keys.

    This function is the canonical validation point for all handler return values.
    It guarantees that the returned dict has:
    - All expected keys present
    - Values of the correct types
    - Sensible defaults for missing or invalid values

    Args:
        result: Return value from a transform handler.
        operation_type: Name of the operation for error messages and logging.
        log_issues: Whether to log validation issues (default True).

    Returns:
        Validated dictionary with guaranteed structure:
        - success: bool (default True)
        - quality_score: float in [0.0, 1.0] (default 0.0)
        - onex_compliance: float in [0.0, 1.0] (default 0.0)
        - complexity_score: float in [0.0, 1.0] (default 0.0)
        - issues: list (default [])
        - recommendations: list (default [])
        - patterns: list (default [])
        - result_data: dict (default {})

    Example:
        >>> result = {"success": True, "quality_score": 0.85}
        >>> validated = validate_handler_result(result, "quality_check")
        >>> validated["success"]
        True
        >>> validated["quality_score"]
        0.85
        >>> validated["issues"]  # Default added
        []

        >>> # Handles None result
        >>> validated = validate_handler_result(None, "quality_check")
        >>> validated["success"]
        False

        >>> # Handles non-dict result
        >>> validated = validate_handler_result("unexpected", "quality_check")
        >>> validated["success"]
        True
        >>> "raw_result" in validated["result_data"]
        True
    """
    issues_found: list[str] = []

    # Handle None result
    if result is None:
        issues_found.append("result is None")
        if log_issues:
            logger.warning(
                "Handler returned None for operation '%s', using default values",
                operation_type,
            )
        return {
            "success": False,
            "quality_score": 0.0,
            "onex_compliance": 0.0,
            "complexity_score": 0.0,
            "issues": [],
            "recommendations": [],
            "patterns": [],
            "result_data": {"validation_error": "Handler returned None"},
        }

    # Handle non-dict result
    if not isinstance(result, dict):
        issues_found.append(f"result is {type(result).__name__}, expected dict")
        if log_issues:
            logger.warning(
                "Handler returned %s instead of dict for operation '%s', "
                "wrapping in result_data",
                type(result).__name__,
                operation_type,
            )
        return {
            "success": True,
            "quality_score": 0.0,
            "onex_compliance": 0.0,
            "complexity_score": 0.0,
            "issues": [],
            "recommendations": [],
            "patterns": [],
            "result_data": {"raw_result": result},
        }

    # Validate and normalize each key
    validated: dict[str, Any] = {}

    # success - must be bool
    raw_success = result.get("success")
    if raw_success is not None and not isinstance(raw_success, bool):
        issues_found.append(
            f"success is {type(raw_success).__name__}, expected bool"
        )
    validated["success"] = _safe_bool(raw_success, default=True)

    # quality_score - must be float in [0.0, 1.0]
    raw_quality = result.get("quality_score")
    if raw_quality is not None and not isinstance(raw_quality, (int, float)):
        issues_found.append(
            f"quality_score is {type(raw_quality).__name__}, expected number"
        )
    validated["quality_score"] = _safe_float(raw_quality, default=0.0)

    # onex_compliance - must be float in [0.0, 1.0]
    raw_onex = result.get("onex_compliance")
    if raw_onex is not None and not isinstance(raw_onex, (int, float)):
        issues_found.append(
            f"onex_compliance is {type(raw_onex).__name__}, expected number"
        )
    validated["onex_compliance"] = _safe_float(raw_onex, default=0.0)

    # complexity_score - must be float in [0.0, 1.0]
    raw_complexity = result.get("complexity_score")
    if raw_complexity is not None and not isinstance(raw_complexity, (int, float)):
        issues_found.append(
            f"complexity_score is {type(raw_complexity).__name__}, expected number"
        )
    validated["complexity_score"] = _safe_float(raw_complexity, default=0.0)

    # issues - must be list
    raw_issues = result.get("issues")
    if raw_issues is not None and not isinstance(raw_issues, list):
        issues_found.append(f"issues is {type(raw_issues).__name__}, expected list")
    validated["issues"] = _safe_list(raw_issues)

    # recommendations - must be list
    raw_recommendations = result.get("recommendations")
    if raw_recommendations is not None and not isinstance(raw_recommendations, list):
        issues_found.append(
            f"recommendations is {type(raw_recommendations).__name__}, expected list"
        )
    validated["recommendations"] = _safe_list(raw_recommendations)

    # patterns - must be list
    raw_patterns = result.get("patterns")
    if raw_patterns is not None and not isinstance(raw_patterns, list):
        issues_found.append(
            f"patterns is {type(raw_patterns).__name__}, expected list"
        )
    validated["patterns"] = _safe_list(raw_patterns)

    # result_data - must be dict
    raw_result_data = result.get("result_data")
    if raw_result_data is not None and not isinstance(raw_result_data, dict):
        issues_found.append(
            f"result_data is {type(raw_result_data).__name__}, expected dict"
        )
    validated["result_data"] = _safe_dict(raw_result_data)

    # Preserve any additional keys from the original result
    # (e.g., "error" key from quality handler on None response)
    for key in result:
        if key not in validated:
            validated[key] = result[key]

    # Log validation issues if any were found
    if issues_found and log_issues:
        logger.warning(
            "Validation issues for operation '%s': %s",
            operation_type,
            "; ".join(issues_found),
        )

    # Cast is safe here because we've validated all required keys are present
    # with correct types. Extra keys may be preserved but don't affect type safety.
    return cast(ValidatedHandlerResponse, validated)


__all__ = ["validate_handler_result"]
