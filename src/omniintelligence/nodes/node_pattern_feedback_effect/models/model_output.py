"""Output models for node_pattern_feedback_effect.

This module defines the output models for the pattern feedback effect node,
representing the results of recording session outcomes.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EnumOutcomeRecordingStatus(str, Enum):
    """Status of the outcome recording operation.

    Attributes:
        SUCCESS: Outcome was successfully recorded and patterns updated.
        NO_INJECTIONS_FOUND: No pattern injections found for the session.
        ALREADY_RECORDED: Outcome was already recorded for this session.
        ERROR: An error occurred during recording.
    """

    SUCCESS = "success"
    NO_INJECTIONS_FOUND = "no_injections_found"
    ALREADY_RECORDED = "already_recorded"
    ERROR = "error"


class ModelSessionOutcomeResult(BaseModel):
    """Result of recording a session outcome.

    This model represents the outcome of processing a session feedback
    request, including how many patterns were updated and any errors.
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
    recorded_at: datetime | None = Field(
        default=None,
        description="Timestamp when outcome was recorded",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if status=ERROR",
    )
