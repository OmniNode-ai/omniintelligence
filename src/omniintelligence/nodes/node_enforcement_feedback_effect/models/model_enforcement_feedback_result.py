# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Enforcement feedback result model.

Reference: OMN-2270
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_enforcement_feedback_effect.models.enum_enforcement_feedback_status import (
    EnumEnforcementFeedbackStatus,
)
from omniintelligence.nodes.node_enforcement_feedback_effect.models.model_confidence_adjustment import (
    ModelConfidenceAdjustment,
)
from omniintelligence.nodes.node_enforcement_feedback_effect.models.model_processing_error import (
    ModelProcessingError,
)


class ModelEnforcementFeedbackResult(BaseModel):
    """Result of processing an enforcement feedback event.

    Returned by the handler after consuming an enforcement event and
    applying any confidence adjustments.

    Attributes:
        status: Overall processing status.
        correlation_id: Correlation ID from the input event.
        session_id: Session ID from the input event.
        patterns_checked: Number of patterns checked in the enforcement event.
        violations_found: Number of violations found in the enforcement event.
        eligible_violations: Number of violations meeting criteria (advised AND corrected).
        adjustments: Per-pattern confidence adjustments that were successfully applied.
        processing_errors: Per-pattern error details for adjustments that failed.
        processed_at: Timestamp of when processing completed.
        error_message: Error details if status is ERROR.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: EnumEnforcementFeedbackStatus = Field(
        ...,
        description="Overall processing status",
    )
    correlation_id: UUID = Field(
        ...,
        description="Correlation ID from the input event",
    )
    session_id: UUID = Field(
        ...,
        description="Session ID from the input event",
    )
    patterns_checked: int = Field(
        default=0,
        description="Number of patterns checked in the enforcement event",
    )
    violations_found: int = Field(
        default=0,
        description="Number of violations found in the enforcement event",
    )
    eligible_violations: int = Field(
        default=0,
        description="Number of violations meeting criteria (advised AND corrected)",
    )
    adjustments: list[ModelConfidenceAdjustment] = Field(
        default_factory=list,
        description="Per-pattern confidence adjustments that were successfully applied",
    )
    processing_errors: list[ModelProcessingError] = Field(
        default_factory=list,
        description="Per-pattern error details for adjustments that failed",
    )
    processed_at: datetime = Field(
        ...,
        description="Timestamp of when processing completed",
    )
    error_message: str | None = Field(
        default=None,
        description="Error details if status is ERROR",
    )


__all__ = ["ModelEnforcementFeedbackResult"]
