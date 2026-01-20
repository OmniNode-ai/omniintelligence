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

from typing import Any


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
    if hasattr(response, "optimization_opportunities"):
        for opportunity in response.optimization_opportunities:
            if hasattr(opportunity, "title") and hasattr(opportunity, "description"):
                recommendations.append(
                    f"{opportunity.title}: {opportunity.description}"
                )

    # Extract complexity score from baseline metrics
    complexity_score = 0.0
    if (
        hasattr(response, "baseline_metrics")
        and response.baseline_metrics
        and hasattr(response.baseline_metrics, "complexity_estimate")
    ):
        complexity_score = response.baseline_metrics.complexity_estimate

    return {
        "success": True,
        "complexity_score": complexity_score,
        "recommendations": recommendations,
        "result_data": {
            "baseline_metrics": (
                response.baseline_metrics.model_dump()
                if hasattr(response, "baseline_metrics") and response.baseline_metrics
                else {}
            ),
            "optimization_opportunities": (
                [
                    opportunity.model_dump()
                    for opportunity in response.optimization_opportunities
                ]
                if hasattr(response, "optimization_opportunities")
                else []
            ),
            "total_opportunities": (
                response.total_opportunities
                if hasattr(response, "total_opportunities")
                else 0
            ),
            "estimated_improvement": (
                response.estimated_total_improvement
                if hasattr(response, "estimated_total_improvement")
                else 0.0
            ),
        },
    }
