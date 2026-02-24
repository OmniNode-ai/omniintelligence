# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Analysis error code enum for intelligence adapter events."""

from enum import Enum


class EnumAnalysisErrorCode(str, Enum):
    """Analysis error codes for failure events.

    Used in ModelCodeAnalysisFailedPayload to categorize the type
    of failure that occurred during code analysis.
    """

    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    INVALID_INPUT = "invalid_input"
    SERVICE_ERROR = "service_error"
    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"


__all__ = ["EnumAnalysisErrorCode"]
