# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
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

    Stores the active observer instance, observer type, and the config used
    at start time at module level for test isolation and runtime wiring.
    """

    _OBSERVER_KEY = "observer"
    _OBSERVER_TYPE_KEY = "observer_type"
    _CONFIG_KEY = "config"
    # Sentinel key set atomically before factory()/schedule_watches() to
    # prevent a second concurrent start_watching() call from racing past the
    # get_observer() check.  Cleared on rollback (start failure) or replaced
    # by register_observer() on success.
    _STARTING_KEY = "_starting"

    @staticmethod
    def claim_start_slot() -> bool:
        """Atomically claim the start slot if no observer is active or starting.

        Returns True if the caller is now the designated starter; False if
        another call already holds the slot (either a running observer or a
        concurrent start in progress).  When True is returned the registry
        contains a ``_starting`` sentinel that prevents racing callers from
        also claiming the slot.
        """
        with _REGISTRY_LOCK:
            if _HANDLER_STORAGE.get(RegistryWatchdogEffect._OBSERVER_KEY) is not None:
                return False
            if _HANDLER_STORAGE.get(RegistryWatchdogEffect._STARTING_KEY):
                return False
            _HANDLER_STORAGE[RegistryWatchdogEffect._STARTING_KEY] = True
            return True

    @staticmethod
    def release_start_slot() -> None:
        """Release the start sentinel without registering an observer.

        Called on rollback (e.g. factory() or observer.start() raised) so
        subsequent start_watching() calls are not permanently blocked.
        """
        with _REGISTRY_LOCK:
            _HANDLER_STORAGE.pop(RegistryWatchdogEffect._STARTING_KEY, None)

    @staticmethod
    def register_observer(
        observer: Any,
        observer_type: EnumWatchdogObserverType,
        config: Any = None,
    ) -> None:
        """Register the active watchdog observer instance.

        Replaces the ``_starting`` sentinel with the real observer so the
        double-start guard reflects the running state.

        Args:
            observer: The running watchdog observer (FSEventsObserver,
                InotifyObserver, or PollingObserver).
            observer_type: The type of observer that was selected.
            config: The ModelWatchdogConfig used when starting the observer.
                Stored so the double-start guard can report the correct
                watched_paths from the running observer's config.
        """
        with _REGISTRY_LOCK:
            _HANDLER_STORAGE.pop(RegistryWatchdogEffect._STARTING_KEY, None)
            _HANDLER_STORAGE[RegistryWatchdogEffect._OBSERVER_KEY] = observer
            _HANDLER_STORAGE[RegistryWatchdogEffect._OBSERVER_TYPE_KEY] = observer_type
            if config is not None:
                _HANDLER_STORAGE[RegistryWatchdogEffect._CONFIG_KEY] = config

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
    def get_config() -> Any | None:
        """Return the ModelWatchdogConfig used when the observer was started, or None."""
        with _REGISTRY_LOCK:
            return _HANDLER_STORAGE.get(RegistryWatchdogEffect._CONFIG_KEY)

    @staticmethod
    def clear() -> None:
        """Clear all registered dependencies.

        MUST be called in test setup and teardown to prevent test pollution.
        """
        with _REGISTRY_LOCK:
            _HANDLER_STORAGE.clear()
