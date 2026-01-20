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

    # Extract detected patterns with defensive model_dump handling
    detected_patterns = getattr(response, "detected_patterns", None) or []
    for pattern in detected_patterns:
        try:
            if hasattr(pattern, "model_dump") and callable(pattern.model_dump):
                patterns.append(pattern.model_dump())
            elif hasattr(pattern, "dict") and callable(pattern.dict):
                # Fallback for older Pydantic v1 models
                patterns.append(pattern.dict())
            elif isinstance(pattern, dict):
                # Already a dict, use as-is
                patterns.append(pattern)
            else:
                # Last resort: convert to dict if possible, or wrap in dict
                patterns.append({"raw_pattern": str(pattern)})
        except Exception as e:
            # Catch all exceptions from serialization to avoid failing the entire
            # transformation due to one malformed pattern
            patterns.append({"error": f"Failed to serialize pattern: {e}"})

    # Extract anti-patterns as issues with defensive attribute access
    anti_patterns = getattr(response, "anti_patterns", None) or []
    for anti_pattern in anti_patterns:
        pattern_type = getattr(anti_pattern, "pattern_type", None)
        description = getattr(anti_pattern, "description", None)
        if pattern_type and description:
            issues.append(f"{pattern_type}: {description}")
        elif pattern_type:
            issues.append(f"{pattern_type}: (no description)")
        elif description:
            issues.append(f"Unknown anti-pattern: {description}")
        # Skip anti-patterns with neither pattern_type nor description

    # Extract recommendations with safe iteration
    raw_recommendations = getattr(response, "recommendations", None)
    if raw_recommendations is not None:
        try:
            recommendations = list(raw_recommendations)
        except TypeError:
            # Not iterable - wrap single value or convert to string
            if raw_recommendations:
                recommendations = [str(raw_recommendations)]

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
