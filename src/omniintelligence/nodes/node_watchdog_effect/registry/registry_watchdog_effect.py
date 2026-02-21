# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Registry for WatchdogEffect dependencies.

Manages the active observer instance and observer type at module level
for test isolation and runtime wiring.

Thread safety:
    ``_HANDLER_STORAGE`` is protected by ``_REGISTRY_LOCK`` (a
    ``threading.Lock``).  The watchdog observer runs in a dedicated OS
    thread and may call registry accessors concurrently with the asyncio
    event loop.  Although asyncio itself is single-threaded, the OS
    observer thread is not — so all dict mutations are performed while
    holding the lock.

Testing:
    Tests MUST call ``RegistryWatchdogEffect.clear()`` in setup
    and teardown to prevent test pollution.

    Recommended fixture pattern::

        @pytest.fixture(autouse=True)
        def clear_registry():
            RegistryWatchdogEffect.clear()
            yield
            RegistryWatchdogEffect.clear()

Reference: OMN-2386
"""

from __future__ import annotations

import logging
import threading
from typing import Any, cast

from omniintelligence.nodes.node_watchdog_effect.models.enum_watchdog_observer_type import (
    EnumWatchdogObserverType,
)

logger = logging.getLogger(__name__)

__all__ = ["RegistryWatchdogEffect"]

# Module-level storage for injected dependencies.
# All mutations are serialised through _REGISTRY_LOCK because the watchdog
# observer runs in an OS thread and may access this dict concurrently.
_HANDLER_STORAGE: dict[str, object] = {}
_REGISTRY_LOCK: threading.Lock = threading.Lock()


class RegistryWatchdogEffect:
    """Registry for WatchdogEffect node dependencies.

    Stores the active observer instance and observer type at module level
    for test isolation and runtime wiring.
    """

    _OBSERVER_KEY = "observer"
    _OBSERVER_TYPE_KEY = "observer_type"

    @staticmethod
    def register_observer(
        observer: Any,
        observer_type: EnumWatchdogObserverType,
    ) -> None:
        """Register the active watchdog observer instance.

        Args:
            observer: The running watchdog observer (FSEventsObserver,
                InotifyObserver, or PollingObserver).
            observer_type: The type of observer that was selected.
        """
        with _REGISTRY_LOCK:
            _HANDLER_STORAGE[RegistryWatchdogEffect._OBSERVER_KEY] = observer
            _HANDLER_STORAGE[RegistryWatchdogEffect._OBSERVER_TYPE_KEY] = observer_type

    @staticmethod
    def get_observer() -> Any | None:
        """Return the active observer instance, or None if not started."""
        with _REGISTRY_LOCK:
            return _HANDLER_STORAGE.get(RegistryWatchdogEffect._OBSERVER_KEY)

    @staticmethod
    def get_observer_type() -> EnumWatchdogObserverType | None:
        """Return the observer type, or None if not started."""
        with _REGISTRY_LOCK:
            result = _HANDLER_STORAGE.get(RegistryWatchdogEffect._OBSERVER_TYPE_KEY)
        return cast("EnumWatchdogObserverType | None", result)

    @staticmethod
    def clear() -> None:
        """Clear all registered dependencies.

        MUST be called in test setup and teardown to prevent test pollution.
        """
        with _REGISTRY_LOCK:
            _HANDLER_STORAGE.clear()
