# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Outcome recording status enum for node_pattern_feedback_effect."""

from enum import Enum


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


__all__ = ["EnumOutcomeRecordingStatus"]
