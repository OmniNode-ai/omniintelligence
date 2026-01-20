"""Handler for transforming pattern detection responses.

This handler transforms raw pattern detection responses from the intelligence
service into a canonical format suitable for event publishing and downstream
processing.

The transformation extracts:
- Detected patterns (serialized via model_dump)
- Anti-patterns as issues
- Pattern-based recommendations
- ONEX compliance from architectural compliance
- Analysis metadata (summary, confidence scores)

Example:
    from omniintelligence.nodes.intelligence_adapter.handlers import (
        transform_pattern_response,
    )

    # Transform raw API response
    result = transform_pattern_response(pattern_api_response)
    # result contains: success, onex_compliance, patterns, issues, recommendations, etc.
"""

from __future__ import annotations

from typing import Any


def transform_pattern_response(response: Any) -> dict[str, Any]:
    """Transform pattern detection response to standard format.

    This function transforms a pattern detection response from the intelligence
    service into a standardized dictionary format. It handles both object-based
    responses (with attribute access) and gracefully handles missing attributes.

    Args:
        response: Pattern detection response from intelligence service.
            Expected to have attributes:
            - detected_patterns: Optional list of pattern objects with model_dump()
            - anti_patterns: Optional list with pattern_type and description
            - recommendations: Optional iterable of recommendation strings
            - architectural_compliance: Optional object with onex_compliance score
            - analysis_summary: Optional string summary
            - confidence_scores: Optional dict of confidence values

    Returns:
        Dictionary with standardized pattern data:
        - success: Operation success status (always True if we got here)
        - onex_compliance: ONEX compliance score (0.0-1.0)
        - patterns: List of detected patterns (serialized dicts)
        - issues: List of anti-pattern issues as formatted strings
        - recommendations: List of pattern-based recommendations
        - result_data: Additional metadata (analysis_summary, confidence_scores)

    Example:
        >>> class MockPattern:
        ...     def model_dump(self):
        ...         return {"name": "singleton", "confidence": 0.9}
        >>> class MockResponse:
        ...     detected_patterns = [MockPattern()]
        ...     anti_patterns = []
        ...     recommendations = ["Use dependency injection"]
        ...     architectural_compliance = None
        ...     analysis_summary = "Good patterns detected"
        ...     confidence_scores = {"overall": 0.85}
        >>> result = transform_pattern_response(MockResponse())
        >>> result["success"]
        True
        >>> len(result["patterns"])
        1
        >>> result["recommendations"]
        ['Use dependency injection']
    """
    patterns: list[Any] = []
    issues: list[str] = []
    recommendations: list[Any] = []

    # Extract detected patterns
    if hasattr(response, "detected_patterns"):
        patterns = [pattern.model_dump() for pattern in response.detected_patterns]

    # Extract anti-patterns as issues
    if hasattr(response, "anti_patterns"):
        for anti_pattern in response.anti_patterns:
            if hasattr(anti_pattern, "pattern_type") and hasattr(
                anti_pattern, "description"
            ):
                issues.append(
                    f"{anti_pattern.pattern_type}: {anti_pattern.description}"
                )

    # Extract recommendations
    if hasattr(response, "recommendations"):
        recommendations = list(response.recommendations)

    # Extract ONEX compliance
    onex_compliance = 0.0
    if (
        hasattr(response, "architectural_compliance")
        and response.architectural_compliance
        and hasattr(response.architectural_compliance, "onex_compliance")
    ):
        onex_compliance = response.architectural_compliance.onex_compliance

    return {
        "success": True,
        "onex_compliance": onex_compliance,
        "patterns": patterns,
        "issues": issues,
        "recommendations": recommendations,
        "result_data": {
            "analysis_summary": (
                response.analysis_summary
                if hasattr(response, "analysis_summary")
                else ""
            ),
            "confidence_scores": (
                response.confidence_scores
                if hasattr(response, "confidence_scores")
                else {}
            ),
        },
    }
