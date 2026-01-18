"""Input model for Intelligence operations.

This model is used by the intelligence_adapter effect node
for processing code analysis requests from Kafka events.

Migration Note:
    This unified input model replaces multiple operation-specific request
    models from the legacy omniarchon system:
    - ModelQualityAssessmentRequest -> operation_type="assess_code_quality"
    - ModelPerformanceAnalysisRequest -> operation_type="analyze_performance"
    - ModelPatternDetectionRequest -> operation_type="detect_patterns"

    Operation-specific parameters that were individual fields in legacy models
    should now be passed in the `options` dictionary.

    See MIGRATION.md for complete migration guidance.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelIntelligenceInput(BaseModel):
    """Input model for intelligence operations.

    This model represents the input for code analysis and intelligence operations
    consumed from Kafka events.

    Migration from Legacy:
        This unified model replaces operation-specific request models:

        Legacy ModelQualityAssessmentRequest:
            >>> # Legacy
            >>> ModelQualityAssessmentRequest(
            ...     content="def foo(): pass",
            ...     source_path="src/main.py",
            ...     language="python",
            ...     include_recommendations=True,
            ...     min_quality_threshold=0.7
            ... )
            >>> # Canonical equivalent
            >>> ModelIntelligenceInput(
            ...     operation_type="assess_code_quality",
            ...     content="def foo(): pass",
            ...     source_path="src/main.py",
            ...     language="python",
            ...     options={"include_recommendations": True, "min_quality_threshold": 0.7}
            ... )

        Legacy ModelPatternDetectionRequest:
            >>> # Legacy
            >>> ModelPatternDetectionRequest(
            ...     content="class Foo: pass",
            ...     source_path="src/foo.py",
            ...     pattern_categories=["best_practices"],
            ...     min_confidence=0.7
            ... )
            >>> # Canonical equivalent
            >>> ModelIntelligenceInput(
            ...     operation_type="detect_patterns",
            ...     content="class Foo: pass",
            ...     source_path="src/foo.py",
            ...     options={"pattern_categories": ["best_practices"], "min_confidence": 0.7}
            ... )
    """

    operation_type: str = Field(
        ...,
        description="Type of intelligence operation (analyze_code, assess_quality, detect_patterns, etc.)",
    )
    content: str = Field(
        ...,
        description="Content to analyze (source code, document, etc.)",
    )
    source_path: Optional[str] = Field(
        default=None,
        description="Path to the source file being analyzed",
    )
    language: str = Field(
        default="python",
        description="Programming language of the content",
    )
    project_name: Optional[str] = Field(
        default=None,
        description="Name of the project for context",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Operation-specific options and parameters for analysis",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for distributed tracing",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the request",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelIntelligenceInput"]
