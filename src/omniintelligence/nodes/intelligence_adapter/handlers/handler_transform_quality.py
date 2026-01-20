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

    # Extract issues from violations (defensive: check for None before extending)
    if hasattr(response, "onex_compliance") and response.onex_compliance is not None:
        if (
            hasattr(response.onex_compliance, "violations")
            and response.onex_compliance.violations is not None
        ):
            issues.extend(response.onex_compliance.violations)
        if (
            hasattr(response.onex_compliance, "recommendations")
            and response.onex_compliance.recommendations is not None
        ):
            recommendations.extend(response.onex_compliance.recommendations)

    # Extract quality_score with defensive check for None/missing
    quality_score = 0.0
    if hasattr(response, "quality_score") and response.quality_score is not None:
        quality_score = response.quality_score

    # Extract onex_compliance.score with defensive check for None/missing
    onex_compliance_score = 0.0
    if hasattr(response, "onex_compliance") and response.onex_compliance is not None:
        if (
            hasattr(response.onex_compliance, "score")
            and response.onex_compliance.score is not None
        ):
            onex_compliance_score = response.onex_compliance.score

    # Extract complexity_score with defensive check for None/missing
    complexity_score = 0.0
    if hasattr(response, "maintainability") and response.maintainability is not None:
        if (
            hasattr(response.maintainability, "complexity_score")
            and response.maintainability.complexity_score is not None
        ):
            complexity_score = response.maintainability.complexity_score

    # Extract optional metadata fields
    architectural_era = None
    if hasattr(response, "architectural_era"):
        architectural_era = response.architectural_era

    temporal_relevance = None
    if hasattr(response, "temporal_relevance"):
        temporal_relevance = response.temporal_relevance

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
