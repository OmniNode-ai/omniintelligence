"""Output model for Intelligence operations.

This model is used by the intelligence_adapter effect node
for publishing code analysis results to Kafka events.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelIntelligenceOutput(BaseModel):
    """Output model for intelligence operations.

    This model represents the output of code analysis and intelligence operations
    that are published as Kafka events.
    """

    success: bool = Field(
        ...,
        description="Whether the intelligence operation succeeded",
    )
    operation_type: str = Field(
        ...,
        description="Type of intelligence operation performed",
    )
    quality_score: Optional[float] = Field(
        default=None,
        description="Overall quality score (0.0 to 1.0) if applicable",
    )
    analysis_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Results of the analysis",
    )
    patterns_detected: list[str] = Field(
        default_factory=list,
        description="List of detected patterns",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="List of recommendations",
    )
    onex_compliant: Optional[bool] = Field(
        default=None,
        description="Whether the analyzed code is ONEX compliant",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for distributed tracing",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if the operation failed",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the result",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelIntelligenceOutput"]
