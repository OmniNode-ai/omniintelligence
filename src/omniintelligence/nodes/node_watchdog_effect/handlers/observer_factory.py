# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Observer factory for WatchdogEffect.

Selects the appropriate watchdog observer backend based on platform and
library availability:
    - macOS: FSEventsObserver (native, low-overhead)
    - Linux: InotifyObserver (native, low-overhead)
    - Fallback: PollingObserver (5-second interval)

The factory returns a (observer_instance, EnumWatchdogObserverType) tuple.
All imports from the watchdog library are wrapped in try/except so the
module can be safely imported even when watchdog is not installed
(tests mock the observer directly).

Design: omni_save/design/DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §4
Reference: OMN-2386
"""

from __future__ import annotations

import platform
from typing import TYPE_CHECKING, Any

from omniintelligence.nodes.node_watchdog_effect.models.enum_watchdog_observer_type import (
    EnumWatchdogObserverType,
)

if TYPE_CHECKING:
    # Only for type annotations — not a runtime import guard
    pass


def create_observer() -> tuple[Any, EnumWatchdogObserverType]:
    """Create and return the best available watchdog observer for the platform.

    Selection priority:
    1. macOS → FSEventsObserver (via ``watchdog.observers.fsevents``)
    2. Linux → InotifyObserver (via ``watchdog.observers.inotify``)
    3. Fallback → PollingObserver (via ``watchdog.observers.polling``)

    Returns:
        A tuple of ``(observer_instance, EnumWatchdogObserverType)``.

    Raises:
        ImportError: If watchdog is not installed AND the platform is not
            handled by the fallback path.  In practice the fallback always
            succeeds because PollingObserver is bundled with watchdog.
    """
    system = platform.system()

    if system == "Darwin":
        try:
            from watchdog.observers.fsevents import FSEventsObserver

            return FSEventsObserver(), EnumWatchdogObserverType.FSEVENTS
        except Exception:
            pass  # fallback-ok: FSEvents unavailable (VM, CI, non-native env)

    if system == "Linux":
        try:
            from watchdog.observers.inotify import InotifyObserver

            return InotifyObserver(), EnumWatchdogObserverType.INOTIFY
        except Exception:
            pass  # fallback-ok: inotify unavailable (container, BSD-compat kernel)

    # Fallback — always available when watchdog is installed
    try:
        from watchdog.observers.polling import PollingObserver

        return PollingObserver(), EnumWatchdogObserverType.POLLING
    except ImportError as exc:
        raise ImportError(
            "watchdog library is not installed.  Install it with: uv add watchdog"
        ) from exc


__all__ = ["create_observer"]
