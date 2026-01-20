"""Handler for transforming performance analysis responses.

This handler transforms raw performance analysis responses from the intelligence
service into a canonical format suitable for event publishing and downstream
processing.

The transformation extracts:
- Complexity score from baseline metrics
- Recommendations from optimization opportunities
- Baseline metrics and improvement estimates

Example:
    from omniintelligence.nodes.intelligence_adapter.handlers import (
        transform_performance_response,
    )

    # Transform raw API response
    result = transform_performance_response(performance_api_response)
    # result contains: success, complexity_score, recommendations, result_data
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from typing import Any


def _ensure_list(value: Any) -> list[Any]:
    """Convert a value to a list safely.

    Handles None, iterables, and single objects gracefully.

    Args:
        value: Any value to convert to a list.

    Returns:
        A list containing the value(s). Empty list if None.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Strings are iterable but should not be expanded
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    # Single non-iterable object
    return [value]


def transform_performance_response(response: Any) -> dict[str, Any]:
    """Transform performance analysis response to standard format.

    This function transforms a performance analysis response from the intelligence
    service into a standardized dictionary format. It handles both object-based
    responses (with attribute access) and gracefully handles missing attributes.

    Args:
        response: Performance analysis response from intelligence service.
            Expected to have attributes:
            - baseline_metrics: Optional object with complexity_estimate, model_dump()
            - optimization_opportunities: Optional list of objects with title,
              description, and model_dump()
            - total_opportunities: Optional int count of opportunities
            - estimated_total_improvement: Optional float improvement estimate

    Returns:
        Dictionary with standardized performance data:
        - success: Operation success status (always True if we got here)
        - complexity_score: Complexity estimate from baseline metrics (0.0 default)
        - recommendations: List of recommendation strings from optimization
          opportunities formatted as "{title}: {description}"
        - result_data: Additional metadata containing:
            - baseline_metrics: Dict from model_dump() or empty dict
            - optimization_opportunities: List of dicts from model_dump()
            - total_opportunities: Int count of opportunities
            - estimated_improvement: Float improvement estimate

    Example:
        >>> class MockMetrics:
        ...     complexity_estimate = 0.7
        ...     def model_dump(self):
        ...         return {"complexity_estimate": 0.7}
        >>> class MockOpportunity:
        ...     title = "Cache results"
        ...     description = "Add caching to reduce latency"
        ...     def model_dump(self):
        ...         return {"title": self.title, "description": self.description}
        >>> class MockResponse:
        ...     baseline_metrics = MockMetrics()
        ...     optimization_opportunities = [MockOpportunity()]
        ...     total_opportunities = 1
        ...     estimated_total_improvement = 0.25
        >>> result = transform_performance_response(MockResponse())
        >>> result["complexity_score"]
        0.7
        >>> result["recommendations"]
        ['Cache results: Add caching to reduce latency']
        >>> result["success"]
        True
    """
    recommendations: list[str] = []

    # Extract optimization opportunities as recommendation strings
    # Guard: Ensure we have an iterable list, never None or non-iterable
    raw_opportunities = getattr(response, "optimization_opportunities", None)
    opportunities = _ensure_list(raw_opportunities)

    for opportunity in opportunities:
        # Guard: Skip None or non-object entries
        if opportunity is None:
            continue
        title = getattr(opportunity, "title", None)
        description = getattr(opportunity, "description", None)
        if title is not None and description is not None:
            recommendations.append(f"{title}: {description}")

    # Extract complexity score from baseline metrics
    # Guard: Ensure baseline_metrics exists and has the expected attribute
    baseline_metrics = getattr(response, "baseline_metrics", None)
    raw_complexity = (
        getattr(baseline_metrics, "complexity_estimate", None)
        if baseline_metrics is not None
        else None
    )
    # Guard: Ensure complexity_score is numeric, default to 0.0
    complexity_score = (
        float(raw_complexity)
        if raw_complexity is not None and isinstance(raw_complexity, int | float)
        else 0.0
    )

    # Build opportunity dicts with safe model_dump access
    opportunity_dicts: list[dict[str, Any]] = []
    for opportunity in opportunities:
        if opportunity is None:
            continue
        if hasattr(opportunity, "model_dump") and callable(
            getattr(opportunity, "model_dump", None)
        ):
            with contextlib.suppress(TypeError, AttributeError):
                opportunity_dicts.append(opportunity.model_dump())

    # Build baseline_metrics dict with safe model_dump access
    baseline_metrics_dict: dict[str, Any] = {}
    if baseline_metrics is not None:
        if hasattr(baseline_metrics, "model_dump") and callable(
            getattr(baseline_metrics, "model_dump", None)
        ):
            with contextlib.suppress(TypeError, AttributeError):
                baseline_metrics_dict = baseline_metrics.model_dump()

    # Extract total_opportunities with type guard
    raw_total = getattr(response, "total_opportunities", None)
    total_opportunities = (
        int(raw_total)
        if raw_total is not None and isinstance(raw_total, int | float)
        else 0
    )

    # Extract estimated_improvement with type guard
    raw_improvement = getattr(response, "estimated_total_improvement", None)
    estimated_improvement = (
        float(raw_improvement)
        if raw_improvement is not None and isinstance(raw_improvement, int | float)
        else 0.0
    )

    return {
        "success": True,
        "complexity_score": complexity_score,
        "recommendations": recommendations,
        "result_data": {
            "baseline_metrics": baseline_metrics_dict,
            "optimization_opportunities": opportunity_dicts,
            "total_opportunities": total_opportunities,
            "estimated_improvement": estimated_improvement,
        },
    }
