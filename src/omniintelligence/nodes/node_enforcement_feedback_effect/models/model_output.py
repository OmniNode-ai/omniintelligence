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
        SUCCESS: Feedback processed and all confidence adjustments applied.
        PARTIAL_SUCCESS: Some adjustments applied but others failed. Check
            ``processing_errors`` for details on which patterns failed.
        NO_ADJUSTMENTS: Event processed but no adjustments were needed
            (e.g., no confirmed violations meeting the criteria).
        NO_VIOLATIONS: Event processed but contained zero violations.
        ERROR: An error occurred during processing.
    """

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
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


class ModelProcessingError(BaseModel):
    """Record of a failed confidence adjustment for a single pattern.

    Captured when ``_apply_confidence_adjustment`` raises an exception so
    that callers can see exactly which patterns failed and why.

    Attributes:
        pattern_id: The pattern whose adjustment failed.
        pattern_name: Human-readable name for diagnostics.
        error: Sanitized error message describing the failure.
        error_type: The exception class name (e.g., ``"ConnectionError"``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: UUID = Field(
        ...,
        description="The pattern whose adjustment failed",
    )
    pattern_name: str = Field(
        default="",
        description="Human-readable name of the pattern",
    )
    error: str = Field(
        ...,
        description="Sanitized error message describing the failure",
    )
    error_type: str = Field(
        ...,
        description="The exception class name (e.g., 'ConnectionError')",
    )


class ModelEnforcementFeedbackResult(BaseModel):
    """Result of processing an enforcement feedback event.

    Returned by the handler after consuming an enforcement event and
    applying any confidence adjustments.

    Partial Failure Reporting:
        Each confirmed violation is processed independently. If some
        adjustments succeed and others fail (e.g., due to transient DB
        errors), the result accurately reports both:
        - ``adjustments``: only successfully applied adjustments
        - ``processing_errors``: per-pattern error details for failures
        - ``status``: ``PARTIAL_SUCCESS`` when some but not all succeeded

        This design is intentional: the ``ProtocolPatternRepository`` does
        not expose transaction control, so each UPDATE runs independently.
        Rather than hiding partial failures behind a generic SUCCESS, the
        result model makes them visible to callers.

    Attributes:
        status: Overall processing status.
        correlation_id: Correlation ID from the input event.
        session_id: Session ID from the input event.
        patterns_checked: Number of patterns checked in the enforcement event.
        violations_found: Number of violations found in the enforcement event.
        eligible_violations: Number of violations that met the criteria for
            confidence adjustment (advised AND corrected). These are violations
            that were eligible for adjustment; see ``adjustments`` for the subset
            where the DB update was actually applied.
        adjustments: Per-pattern confidence adjustments that were successfully
            applied. Only contains adjustments that committed to the database.
        processing_errors: Per-pattern error details for adjustments that
            failed. Empty when all adjustments succeed.
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


__all__ = [
    "EnumEnforcementFeedbackStatus",
    "ModelConfidenceAdjustment",
    "ModelEnforcementFeedbackResult",
    "ModelProcessingError",
]
