# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Output models for node_enforcement_feedback_effect.

This module defines the result model returned by the enforcement feedback
handler after processing an enforcement event and adjusting pattern confidence.

Reference:
    - OMN-2270: Enforcement feedback loop for pattern confidence adjustment
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EnumEnforcementFeedbackStatus(str, Enum):
    """Status of the enforcement feedback processing.

    Attributes:
        SUCCESS: Feedback processed and confidence adjustments applied.
        NO_ADJUSTMENTS: Event processed but no adjustments were needed
            (e.g., no confirmed violations meeting the criteria).
        NO_VIOLATIONS: Event processed but contained zero violations.
        ERROR: An error occurred during processing.
    """

    SUCCESS = "success"
    NO_ADJUSTMENTS = "no_adjustments"
    NO_VIOLATIONS = "no_violations"
    ERROR = "error"


class ModelConfidenceAdjustment(BaseModel):
    """Record of a single confidence adjustment applied to a pattern.

    Attributes:
        pattern_id: The pattern whose confidence was adjusted.
        adjustment: The amount subtracted from quality_score (negative value).
        reason: Human-readable reason for the adjustment.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: UUID = Field(
        ...,
        description="The pattern whose confidence was adjusted",
    )
    adjustment: float = Field(
        ...,
        description="The adjustment applied to quality_score (negative for violations)",
    )
    reason: str = Field(
        ...,
        description="Human-readable reason for the adjustment",
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
        confirmed_violations: Number of violations that met the criteria for
            confidence adjustment (advised AND corrected).
        adjustments: Per-pattern confidence adjustments that were applied.
        processed_at: Timestamp of when processing completed.
        error_message: Error details if status is ERROR.
    """

    model_config = ConfigDict(frozen=True)

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
    confirmed_violations: int = Field(
        default=0,
        description="Number of violations meeting criteria (advised AND corrected)",
    )
    adjustments: list[ModelConfidenceAdjustment] = Field(
        default_factory=list,
        description="Per-pattern confidence adjustments that were applied",
    )
    processed_at: datetime | None = Field(
        default=None,
        description="Timestamp of when processing completed",
    )
    error_message: str | None = Field(
        default=None,
        description="Error details if status is ERROR",
    )


__all__ = [
    "EnumEnforcementFeedbackStatus",
    "ModelConfidenceAdjustment",
    "ModelEnforcementFeedbackResult",
]
