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


def transform_quality_response(response: Any) -> dict[str, Any]:
    """Transform quality assessment response to standard format.

    This function transforms a quality assessment response from the intelligence
    service into a standardized dictionary format. It handles both object-based
    responses (with attribute access) and gracefully handles missing attributes.

    Args:
        response: Quality assessment response from intelligence service.
            Expected to have attributes:
            - quality_score: float (0.0-1.0)
            - onex_compliance: Optional object with score, violations, recommendations
            - maintainability: Optional object with complexity_score
            - architectural_era: Optional string
            - temporal_relevance: Optional float

    Returns:
        Dictionary with standardized quality data:
        - success: Operation success status (always True if we got here)
        - quality_score: Overall quality score (0.0-1.0)
        - onex_compliance: ONEX compliance score (0.0-1.0)
        - complexity_score: Complexity score from maintainability
        - issues: List of identified issues from violations
        - recommendations: List of recommendations
        - patterns: Empty list (reserved for pattern data)
        - result_data: Additional metadata (architectural_era, temporal_relevance)

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
    """
    issues: list[Any] = []
    recommendations: list[Any] = []

    # Extract issues from violations
    if hasattr(response, "onex_compliance") and response.onex_compliance:
        if hasattr(response.onex_compliance, "violations"):
            issues.extend(response.onex_compliance.violations)
        if hasattr(response.onex_compliance, "recommendations"):
            recommendations.extend(response.onex_compliance.recommendations)

    return {
        "success": True,
        "quality_score": (
            response.quality_score
            if hasattr(response, "quality_score")
            else 0.0
        ),
        "onex_compliance": (
            response.onex_compliance.score
            if hasattr(response, "onex_compliance") and response.onex_compliance
            else 0.0
        ),
        "complexity_score": (
            response.maintainability.complexity_score
            if hasattr(response, "maintainability") and response.maintainability
            else 0.0
        ),
        "issues": issues,
        "recommendations": recommendations,
        "patterns": [],
        "result_data": {
            "architectural_era": (
                response.architectural_era
                if hasattr(response, "architectural_era")
                else None
            ),
            "temporal_relevance": (
                response.temporal_relevance
                if hasattr(response, "temporal_relevance")
                else None
            ),
        },
    }
