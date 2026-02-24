# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Registry for CrawlSchedulerEffect dependencies.

Manages Kafka publisher and scheduler configuration for the node.
Uses the module-level storage pattern established in other effect nodes
to allow test isolation via ``clear()``.

Testing:
    Tests MUST call ``RegistryCrawlSchedulerEffect.clear()`` in setup
    and teardown to prevent test pollution.

    Recommended fixture pattern::

        @pytest.fixture(autouse=True)
        def clear_registry():
            RegistryCrawlSchedulerEffect.clear()
            yield
            RegistryCrawlSchedulerEffect.clear()

Reference: OMN-2384
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from omniintelligence.nodes.node_crawl_scheduler_effect.handlers.debounce_state import (
    DebounceStateManager,
    get_debounce_state,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.models.model_crawl_scheduler_config import (
    ModelCrawlSchedulerConfig,
)

if TYPE_CHECKING:
    from omniintelligence.protocols import ProtocolKafkaPublisher

logger = logging.getLogger(__name__)

__all__ = ["RegistryCrawlSchedulerEffect"]

# Module-level storage for injected dependencies
_HANDLER_STORAGE: dict[str, object] = {}


class RegistryCrawlSchedulerEffect:
    """Registry for CrawlSchedulerEffect node dependencies.

    Stores the Kafka publisher, scheduler configuration, and debounce state
    manager at module level for test isolation and runtime wiring.

    Usage::

        from omniintelligence.nodes.node_crawl_scheduler_effect.registry import (
            RegistryCrawlSchedulerEffect,
        )

        RegistryCrawlSchedulerEffect.register_publisher(kafka_producer)
        RegistryCrawlSchedulerEffect.register_config(config)
    """

    _PUBLISHER_KEY = "kafka_publisher"
    _CONFIG_KEY = "crawl_scheduler_config"
    _DEBOUNCE_STATE_KEY = "debounce_state"

    @staticmethod
    def register_publisher(publisher: ProtocolKafkaPublisher) -> None:
        """Register the Kafka publisher for crawl-tick.v1 emission.

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

        if RegistryCrawlSchedulerEffect._PUBLISHER_KEY in _HANDLER_STORAGE:
            logger.warning(
                "Re-registering Kafka publisher for CrawlSchedulerEffect. "
                "This may indicate lifecycle issues or missing clear() in tests.",
            )

        _HANDLER_STORAGE[RegistryCrawlSchedulerEffect._PUBLISHER_KEY] = publisher

    @staticmethod
    def register_config(config: ModelCrawlSchedulerConfig) -> None:
        """Register the scheduler configuration (debounce windows).

        Args:
            config: Scheduler config with per-crawler-type debounce windows.
        """
        _HANDLER_STORAGE[RegistryCrawlSchedulerEffect._CONFIG_KEY] = config

    @staticmethod
    def register_debounce_state(state: DebounceStateManager) -> None:
        """Register a custom debounce state manager.

        The default debounce state is the module-level singleton from
        ``get_debounce_state()``.  Override in tests to inject a fresh
        instance per test case.

        Args:
            state: DebounceStateManager instance to use.
        """
        _HANDLER_STORAGE[RegistryCrawlSchedulerEffect._DEBOUNCE_STATE_KEY] = state

    @staticmethod
    def get_publisher() -> ProtocolKafkaPublisher | None:
        """Return the registered Kafka publisher, or None if not registered."""
        result = _HANDLER_STORAGE.get(RegistryCrawlSchedulerEffect._PUBLISHER_KEY)
        return cast("ProtocolKafkaPublisher | None", result)

    @staticmethod
    def get_config() -> ModelCrawlSchedulerConfig:
        """Return the registered config, or a default config if not registered."""
        result = _HANDLER_STORAGE.get(RegistryCrawlSchedulerEffect._CONFIG_KEY)
        if result is None:
            return ModelCrawlSchedulerConfig()
        return cast("ModelCrawlSchedulerConfig", result)

    @staticmethod
    def get_debounce_state() -> DebounceStateManager:
        """Return the registered debounce state manager.

        Falls back to the module-level singleton if none was explicitly
        registered.
        """
        result = _HANDLER_STORAGE.get(RegistryCrawlSchedulerEffect._DEBOUNCE_STATE_KEY)
        if result is None:
            return get_debounce_state()
        return cast("DebounceStateManager", result)

    @staticmethod
    def clear() -> None:
        """Clear all registered dependencies.

        MUST be called in test setup and teardown to prevent test pollution.
        Also resets the debounce state singleton if no custom state was
        registered.
        """
        _HANDLER_STORAGE.clear()
        # Reset the module-level singleton debounce state
        get_debounce_state().clear_all()
