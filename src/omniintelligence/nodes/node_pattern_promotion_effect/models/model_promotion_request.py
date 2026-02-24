# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input models for pattern_promotion_effect.

This module defines the request models for the pattern promotion effect node,
which checks and promotes eligible provisional patterns to validated status.
"""

from uuid import UUID

from pydantic import BaseModel, Field


class ModelPromotionCheckRequest(BaseModel):
    """Request to check and promote eligible patterns.

    This model triggers a scan of all provisional patterns to identify those
    meeting the promotion criteria based on rolling window success rates.
    """

    dry_run: bool = Field(
        default=False,
        description="If True, return what WOULD be promoted without mutating",
    )
    min_injection_count: int = Field(
        default=5,
        ge=1,
        description="Minimum injection_count_rolling_20 required for promotion eligibility",
    )
    min_success_rate: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum success rate (0.0-1.0) required for promotion",
    )
    max_failure_streak: int = Field(
        default=3,
        ge=0,
        description="Maximum consecutive failures allowed for promotion eligibility. "
        "Set to 0 for zero-tolerance configurations where any failure prevents promotion.",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Optional correlation ID for tracing",
    )


__all__ = ["ModelPromotionCheckRequest"]
