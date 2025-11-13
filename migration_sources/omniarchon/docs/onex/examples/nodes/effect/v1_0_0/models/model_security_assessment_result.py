#!/usr/bin/env python3
"""
Security Assessment Result Model for Canary Impure Tool

Strongly typed model for security assessment results for security risk assessment operations.
"""


from pydantic import BaseModel, Field


class ModelSecurityAssessmentResult(BaseModel):
    """Results of security risk assessment for operations."""

    operation_name: str = Field(description="Name of operation being assessed")
    risk_level: str = Field(
        description="Assessed risk level", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$"
    )
    sandbox_required: bool = Field(description="Whether sandbox mode is required")
    security_violations: list[str] = Field(
        default_factory=list, description="Any security violations detected"
    )
    mitigation_recommendations: list[str] = Field(
        default_factory=list, description="Recommended security mitigations"
    )
    approval_required: bool = Field(
        default=False, description="Whether manual approval is required"
    )
    risk_score: float = Field(
        description="Numerical risk score (0.0-1.0)", ge=0.0, le=1.0
    )
    assessment_timestamp: str = Field(description="When assessment was performed")
    assessment_duration_ms: float = Field(description="Assessment processing time")

    class Config:
        json_schema_extra = {
            "example": {
                "operation_name": "file_write",
                "risk_level": "LOW",
                "sandbox_required": True,
                "security_violations": [],
                "mitigation_recommendations": [
                    "path_validation",
                    "sandbox_enforcement",
                ],
                "approval_required": False,
                "risk_score": 0.2,
                "assessment_timestamp": "2024-01-15T10:30:45.123Z",
                "assessment_duration_ms": 5.2,
            }
        }
