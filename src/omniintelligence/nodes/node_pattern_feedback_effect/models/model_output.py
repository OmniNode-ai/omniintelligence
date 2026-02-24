# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output models for node_pattern_feedback_effect.

This module defines the output models for the pattern feedback effect node,
representing the results of recording session outcomes.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_feedback_effect.models.enum_outcome_recording_status import (
    EnumOutcomeRecordingStatus,
)


class ModelSessionOutcomeResult(BaseModel):
    """Result of recording a session outcome.

    This model represents the outcome of processing a session feedback
    request, including how many patterns were updated, their new
    effectiveness scores, and any errors.
    """

    model_config = ConfigDict(frozen=True)

    status: EnumOutcomeRecordingStatus = Field(
        ...,
        description="The status of the outcome recording operation",
    )
    session_id: UUID = Field(
        ...,
        description="The session ID that was processed",
    )
    injections_updated: int = Field(
        default=0,
        description="Number of pattern_injections rows updated",
    )
    patterns_updated: int = Field(
        default=0,
        description="Number of learned_patterns rows updated",
    )
    pattern_ids: list[UUID] = Field(
        default_factory=list,
        description="List of pattern IDs that were updated",
    )
    effectiveness_scores: dict[UUID, float] | None = Field(
        default_factory=dict,
        description="Mapping of pattern UUID to updated effectiveness score (quality_score). "
        "Score is success_count_rolling_20 / injection_count_rolling_20, range [0.0, 1.0]. "
        "None indicates scoring failed (caller should treat as degraded). "
        "Empty dict ({}) indicates no patterns were eligible for scoring.",
    )
    recorded_at: datetime | None = Field(
        default=None,
        description="Timestamp when outcome was recorded",
    )
    attribution_binding_failed: bool = Field(
        default=False,
        description="True if the L1 attribution binding step failed. "
        "When True, evidence tiers were not updated for this session. "
        "The critical path (metrics, scores) still succeeded.",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if status=ERROR",
    )


__all__ = ["ModelSessionOutcomeResult"]
