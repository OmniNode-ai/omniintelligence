"""Handler for transforming quality assessment responses.

This handler transforms raw quality assessment responses from the intelligence
service into a canonical format suitable for event publishing and downstream
processing.

The transformation extracts:
- Quality scores (overall, ONEX compliance, complexity)
- Issues from violations
- Recommendations
- Architectural metadata

Example:
    from omniintelligence.nodes.intelligence_adapter.handlers import (
        transform_quality_response,
    )

    # Transform raw API response
    result = transform_quality_response(quality_api_response)
    # result contains: success, quality_score, onex_compliance, issues, etc.
"""

from __future__ import annotations

from typing import Any

from omniintelligence.nodes.intelligence_adapter.handlers.protocols import (
    QualityHandlerResponse,
)
from omniintelligence.nodes.intelligence_adapter.handlers.utils import (
    MAX_ISSUES,
    SCORE_MAX,
    SCORE_MIN,
    _safe_float,
    _safe_list,
)


def _get_attr_or_key(obj: Any, name: str, default: Any = None) -> Any:
    """Get attribute or key from object or dict with default.

    Supports both object-based responses (with attribute access) and
    dict-based responses (with key access).

    Args:
        obj: Object or dict to extract value from.
        name: Attribute name or dict key to access.
        default: Default value if not found or None.

    Returns:
        The value if found and not None, otherwise the default.
    """
    if obj is None:
        return default

    # Try dict-style access first (more common in API responses)
    if isinstance(obj, dict):
        value = obj.get(name)
        return value if value is not None else default

    # Fall back to attribute access
    if hasattr(obj, name):
        value = getattr(obj, name, None)
        return value if value is not None else default

    return default


def transform_quality_response(response: Any) -> QualityHandlerResponse:
    """Transform quality assessment response to standard format.

    This function transforms a quality assessment response from the intelligence
    service into a standardized dictionary format. It handles both object-based
    responses (with attribute access) and dict-based responses (with key access),
    gracefully handling missing or malformed data.

    Args:
        response: Quality assessment response from intelligence service.
            Can be an object or dict. Expected to have:
            - quality_score: float (0.0-1.0)
            - onex_compliance: Optional object/dict with score, violations, recommendations
            - maintainability: Optional object/dict with complexity_score
            - architectural_era: Optional string
            - temporal_relevance: Optional float

    Returns:
        Dictionary with standardized quality data:
        - success: Operation success status (False if response is None/invalid)
        - quality_score: Overall quality score (0.0-1.0, default 0.0)
        - onex_compliance: ONEX compliance score (0.0-1.0, default 0.0)
        - complexity_score: Complexity score from maintainability (0.0-1.0, default 0.0)
        - issues: List of identified issues from violations
        - recommendations: List of recommendations
        - patterns: Empty list (reserved for pattern data)
        - result_data: Additional metadata (architectural_era, temporal_relevance)
        - error: Error message if response was invalid (only present on failure)

    Example:
        >>> class MockResponse:
        ...     quality_score = 0.85
        ...     onex_compliance = None
        ...     maintainability = None
        >>> result = transform_quality_response(MockResponse())
        >>> result["quality_score"]
        0.85
        >>> result["success"]
        True

        >>> # Handles None response gracefully
        >>> result = transform_quality_response(None)
        >>> result["success"]
        False
        >>> "error" in result
        True
    """
    # Defensive check: Handle None or completely invalid response
    if response is None:
        return {
            "success": False,
            "quality_score": 0.0,
            "onex_compliance": 0.0,
            "complexity_score": 0.0,
            "issues": [],
            "recommendations": [],
            "patterns": [],
            "result_data": {},
            "error": "Response is None - cannot transform quality assessment",
        }

    issues: list[Any] = []
    recommendations: list[Any] = []

    # Extract onex_compliance object/dict (supports both object and dict responses)
    onex_compliance_obj = _get_attr_or_key(response, "onex_compliance")

    # Extract issues from violations with comprehensive defensive checks
    # Security: Apply MAX_ISSUES limit to prevent memory exhaustion
    if onex_compliance_obj is not None:
        violations = _safe_list(_get_attr_or_key(onex_compliance_obj, "violations"))
        remaining_issues = MAX_ISSUES - len(issues)
        if remaining_issues > 0:
            issues.extend(violations[:remaining_issues])

        recs = _safe_list(_get_attr_or_key(onex_compliance_obj, "recommendations"))
        remaining_recs = MAX_ISSUES - len(recommendations)
        if remaining_recs > 0:
            recommendations.extend(recs[:remaining_recs])

    # Extract quality_score with type safety and range validation
    # _safe_float handles: None, missing, non-numeric types, out-of-range values
    raw_quality_score = _get_attr_or_key(response, "quality_score")
    quality_score = _safe_float(raw_quality_score, default=SCORE_MIN, min_val=SCORE_MIN, max_val=SCORE_MAX)

    # Extract onex_compliance.score with defensive checks
    raw_compliance_score = _get_attr_or_key(onex_compliance_obj, "score") if onex_compliance_obj else None
    onex_compliance_score = _safe_float(raw_compliance_score, default=SCORE_MIN, min_val=SCORE_MIN, max_val=SCORE_MAX)

    # Extract complexity_score from maintainability with defensive checks
    maintainability_obj = _get_attr_or_key(response, "maintainability")
    raw_complexity_score = _get_attr_or_key(maintainability_obj, "complexity_score") if maintainability_obj else None
    complexity_score = _safe_float(raw_complexity_score, default=SCORE_MIN, min_val=SCORE_MIN, max_val=SCORE_MAX)

    # Extract optional metadata fields (no type conversion needed)
    architectural_era = _get_attr_or_key(response, "architectural_era")
    temporal_relevance_raw = _get_attr_or_key(response, "temporal_relevance")
    # temporal_relevance should be a float if present
    temporal_relevance = _safe_float(temporal_relevance_raw, default=SCORE_MIN, min_val=SCORE_MIN, max_val=SCORE_MAX) if temporal_relevance_raw is not None else None

    return {
        "success": True,
        "quality_score": quality_score,
        "onex_compliance": onex_compliance_score,
        "complexity_score": complexity_score,
        "issues": issues,
        "recommendations": recommendations,
        "patterns": [],
        "result_data": {
            "architectural_era": architectural_era,
            "temporal_relevance": temporal_relevance,
        },
    }
