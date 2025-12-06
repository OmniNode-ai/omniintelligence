"""
Quality Score Model for omniintelligence.

Models for quality assessment scoring.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence._legacy.enums import EnumQualityDimension


class ModelQualityScore(BaseModel):
    """Quality assessment score."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall_score": 0.85,
                "dimensions": {
                    "MAINTAINABILITY": 0.9,
                    "READABILITY": 0.8,
                },
                "onex_compliant": True,
            }
        }
    )

    overall_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall quality score"
    )
    dimensions: dict[EnumQualityDimension, float] = Field(
        ..., description="Dimension scores"
    )
    onex_compliant: bool = Field(..., description="ONEX compliance status")
    compliance_issues: list[str] = Field(
        default_factory=list, description="Compliance issues"
    )
    recommendations: list[dict[str, Any]] = Field(
        default_factory=list, description="Recommendations"
    )


__all__ = ["ModelQualityScore"]
