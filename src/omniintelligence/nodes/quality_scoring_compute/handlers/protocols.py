"""Type protocols for quality scoring handler results.

This module defines TypedDict structures for type-safe handler responses,
enabling static type checking with mypy and improved IDE support.

Design Decisions:
    - TypedDict is used because handlers return dicts, not objects with methods.
    - All scores are normalized to 0.0-1.0 range for consistency.
    - Required fields use total=True (default) for strict validation.

Usage:
    from omniintelligence.nodes.quality_scoring_compute.handlers.protocols import (
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


class QualityScoringResult(TypedDict):
    """Result structure for quality scoring handler.

    This TypedDict defines the guaranteed structure returned by
    the score_code_quality function.

    All Attributes are Required:
        success: Whether the scoring completed without errors.
        quality_score: Overall quality score (0.0-1.0), weighted aggregate.
        dimensions: Individual dimension scores, each 0.0-1.0.
            Keys: patterns, type_coverage, maintainability, complexity, documentation.
        onex_compliant: True if quality_score >= onex_threshold.
        recommendations: List of improvement suggestions based on low scores.
        source_language: The detected or specified source language.
        analysis_version: Version identifier for the scoring algorithm.

    Example:
        >>> result: QualityScoringResult = {
        ...     "success": True,
        ...     "quality_score": 0.78,
        ...     "dimensions": {
        ...         "patterns": 0.85,
        ...         "type_coverage": 0.70,
        ...         "maintainability": 0.80,
        ...         "complexity": 0.75,
        ...         "documentation": 0.65,
        ...     },
        ...     "onex_compliant": True,
        ...     "recommendations": ["Add docstrings to functions"],
        ...     "source_language": "python",
        ...     "analysis_version": "1.0.0",
        ... }
    """

    success: bool
    quality_score: float
    dimensions: dict[str, float]
    onex_compliant: bool
    recommendations: list[str]
    source_language: str
    analysis_version: str


__all__ = ["QualityScoringResult"]
