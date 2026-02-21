# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Registry for WatchdogEffect dependencies.

Manages the active observer instance, observer type, and Kafka publisher
at module level for test isolation and runtime wiring.

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
from typing import TYPE_CHECKING, Any, cast

from omniintelligence.nodes.node_watchdog_effect.models.enum_watchdog_observer_type import (
    EnumWatchdogObserverType,
)

if TYPE_CHECKING:
    from omniintelligence.protocols import ProtocolKafkaPublisher

logger = logging.getLogger(__name__)

__all__ = ["RegistryWatchdogEffect"]

# Module-level storage for injected dependencies
_HANDLER_STORAGE: dict[str, object] = {}


class RegistryWatchdogEffect:
    """Registry for WatchdogEffect node dependencies.

    Stores the active observer instance, observer type, and Kafka publisher
    at module level for test isolation and runtime wiring.

    Usage::

        from omniintelligence.nodes.node_watchdog_effect.registry import (
            RegistryWatchdogEffect,
        )

        RegistryWatchdogEffect.register_publisher(kafka_producer)
        RegistryWatchdogEffect.register_config(config)
    """

    _OBSERVER_KEY = "observer"
    _OBSERVER_TYPE_KEY = "observer_type"
    _PUBLISHER_KEY = "kafka_publisher"
    _CONFIG_KEY = "watchdog_config"

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
        _HANDLER_STORAGE[RegistryWatchdogEffect._OBSERVER_KEY] = observer
        _HANDLER_STORAGE[RegistryWatchdogEffect._OBSERVER_TYPE_KEY] = observer_type

    @staticmethod
    def register_publisher(publisher: ProtocolKafkaPublisher) -> None:
        """Register the Kafka publisher for crawl-requested.v1 emission.

        Args:
            publisher: Kafka publisher implementing ``ProtocolKafkaPublisher``
                with an async ``publish(topic, key, value)`` method.

        Raises:
            TypeError: If publisher is missing the required ``publish`` method.
        """
        if not callable(getattr(publisher, "publish", None)):
            raise TypeError(
                f"Publisher missing required 'publish' method. "
                f"Got {type(publisher).__name__}"
            )

        if RegistryWatchdogEffect._PUBLISHER_KEY in _HANDLER_STORAGE:
            logger.warning(
                "Re-registering Kafka publisher for WatchdogEffect. "
                "This may indicate lifecycle issues or missing clear() in tests.",
            )

        _HANDLER_STORAGE[RegistryWatchdogEffect._PUBLISHER_KEY] = publisher

    @staticmethod
    def get_observer() -> Any | None:
        """Return the active observer instance, or None if not started."""
        return _HANDLER_STORAGE.get(RegistryWatchdogEffect._OBSERVER_KEY)

    @staticmethod
    def get_observer_type() -> EnumWatchdogObserverType | None:
        """Return the observer type, or None if not started."""
        result = _HANDLER_STORAGE.get(RegistryWatchdogEffect._OBSERVER_TYPE_KEY)
        return cast("EnumWatchdogObserverType | None", result)

    @staticmethod
    def get_publisher() -> ProtocolKafkaPublisher | None:
        """Return the registered Kafka publisher, or None if not registered."""
        result = _HANDLER_STORAGE.get(RegistryWatchdogEffect._PUBLISHER_KEY)
        return cast("ProtocolKafkaPublisher | None", result)

    @staticmethod
    def clear() -> None:
        """Clear all registered dependencies.

        MUST be called in test setup and teardown to prevent test pollution.
        """
        _HANDLER_STORAGE.clear()
