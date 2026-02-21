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

    EMITTED:
        A crawl-requested.v1 command was successfully published to Kafka
        in response to a filesystem change event.

    SKIPPED:
        The change event was filtered (e.g. temporary file, editor swap
        file) and no Kafka message was published.

    ERROR:
        An unexpected error occurred.  The handler returned a structured
        result rather than raising.  The error_message field contains details.
    """

    STARTED = "started"
    STOPPED = "stopped"
    EMITTED = "emitted"
    SKIPPED = "skipped"
    ERROR = "error"


__all__ = ["EnumWatchdogStatus"]
