"""Input model for Intelligence operations.

This model is used by the intelligence_adapter effect node
for processing code analysis requests from Kafka events.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelIntelligenceInput(BaseModel):
    """Input model for intelligence operations.

    This model represents the input for code analysis and intelligence operations
    consumed from Kafka events.
    """

    operation_type: str = Field(
        ...,
        description="Type of intelligence operation (analyze_code, assess_quality, detect_patterns, etc.)",
    )
    content: str = Field(
        ...,
        description="Content to analyze (source code, document, etc.)",
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Path to the file being analyzed",
    )
    language: str = Field(
        default="python",
        description="Programming language of the content",
    )
    project_name: Optional[str] = Field(
        default=None,
        description="Name of the project for context",
    )
    analysis_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional parameters for the analysis",
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
