"""Type protocols for quality scoring handler results.

This module defines TypedDict structures for type-safe handler responses,
enabling static type checking with mypy and improved IDE support.

Design Decisions:
    - TypedDict is used because handlers return dicts, not objects with methods.
    - All scores are normalized to 0.0-1.0 range for consistency.
    - Required fields use total=True (default) for strict validation.
    - DimensionScores provides type-safe dimension field access.

Usage:
    from omniintelligence.nodes.quality_scoring_compute.handlers.protocols import (
        DimensionScores,
        QualityScoringResult,
    )

    def score_code_quality(...) -> QualityScoringResult:
        return {
            "success": True,
            "quality_score": 0.85,
            ...
        }
"""

from __future__ import annotations

from typing import TypedDict


class DimensionScores(TypedDict):
    """Individual dimension scores for quality scoring.

    All six dimensions are required and must be in the 0.0-1.0 range.

    Attributes:
        complexity: Cyclomatic complexity score (inverted - lower complexity is better).
        maintainability: Code structure and naming convention score.
        documentation: Docstring and comment coverage score.
        temporal_relevance: Code freshness score based on staleness indicators.
        patterns: ONEX pattern adherence score.
        architectural: Module organization and structure score.
    """

    complexity: float
    maintainability: float
    documentation: float
    temporal_relevance: float
    patterns: float
    architectural: float


class QualityScoringResult(TypedDict):
    """Result structure for quality scoring handler.

    This TypedDict defines the guaranteed structure returned by
    the score_code_quality function.

    All Attributes are Required:
        success: Whether the scoring completed without errors.
        quality_score: Overall quality score (0.0-1.0), weighted aggregate.
        dimensions: Individual dimension scores using the six-dimension standard.
            Keys: complexity, maintainability, documentation, temporal_relevance,
                  patterns, architectural.
        onex_compliant: True if quality_score >= onex_threshold.
        recommendations: List of improvement suggestions based on low scores.
        source_language: The detected or specified source language.
        analysis_version: Version identifier for the scoring algorithm.

    Example:
        >>> result: QualityScoringResult = {
        ...     "success": True,
        ...     "quality_score": 0.78,
        ...     "dimensions": {
        ...         "complexity": 0.75,
        ...         "maintainability": 0.80,
        ...         "documentation": 0.65,
        ...         "temporal_relevance": 0.90,
        ...         "patterns": 0.85,
        ...         "architectural": 0.70,
        ...     },
        ...     "onex_compliant": True,
        ...     "recommendations": ["Add docstrings to functions"],
        ...     "source_language": "python",
        ...     "analysis_version": "1.0.0",
        ... }
    """

    success: bool
    quality_score: float
    dimensions: DimensionScores
    onex_compliant: bool
    recommendations: list[str]
    source_language: str
    analysis_version: str


def create_error_dimensions() -> DimensionScores:
    """Create zero-scored dimensions for error cases.

    Returns a valid DimensionScores with all dimensions set to 0.0,
    suitable for use when scoring fails due to validation or compute errors.
    """
    return DimensionScores(
        complexity=0.0,
        maintainability=0.0,
        documentation=0.0,
        temporal_relevance=0.0,
        patterns=0.0,
        architectural=0.0,
    )


__all__ = ["DimensionScores", "QualityScoringResult", "create_error_dimensions"]
