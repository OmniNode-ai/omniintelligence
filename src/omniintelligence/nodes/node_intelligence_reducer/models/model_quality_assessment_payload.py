"""Quality assessment payload model for Intelligence Reducer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelQualityAssessmentPayload(BaseModel):
    """Payload for QUALITY_ASSESSMENT FSM operations.

    Used for quality assessment: RAW -> ASSESSING -> SCORED -> STORED.
    """

    # Assessment input
    content: str | None = Field(
        default=None,
        min_length=1,
        description="Content to assess",
    )
    file_path: str | None = Field(
        default=None,
        min_length=1,
        description="Source file path",
    )
    source_type: str | None = Field(
        default=None,
        description="Source type for assessment context",
    )

    # Assessment results (populated during SCORED state)
    quality_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Quality score (0.0 to 1.0)",
    )
    compliance_status: str | None = Field(
        default=None,
        description="ONEX compliance status",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Quality improvement recommendations",
    )

    # Assessment metadata
    assessment_metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Additional assessment metadata",
    )

    # Error fields (used when action is 'fail')
    failure_reason: str | None = Field(
        default=None,
        description="Reason for failure if action is 'fail'",
    )
    error_code: str | None = Field(
        default=None,
        description="Error code for failure categorization",
    )
    error_details: str | None = Field(
        default=None,
        description="Detailed error information",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


__all__ = ["ModelQualityAssessmentPayload"]
