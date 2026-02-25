# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Observer type enum for WatchdogEffect.

Identifies which filesystem observer backend is active.
Determined at startup by platform detection and library availability.

Reference: OMN-2386
"""

from enum import Enum


class EnumWatchdogObserverType(str, Enum):
    """Backend observer used by the watchdog library.

    FSEVENTS:
        macOS FSEvents API (native, low-overhead).  Used on macOS when
        the ``watchdog`` library supports it.

    INOTIFY:
        Linux inotify API (native, low-overhead).  Used on Linux when
        the ``watchdog`` library supports it.

    POLLING:
        Fallback polling observer (5-second interval).  Used when native
        APIs are unavailable or the watchdog library is not installed.
    """

    FSEVENTS = "fsevents"
    INOTIFY = "inotify"
    POLLING = "polling"


__all__ = ["EnumWatchdogObserverType"]
