"""Input model for Intelligence operations.

This model is used by the intelligence_adapter effect node
for processing code analysis requests from Kafka events.

Migration Note:
    This unified input model replaces multiple operation-specific request
    models from the legacy omniarchon system:
    - ModelQualityAssessmentRequest -> operation_type="assess_code_quality"
    - ModelPerformanceAnalysisRequest -> operation_type="establish_performance_baseline"
    - ModelPatternDetectionRequest -> operation_type="pattern_match"

    Operation-specific parameters that were individual fields in legacy models
    should now be passed in the `options` dictionary.

    See MIGRATION.md for complete migration guidance.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from omniintelligence.enums import EnumIntelligenceOperationType


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
            ...     operation_type="pattern_match",
            ...     content="class Foo: pass",
            ...     source_path="src/foo.py",
            ...     options={"pattern_categories": ["best_practices"], "min_confidence": 0.7}
            ... )
    """

    operation_type: EnumIntelligenceOperationType = Field(
        ...,
        description="Type of intelligence operation (analyze_code, assess_quality, detect_patterns, etc.)",
    )
    content: str = Field(
        ...,
        min_length=1,
        description=(
            "Content to analyze (source code, document, etc.). "
            "When both content and source_path are provided, content takes precedence "
            "and is used for analysis. The source_path is then used only for metadata "
            "(e.g., language detection, file context in reports)."
        ),
    )
    source_path: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Path to the source file being analyzed. Used for metadata and context "
            "when content is provided inline. Note: This field does NOT load content "
            "from the path - content must be provided explicitly in the content field."
        ),
    )
    language: str = Field(
        default="python",
        description="Programming language of the content",
    )
    project_name: str | None = Field(
        default=None,
        description="Name of the project for context",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Operation-specific options and parameters for analysis",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for distributed tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the request",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelIntelligenceInput"]
