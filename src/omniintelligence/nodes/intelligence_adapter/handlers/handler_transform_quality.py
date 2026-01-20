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
    HandlerValidationError,
    MAX_ISSUES,
    SCORE_MAX,
    SCORE_MIN,
    _get_optional_field,
    _require_field,
    _require_float,
    _safe_list,
)


def transform_quality_response(response: Any) -> QualityHandlerResponse:
    """Transform quality assessment response to standard format.

    Fail-fast validation: This function raises HandlerValidationError if
    required fields are missing or have invalid types. We don't silently
    degrade with defaults - API contract violations should be caught immediately.

    Args:
        response: Quality assessment response from intelligence service.
            Can be an object or dict. Required fields:
            - quality_score: float (0.0-1.0) - REQUIRED
            - onex_compliance: object/dict - REQUIRED, with:
                - score: float (0.0-1.0) - REQUIRED
                - violations: list - REQUIRED (can be empty)
                - recommendations: list - REQUIRED (can be empty)
            - maintainability: object/dict - REQUIRED, with:
                - complexity_score: float (0.0-1.0) - REQUIRED
            Optional fields:
            - architectural_era: Optional string
            - temporal_relevance: Optional float

    Returns:
        Dictionary with standardized quality data.

    Raises:
        HandlerValidationError: If response is None or required fields are
            missing/invalid. Fail-fast behavior to catch API issues early.

    Example:
        >>> class MockResponse:
        ...     quality_score = 0.85
        ...     onex_compliance = {"score": 0.9, "violations": [], "recommendations": []}
        ...     maintainability = {"complexity_score": 0.7}
        >>> result = transform_quality_response(MockResponse())
        >>> result["quality_score"]
        0.85

        >>> # None response raises - fail fast!
        >>> transform_quality_response(None)
        HandlerValidationError: Response is None - cannot transform quality assessment
    """
    # Fail fast: None response is an API contract violation
    if response is None:
        raise HandlerValidationError(
            "Response is None - cannot transform quality assessment"
        )

    # REQUIRED: quality_score must exist and be numeric
    raw_quality_score = _require_field(response, "quality_score", "response")
    quality_score = _require_float(raw_quality_score, "quality_score", SCORE_MIN, SCORE_MAX)

    # REQUIRED: onex_compliance must exist
    onex_compliance_obj = _require_field(response, "onex_compliance", "response")

    # REQUIRED: onex_compliance.score must exist and be numeric
    raw_compliance_score = _require_field(onex_compliance_obj, "score", "onex_compliance")
    onex_compliance_score = _require_float(raw_compliance_score, "onex_compliance.score", SCORE_MIN, SCORE_MAX)

    # REQUIRED: violations and recommendations must exist (can be empty lists)
    raw_violations = _require_field(onex_compliance_obj, "violations", "onex_compliance")
    raw_recommendations = _require_field(onex_compliance_obj, "recommendations", "onex_compliance")

    # Convert to lists and apply security limits
    violations = _safe_list(raw_violations)
    recommendations_list = _safe_list(raw_recommendations)

    issues: list[Any] = violations[:MAX_ISSUES]
    recommendations: list[Any] = recommendations_list[:MAX_ISSUES]

    # REQUIRED: maintainability must exist
    maintainability_obj = _require_field(response, "maintainability", "response")

    # REQUIRED: complexity_score must exist and be numeric
    raw_complexity_score = _require_field(maintainability_obj, "complexity_score", "maintainability")
    complexity_score = _require_float(raw_complexity_score, "maintainability.complexity_score", SCORE_MIN, SCORE_MAX)

    # OPTIONAL: architectural_era and temporal_relevance
    architectural_era = _get_optional_field(response, "architectural_era")
    temporal_relevance_raw = _get_optional_field(response, "temporal_relevance")
    temporal_relevance = (
        _require_float(temporal_relevance_raw, "temporal_relevance", SCORE_MIN, SCORE_MAX)
        if temporal_relevance_raw is not None
        else None
    )

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
