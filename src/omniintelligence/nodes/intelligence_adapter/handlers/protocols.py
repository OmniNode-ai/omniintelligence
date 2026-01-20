"""Type protocols and TypedDicts for handler response objects.

This module defines type-safe structures for handler transform results,
enabling static type checking with mypy and improved IDE support.

The type system uses TypedDict for dictionary return values, which allows
mypy to validate that handler functions return properly structured responses.

Design Decisions:
    - TypedDict is used instead of Protocol because handlers return dicts,
      not objects with methods. TypedDict provides exact dictionary typing.
    - Required vs Optional: Base fields are required (success, result_data),
      domain-specific fields are optional to allow partial responses.
    - NotRequired is used for fields that may be absent (Python 3.11+).
    - Union types are used for result_data to accommodate different handlers.

Usage:
    from omniintelligence.nodes.intelligence_adapter.handlers.protocols import (
        QualityHandlerResponse,
        PerformanceHandlerResponse,
        PatternHandlerResponse,
        ValidatedHandlerResponse,
    )

    def transform_quality_response(response: Any) -> QualityHandlerResponse:
        # Type checker validates return structure
        return {
            "success": True,
            "quality_score": 0.85,
            ...
        }

Example:
    >>> from omniintelligence.nodes.intelligence_adapter.handlers.protocols import (
    ...     QualityHandlerResponse,
    ... )
    >>> def check_quality(data: QualityHandlerResponse) -> bool:
    ...     return data["success"] and data["quality_score"] > 0.8
    >>> result: QualityHandlerResponse = {
    ...     "success": True,
    ...     "quality_score": 0.9,
    ...     "onex_compliance": 0.85,
    ...     "complexity_score": 0.7,
    ...     "issues": [],
    ...     "recommendations": [],
    ...     "patterns": [],
    ...     "result_data": {},
    ... }
    >>> check_quality(result)
    True
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


# =============================================================================
# Result Data Sub-structures
# =============================================================================


class QualityResultData(TypedDict, total=False):
    """Result data structure for quality assessment responses.

    Contains additional metadata from quality assessment operations.

    Attributes:
        architectural_era: Detected architectural era/style of the code.
        temporal_relevance: Time-based relevance score (0.0-1.0).
    """

    architectural_era: str | None
    temporal_relevance: float | None


class PerformanceBaselineMetrics(TypedDict, total=False):
    """Baseline metrics from performance analysis.

    Contains performance baseline measurements.

    Attributes:
        complexity_estimate: Estimated complexity score.
        Additional fields may be present from model_dump().
    """

    complexity_estimate: float


class PerformanceOpportunity(TypedDict, total=False):
    """Individual optimization opportunity.

    Attributes:
        title: Short title of the optimization.
        description: Detailed description of the opportunity.
        Additional fields may be present from model_dump().
    """

    title: str
    description: str


class PerformanceResultData(TypedDict, total=False):
    """Result data structure for performance analysis responses.

    Contains detailed performance analysis metadata.

    Attributes:
        baseline_metrics: Dict containing baseline performance metrics.
        optimization_opportunities: List of optimization opportunity dicts.
        total_opportunities: Count of identified optimization opportunities.
        estimated_improvement: Estimated total improvement percentage.
    """

    baseline_metrics: dict[str, Any]
    optimization_opportunities: list[dict[str, Any]]
    total_opportunities: int
    estimated_improvement: float


class PatternResultData(TypedDict, total=False):
    """Result data structure for pattern detection responses.

    Contains pattern analysis metadata.

    Attributes:
        analysis_summary: Human-readable summary of the analysis.
        confidence_scores: Dict mapping pattern names to confidence scores.
    """

    analysis_summary: str
    confidence_scores: dict[str, Any]


# =============================================================================
# Base Handler Response
# =============================================================================


class BaseHandlerResponse(TypedDict, total=False):
    """Base protocol for all handler transform responses.

    Defines the common structure shared by all handler responses.
    All handlers should return at minimum these fields.

    Required Attributes:
        success: Whether the operation completed successfully.

    Optional Attributes:
        error: Error message if operation failed (present when success=False).
        result_data: Additional operation-specific metadata.

    Note:
        Using total=False allows partial responses during construction,
        but the validate_handler_result function ensures all required
        fields are present before downstream processing.
    """

    success: bool
    error: NotRequired[str]
    result_data: dict[str, Any]


# =============================================================================
# Handler-Specific Response Types
# =============================================================================


class QualityHandlerResponse(TypedDict, total=False):
    """Response type for quality assessment transform handler.

    Contains quality scores, compliance information, and identified issues
    from code quality assessment operations.

    Required Attributes:
        success: Whether the quality assessment completed successfully.

    Score Attributes (all 0.0-1.0 range):
        quality_score: Overall code quality score.
        onex_compliance: ONEX architectural compliance score.
        complexity_score: Code complexity score from maintainability analysis.

    Collection Attributes:
        issues: List of identified quality issues/violations.
        recommendations: List of improvement recommendations.
        patterns: List of detected patterns (typically empty for quality).

    Metadata Attributes:
        result_data: QualityResultData with architectural metadata.
        error: Error message if success=False.

    Example:
        >>> response: QualityHandlerResponse = {
        ...     "success": True,
        ...     "quality_score": 0.85,
        ...     "onex_compliance": 0.90,
        ...     "complexity_score": 0.75,
        ...     "issues": ["Missing docstring", "Long function"],
        ...     "recommendations": ["Add type hints"],
        ...     "patterns": [],
        ...     "result_data": {
        ...         "architectural_era": "modern",
        ...         "temporal_relevance": 0.95,
        ...     },
        ... }
    """

    # Required
    success: bool

    # Scores (0.0-1.0 range)
    quality_score: float
    onex_compliance: float
    complexity_score: float

    # Collections
    issues: list[Any]
    recommendations: list[Any]
    patterns: list[Any]

    # Metadata
    result_data: QualityResultData | dict[str, Any]

    # Optional error
    error: NotRequired[str]


class PerformanceHandlerResponse(TypedDict, total=False):
    """Response type for performance analysis transform handler.

    Contains performance metrics, optimization opportunities, and
    recommendations from performance analysis operations.

    Required Attributes:
        success: Whether the performance analysis completed successfully.

    Score Attributes:
        complexity_score: Complexity estimate from baseline metrics.

    Collection Attributes:
        recommendations: List of optimization recommendation strings
            formatted as "{title}: {description}".

    Metadata Attributes:
        result_data: PerformanceResultData with detailed metrics.

    Example:
        >>> response: PerformanceHandlerResponse = {
        ...     "success": True,
        ...     "complexity_score": 0.7,
        ...     "recommendations": [
        ...         "Add caching: Implement Redis cache for API calls",
        ...         "Use lazy loading: Defer initialization until needed",
        ...     ],
        ...     "result_data": {
        ...         "baseline_metrics": {"complexity_estimate": 0.7},
        ...         "optimization_opportunities": [...],
        ...         "total_opportunities": 5,
        ...         "estimated_improvement": 0.25,
        ...     },
        ... }
    """

    # Required
    success: bool

    # Scores
    complexity_score: float

    # Collections
    recommendations: list[str]

    # Metadata
    result_data: PerformanceResultData | dict[str, Any]


class PatternHandlerResponse(TypedDict, total=False):
    """Response type for pattern detection transform handler.

    Contains detected patterns, anti-patterns (as issues), and
    architectural compliance information.

    Required Attributes:
        success: Whether the pattern detection completed successfully.

    Score Attributes:
        onex_compliance: ONEX architectural compliance score (0.0-1.0).

    Collection Attributes:
        patterns: List of detected pattern dicts (from model_dump()).
        issues: List of anti-pattern issue strings formatted as
            "{pattern_type}: {description}".
        recommendations: List of pattern-based recommendations.

    Metadata Attributes:
        result_data: PatternResultData with analysis summary.

    Example:
        >>> response: PatternHandlerResponse = {
        ...     "success": True,
        ...     "onex_compliance": 0.85,
        ...     "patterns": [
        ...         {"name": "singleton", "confidence": 0.9},
        ...         {"name": "factory", "confidence": 0.75},
        ...     ],
        ...     "issues": ["God object: Class handles too many responsibilities"],
        ...     "recommendations": ["Consider dependency injection"],
        ...     "result_data": {
        ...         "analysis_summary": "Found 2 design patterns, 1 anti-pattern",
        ...         "confidence_scores": {"overall": 0.85},
        ...     },
        ... }
    """

    # Required
    success: bool

    # Scores
    onex_compliance: float

    # Collections
    patterns: list[Any]
    issues: list[str]
    recommendations: list[Any]

    # Metadata
    result_data: PatternResultData | dict[str, Any]


class ValidatedHandlerResponse(TypedDict):
    """Fully validated handler response structure.

    This TypedDict represents the guaranteed structure after validation
    by validate_handler_result(). All fields are required and have
    guaranteed types.

    Unlike the handler-specific responses (which use total=False),
    this type uses total=True (the default) because validation
    ensures all fields are present.

    Attributes:
        success: Whether the operation completed successfully.
        quality_score: Quality score (0.0-1.0), default 0.0.
        onex_compliance: ONEX compliance score (0.0-1.0), default 0.0.
        complexity_score: Complexity score (0.0-1.0), default 0.0.
        issues: List of identified issues, default [].
        recommendations: List of recommendations, default [].
        patterns: List of detected patterns, default [].
        result_data: Additional metadata dict, default {}.

    Note:
        Additional keys may be present (e.g., "error") as validation
        preserves extra keys from the original response.

    Example:
        >>> from omniintelligence.nodes.intelligence_adapter.handlers import (
        ...     validate_handler_result,
        ... )
        >>> raw_result = {"success": True, "quality_score": 0.85}
        >>> validated: ValidatedHandlerResponse = validate_handler_result(
        ...     raw_result, "quality_check"
        ... )
        >>> validated["success"]
        True
        >>> validated["issues"]  # Guaranteed to be present
        []
    """

    success: bool
    quality_score: float
    onex_compliance: float
    complexity_score: float
    issues: list[Any]
    recommendations: list[Any]
    patterns: list[Any]
    result_data: dict[str, Any]


# =============================================================================
# Type Aliases for Flexibility
# =============================================================================

# Union type for any handler response (useful for generic processing)
AnyHandlerResponse = (
    QualityHandlerResponse
    | PerformanceHandlerResponse
    | PatternHandlerResponse
    | ValidatedHandlerResponse
)

# Union type for result_data structures
AnyResultData = (
    QualityResultData
    | PerformanceResultData
    | PatternResultData
    | dict[str, Any]
)


__all__ = [
    "AnyHandlerResponse",
    "AnyResultData",
    "BaseHandlerResponse",
    "PatternHandlerResponse",
    "PatternResultData",
    "PerformanceBaselineMetrics",
    "PerformanceHandlerResponse",
    "PerformanceOpportunity",
    "PerformanceResultData",
    "QualityHandlerResponse",
    "QualityResultData",
    "ValidatedHandlerResponse",
]
