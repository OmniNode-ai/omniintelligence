# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Code analysis completed event payload model.

This module defines the Pydantic model for CODE_ANALYSIS_COMPLETED events
published to the code analysis completed Kafka topic after successful analysis.

ONEX Compliance:
- Model-based naming: Model{Domain}{Purpose}
- Strong typing with Pydantic Field validation
- UUID type for correlation_id (aligns with omnimemory consumer)

Contract notes:
- operation_type mirrors the value from the originating request. It should
  always be non-null for well-formed completed events (since the request
  model requires it), but consumers must handle null defensively in case
  events were produced by older or non-conformant producers.
"""

from uuid import UUID

from pydantic import BaseModel, Field

from omniintelligence.enums.enum_analysis_operation_type import (
    EnumAnalysisOperationType,
)


class ModelCodeAnalysisCompletedPayload(BaseModel):
    """Event payload for completed code analysis.

    Published to the CODE_ANALYSIS_COMPLETED topic after successful
    analysis, containing quality scores and recommendations.

    Attributes:
        correlation_id: UUID for distributed tracing
        result: Full analysis result dictionary
        source_path: Path to the analyzed source
        quality_score: Overall quality score (0.0-1.0)
        onex_compliance: ONEX compliance score (0.0-1.0)
        issues_count: Number of issues found
        recommendations_count: Number of recommendations
        processing_time_ms: Processing time in milliseconds
        operation_type: Type of analysis performed
        complexity_score: Optional complexity score
        maintainability_score: Optional maintainability score
        results_summary: Summary of analysis results
        cache_hit: Whether result was from cache
    """

    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for distributed tracing",
    )
    result: dict[str, object] = Field(default_factory=dict)
    source_path: str = Field(default="", description="Path to the analyzed source")
    quality_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Quality score"
    )
    onex_compliance: float = Field(
        default=0.0, ge=0.0, le=1.0, description="ONEX compliance score"
    )
    issues_count: int = Field(default=0, ge=0, description="Number of issues found")
    recommendations_count: int = Field(
        default=0, ge=0, description="Number of recommendations"
    )
    processing_time_ms: float = Field(
        default=0.0, ge=0.0, description="Processing time in ms"
    )
    operation_type: EnumAnalysisOperationType | None = Field(
        default=None, description="Type of analysis performed"
    )
    complexity_score: float | None = Field(default=None, description="Complexity score")
    maintainability_score: float | None = Field(
        default=None, description="Maintainability score"
    )
    results_summary: dict[str, object] = Field(
        default_factory=dict, description="Summary of results"
    )
    cache_hit: bool = Field(default=False, description="Whether result was cached")
