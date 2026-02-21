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
    from omniintelligence.nodes.node_watchdog_effect.models.model_watchdog_config import (
        ModelWatchdogConfig,
    )


def create_observer(
    config: ModelWatchdogConfig | None = None,
) -> tuple[Any, EnumWatchdogObserverType]:
    """Create and return the best available watchdog observer for the platform.

    Selection priority:
    1. macOS → FSEventsObserver (via ``watchdog.observers.fsevents``)
    2. Linux → InotifyObserver (via ``watchdog.observers.inotify``)
    3. Fallback → PollingObserver (via ``watchdog.observers.polling``)

    Args:
        config: Optional watchdog configuration.  When provided,
            ``config.polling_interval_seconds`` is passed to
            ``PollingObserver`` as the polling interval.  Ignored when a
            native FSEvents or inotify observer is selected.

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
        except (ImportError, OSError):
            pass  # fallback-ok: FSEvents unavailable (VM, CI, non-native env)

    if system == "Linux":
        try:
            from watchdog.observers.inotify import InotifyObserver

            return InotifyObserver(), EnumWatchdogObserverType.INOTIFY
        except (ImportError, OSError):
            pass  # fallback-ok: inotify unavailable (container, BSD-compat kernel)

    # Fallback — always available when watchdog is installed.
    # Pass polling_interval_seconds from config so the operator-configured
    # value is actually honoured (PollingObserver default is 1 second).
    try:
        from watchdog.observers.polling import PollingObserver

        polling_interval = (
            float(config.polling_interval_seconds) if config is not None else 5.0
        )
        return PollingObserver(
            timeout=polling_interval
        ), EnumWatchdogObserverType.POLLING
    except ImportError as exc:
        raise ImportError(
            "watchdog library is not installed.  Install it with: uv add watchdog"
        ) from exc


__all__ = ["create_observer"]
