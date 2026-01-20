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

from omniintelligence.nodes.intelligence_adapter.handlers.protocols import (
    PatternHandlerResponse,
)
from omniintelligence.nodes.intelligence_adapter.handlers.utils import MAX_ISSUES


def transform_pattern_response(response: Any | None) -> PatternHandlerResponse:
    """Transform pattern detection response to standard format.

    This function transforms a pattern detection response from the intelligence
    service into a standardized dictionary format. It handles both object-based
    responses (with attribute access) and gracefully handles missing attributes.

    All optional fields are accessed defensively with sensible defaults to prevent
    AttributeError or KeyError at runtime.

    Args:
        response: Pattern detection response from intelligence service, or None.
            Expected to have optional attributes:
            - detected_patterns: Optional list of pattern objects with model_dump()
            - anti_patterns: Optional list with pattern_type and description
            - recommendations: Optional iterable of recommendation strings
            - architectural_compliance: Optional object with onex_compliance score
            - analysis_summary: Optional string summary
            - confidence_scores: Optional dict of confidence values

    Returns:
        Dictionary with standardized pattern data:
        - success: Operation success status (True if response exists)
        - onex_compliance: ONEX compliance score (0.0-1.0, defaults to 0.0)
        - patterns: List of detected patterns (serialized dicts, empty if none)
        - issues: List of anti-pattern issues as formatted strings (empty if none)
        - recommendations: List of pattern-based recommendations (empty if none)
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
        >>> # Also handles None response gracefully
        >>> result = transform_pattern_response(None)
        >>> result["success"]
        False
        >>> result["patterns"]
        []
    """
    # Handle None response gracefully - return empty result structure
    if response is None:
        return {
            "success": False,
            "onex_compliance": 0.0,
            "patterns": [],
            "issues": [],
            "recommendations": [],
            "result_data": {
                "analysis_summary": "",
                "confidence_scores": {},
            },
        }

    patterns: list[Any] = []
    issues: list[str] = []
    recommendations: list[Any] = []

    # Extract detected patterns with defensive model_dump handling
    # Security: Apply MAX_ISSUES limit to prevent memory exhaustion from
    # malicious or buggy API responses returning millions of items.
    detected_patterns = getattr(response, "detected_patterns", None) or []
    for pattern in detected_patterns:
        # Security: Stop collecting if we hit the limit
        if len(patterns) >= MAX_ISSUES:
            break
        # Skip None items in the list
        if pattern is None:
            continue
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
        except (AttributeError, TypeError) as e:
            # AttributeError: method doesn't exist; TypeError: method not callable
            # or wrong arguments - these are structural issues with the pattern object
            patterns.append({"error": f"Pattern serialization error (type/attribute): {e}"})
        except ValueError as e:
            # ValueError from model_dump() or dict() due to invalid field values
            patterns.append({"error": f"Pattern serialization error (value): {e}"})
        except Exception as e:
            # Intentionally broad: catch any other serialization error to avoid
            # failing the entire transformation due to one malformed pattern.
            # Logs the full error type for debugging.
            patterns.append({
                "error": f"Failed to serialize pattern ({type(e).__name__}): {e}"
            })

    # Extract anti-patterns as issues with defensive attribute/dict access
    # Security: Apply MAX_ISSUES limit to prevent memory exhaustion
    anti_patterns = getattr(response, "anti_patterns", None) or []
    for anti_pattern in anti_patterns:
        # Security: Stop collecting if we hit the limit
        if len(issues) >= MAX_ISSUES:
            break
        # Skip None items in the list
        if anti_pattern is None:
            continue

        # Handle both object-style (getattr) and dict-style (.get) access
        if isinstance(anti_pattern, dict):
            pattern_type = anti_pattern.get("pattern_type")
            description = anti_pattern.get("description")
        else:
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
    # Security: Apply MAX_ISSUES limit to prevent memory exhaustion
    raw_recommendations = getattr(response, "recommendations", None)
    if raw_recommendations is not None:
        try:
            recommendations = list(raw_recommendations)[:MAX_ISSUES]
        except TypeError:
            # Not iterable - wrap single value or convert to string
            if raw_recommendations:
                recommendations = [str(raw_recommendations)]

    # Extract ONEX compliance with safe access and type coercion
    onex_compliance = 0.0
    arch_compliance = getattr(response, "architectural_compliance", None)
    if arch_compliance is not None:
        # Handle both object-style and dict-style access
        if isinstance(arch_compliance, dict):
            raw_compliance = arch_compliance.get("onex_compliance")
        else:
            raw_compliance = getattr(arch_compliance, "onex_compliance", None)

        # Safely convert to float, defaulting to 0.0 on any error
        if raw_compliance is not None:
            try:
                onex_compliance = float(raw_compliance)
            except (TypeError, ValueError):
                # Non-numeric value, keep default of 0.0
                onex_compliance = 0.0

    # Extract analysis metadata with safe defaults for None values
    analysis_summary = getattr(response, "analysis_summary", None)
    if analysis_summary is None:
        analysis_summary = ""
    elif not isinstance(analysis_summary, str):
        # Coerce non-string values to string
        analysis_summary = str(analysis_summary)

    confidence_scores = getattr(response, "confidence_scores", None)
    if confidence_scores is None:
        confidence_scores = {}
    elif not isinstance(confidence_scores, dict):
        # Wrap non-dict values in a dict
        confidence_scores = {"raw_value": confidence_scores}

    return {
        "success": True,
        "onex_compliance": onex_compliance,
        "patterns": patterns,
        "issues": issues,
        "recommendations": recommendations,
        "result_data": {
            "analysis_summary": analysis_summary,
            "confidence_scores": confidence_scores,
        },
    }
