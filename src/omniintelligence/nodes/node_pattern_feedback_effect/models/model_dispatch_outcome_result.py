# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for dispatch outcome feedback recording."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_feedback_effect.models.enum_outcome_recording_status import (
    EnumOutcomeRecordingStatus,
)


class ModelDispatchOutcomeResult(BaseModel):
    """Result of recording a dispatch evaluation outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: EnumOutcomeRecordingStatus = Field(
        ...,
        description="The status of the dispatch outcome recording operation.",
    )
    task_id: str = Field(..., min_length=1, description="Evaluated task ID.")
    dispatch_id: str = Field(..., min_length=1, description="Dispatch operation ID.")
    ticket_id: str | None = Field(
        default=None,
        description="Optional Linear ticket associated with the dispatch.",
    )
    rows_updated: int = Field(
        default=0,
        ge=0,
        description="Number of dispatch_eval_results rows inserted or updated.",
    )
    recorded_at: datetime | None = Field(
        default=None,
        description="Timestamp when the dispatch outcome was recorded.",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if status=ERROR.",
    )


__all__ = ["ModelDispatchOutcomeResult"]
