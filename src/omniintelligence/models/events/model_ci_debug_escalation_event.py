# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Event model for CI debug escalation telemetry.

Published when consecutive CI failures cross the escalation threshold,
triggering debug intelligence analysis. Consumed by omnidash
/ci-intelligence page.

Reference: OMN-6123 (Dashboard Data Pipeline Gaps)
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelCiDebugEscalationEvent(BaseModel):
    """Frozen event model for CI debug escalation.

    Emitted when a CI failure streak crosses the configured threshold,
    indicating that debug intelligence analysis should be triggered.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    escalation_id: str = Field(
        min_length=1, description="Unique ID for this escalation"
    )
    correlation_id: str = Field(
        min_length=1, description="Distributed tracing correlation ID"
    )
    repo: str = Field(min_length=1, description="Repository identifier")
    branch: str = Field(min_length=1, description="Branch name")
    ci_run_url: str = Field(
        default="",
        description="URL to the failing CI run (empty if not available)",
    )
    failure_type: str = Field(
        min_length=1,
        description="Classification: test_failure, lint_failure, build_failure, timeout",
    )
    consecutive_failures: int = Field(
        ge=1, description="Number of consecutive failures at escalation time"
    )
    escalated_at: datetime = Field(description="UTC timestamp of escalation")

    @field_validator("escalated_at")
    @classmethod
    def validate_tz_aware(cls, v: datetime) -> datetime:
        """Validate that escalated_at is timezone-aware."""
        if v.tzinfo is None:
            raise ValueError("escalated_at must be timezone-aware")
        return v


__all__ = ["ModelCiDebugEscalationEvent"]
