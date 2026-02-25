# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern learning payload model for Intelligence Reducer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelPatternLearningPayload(BaseModel):
    """Payload for PATTERN_LEARNING FSM operations.

    Used for 4-phase pattern learning: Foundation -> Matching -> Validation -> Traceability.
    """

    # Pattern identification
    pattern_id: str | None = Field(
        default=None,
        description="Unique identifier for the pattern",
    )
    pattern_name: str | None = Field(
        default=None,
        description="Human-readable pattern name",
    )

    # Learning configuration
    confidence_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for pattern matching",
    )

    # Pattern metadata
    pattern_metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Additional pattern metadata",
    )

    # Source content for learning
    content: str | None = Field(
        default=None,
        min_length=1,
        description="Source content for pattern learning",
    )
    file_path: str | None = Field(
        default=None,
        min_length=1,
        description="Source file path",
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


__all__ = ["ModelPatternLearningPayload"]
