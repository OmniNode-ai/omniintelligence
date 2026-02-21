# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for node_watchdog_effect node tests.

Provides protocol conformance assertions and mock implementations for
unit testing governance invariants without requiring a live Kafka broker,
real filesystem observer, or native OS APIs.

Reference:
    - OMN-2386: WatchdogEffect implementation
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from omniintelligence.nodes.node_watchdog_effect.models import (
    EnumWatchdogObserverType,
    ModelWatchdogConfig,
)
from omniintelligence.nodes.node_watchdog_effect.node import NodeWatchdogEffect
from omniintelligence.nodes.node_watchdog_effect.registry.registry_watchdog_effect import (
    RegistryWatchdogEffect,
)

# =============================================================================
# Protocol conformance assertion (canonical location per CLAUDE.md)
# =============================================================================


def assert_node_protocol_conformance() -> None:
    """Assert that NodeWatchdogEffect conforms to the NodeEffect protocol.

    This is the canonical isinstance() check referenced in CLAUDE.md:
        nodes/*/node_tests/conftest.py — protocol conformance checks.
    """
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer
    from omnibase_core.nodes.node_effect import NodeEffect

    container = ModelONEXContainer()
    node = NodeWatchdogEffect(container)
    assert isinstance(node, NodeEffect), (
        f"NodeWatchdogEffect must be an instance of NodeEffect. Got: {type(node)}"
    )


# =============================================================================
# Mock implementations
# =============================================================================


class MockKafkaPublisher:
    """Minimal in-memory Kafka publisher mock.

    Records all published messages for assertion in tests.
    The ``publish`` method is an AsyncMock with ``_record_and_publish``
    wired as its ``side_effect`` so that ``published_messages`` is
    populated on every ``await publisher.publish(...)`` call.
    """

    def __init__(self) -> None:
        self.published_messages: list[dict[str, object]] = []
        self.publish = AsyncMock(side_effect=self._record_and_publish)

    async def _record_and_publish(self, topic: str, key: str, value: object) -> None:
        self.published_messages.append({"topic": topic, "key": key, "value": value})

    def reset(self) -> None:
        """Clear all recorded messages and reset the mock."""
        self.publish.reset_mock()
        self.published_messages.clear()


class MockObserver:
    """Minimal mock for a watchdog observer.

    Tracks whether start(), stop(), and join() were called,
    and records scheduled watches for assertions.
    """

    def __init__(
        self, observer_type: EnumWatchdogObserverType = EnumWatchdogObserverType.POLLING
    ) -> None:
        self.observer_type = observer_type
        self.started = False
        self.stopped = False
        self.joined = False
        self.scheduled_watches: list[dict[str, Any]] = []

    def start(self) -> None:
        """Record that the observer was started."""
        self.started = True

    def stop(self) -> None:
        """Record that the observer was stopped."""
        self.stopped = True

    def join(self, timeout: float | None = None) -> None:
        """Record that the observer was joined.

        Args:
            timeout: Optional join timeout in seconds (mirrors
                ``threading.Thread.join`` signature).  Accepted but not
                used by the mock — the mock always returns immediately.
        """
        self.joined = True

    def schedule(self, handler: Any, path: str, recursive: bool = True) -> MagicMock:
        """Record a scheduled watch and return a mock watch handle."""
        self.scheduled_watches.append(
            {"handler": handler, "path": path, "recursive": recursive}
        )
        return MagicMock()

    def is_alive(self) -> bool:
        """Return True if started and not stopped."""
        return self.started and not self.stopped


def make_mock_observer_factory(
    observer_type: EnumWatchdogObserverType = EnumWatchdogObserverType.POLLING,
) -> tuple[Any, type[MockObserver]]:
    """Return a (factory_callable, observer_class) pair for injection into start_watching().

    The factory callable returns a fresh MockObserver each time it is called.

    Args:
        observer_type: The observer type to report.

    Returns:
        Tuple of (factory_fn, MockObserver_class).
    """
    created_observers: list[MockObserver] = []

    def factory() -> tuple[MockObserver, EnumWatchdogObserverType]:
        obs = MockObserver(observer_type=observer_type)
        created_observers.append(obs)
        return obs, observer_type

    factory.created_observers = created_observers  # type: ignore[attr-defined]
    return factory, MockObserver


# =============================================================================
# Pytest fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def clear_registry() -> object:
    """Clear RegistryWatchdogEffect before and after every test.

    This is the required fixture per registry_watchdog_effect.py
    to prevent test pollution via module-level storage.
    """
    RegistryWatchdogEffect.clear()
    yield
    RegistryWatchdogEffect.clear()


@pytest.fixture
def mock_kafka_publisher() -> MockKafkaPublisher:
    """Provide a fresh MockKafkaPublisher for each test."""
    return MockKafkaPublisher()


@pytest.fixture
def default_config(tmp_path: Any) -> ModelWatchdogConfig:
    """Provide a ModelWatchdogConfig with a temp directory as the watched path.

    Using tmp_path avoids watching real filesystem paths in unit tests
    and prevents interference with the developer's ~/.claude/ directory.
    """
    return ModelWatchdogConfig(
        watched_paths=(str(tmp_path),),
        crawl_scope="omninode/test",
    )


@pytest.fixture
def polling_observer_factory() -> Any:
    """Provide a mock observer factory that returns a PollingObserver mock."""
    factory, _ = make_mock_observer_factory(EnumWatchdogObserverType.POLLING)
    return factory


@pytest.fixture
def fsevents_observer_factory() -> Any:
    """Provide a mock observer factory that returns an FSEventsObserver mock."""
    factory, _ = make_mock_observer_factory(EnumWatchdogObserverType.FSEVENTS)
    return factory


# =============================================================================
# __all__
# =============================================================================

__all__ = [
    "MockKafkaPublisher",
    "MockObserver",
    "assert_node_protocol_conformance",
    "clear_registry",
    "default_config",
    "fsevents_observer_factory",
    "make_mock_observer_factory",
    "mock_kafka_publisher",
    "polling_observer_factory",
]
