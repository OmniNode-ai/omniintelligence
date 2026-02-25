# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Status enum for WatchdogEffect handler results.

Reference: OMN-2386
"""

from enum import Enum


class EnumWatchdogStatus(str, Enum):
    """Outcome status for a single watchdog operation.

    STARTED:
        The filesystem observer was successfully started and is watching
        the configured paths.

    STOPPED:
        The filesystem observer was successfully stopped.

    ERROR:
        An unexpected error occurred.  The handler returned a structured
        result rather than raising.  The error_message field contains details.
    """

    STARTED = "started"
    STOPPED = "stopped"
    ERROR = "error"


__all__ = ["EnumWatchdogStatus"]
