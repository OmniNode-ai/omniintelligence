# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for node_crawl_scheduler_effect node tests.

Provides protocol conformance assertions and mock implementations for
unit testing governance invariants without requiring a live Kafka broker
or a real database connection.

Reference:
    - OMN-2384: CrawlSchedulerEffect implementation
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_crawl_scheduler_effect.handlers.debounce_state import (
    DebounceStateManager,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.models import (
    CrawlerType,
    EnumTriggerSource,
    ModelCrawlRequestedEvent,
    ModelCrawlSchedulerConfig,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.node import (
    NodeCrawlSchedulerEffect,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.registry.registry_crawl_scheduler_effect import (
    RegistryCrawlSchedulerEffect,
)

# =============================================================================
# Protocol conformance assertion (canonical location per CLAUDE.md)
# =============================================================================


def assert_node_protocol_conformance() -> None:
    """Assert that NodeCrawlSchedulerEffect conforms to the NodeEffect protocol.

    This is the canonical isinstance() check referenced in CLAUDE.md:
        nodes/*/node_tests/conftest.py — protocol conformance checks.
    """
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer
    from omnibase_core.nodes.node_effect import NodeEffect

    container = ModelONEXContainer()
    node = NodeCrawlSchedulerEffect(container)
    assert isinstance(node, NodeEffect), (
        f"NodeCrawlSchedulerEffect must be an instance of NodeEffect. Got: {type(node)}"
    )


# =============================================================================
# __all__
# =============================================================================

__all__ = [
    "MockKafkaPublisher",
    "assert_node_protocol_conformance",
    "clear_registry",
    "correlation_id",
    "debounce_state",
    "fresh_config",
    "mock_kafka_publisher",
    "now_utc",
    "sample_crawl_requested_event",
    "source_ref",
]


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


# =============================================================================
# Pytest fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def clear_registry() -> object:
    """Clear RegistryCrawlSchedulerEffect before and after every test.

    This is the required fixture per registry_crawl_scheduler_effect.py
    to prevent test pollution via module-level storage.
    """
    RegistryCrawlSchedulerEffect.clear()
    yield
    RegistryCrawlSchedulerEffect.clear()


@pytest.fixture
def mock_kafka_publisher() -> MockKafkaPublisher:
    """Provide a fresh MockKafkaPublisher for each test."""
    return MockKafkaPublisher()


@pytest.fixture
def debounce_state() -> DebounceStateManager:
    """Provide a fresh DebounceStateManager for each test (not the singleton)."""
    return DebounceStateManager()


@pytest.fixture
def fresh_config() -> ModelCrawlSchedulerConfig:
    """Provide a ModelCrawlSchedulerConfig with default debounce windows."""
    return ModelCrawlSchedulerConfig()


@pytest.fixture
def now_utc() -> datetime:
    """Provide a fixed UTC-aware datetime for deterministic time-based tests."""
    return datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def source_ref() -> str:
    """Provide a canonical source reference string."""
    return "/Volumes/PRO-G40/Code/omniintelligence"


@pytest.fixture
def correlation_id() -> UUID:
    """Provide a correlation ID for distributed tracing tests."""
    return uuid4()


@pytest.fixture
def sample_crawl_requested_event(
    source_ref: str,
    correlation_id: UUID,
) -> ModelCrawlRequestedEvent:
    """Provide a valid ModelCrawlRequestedEvent for handler tests."""
    return ModelCrawlRequestedEvent(
        crawl_type=CrawlerType.FILESYSTEM,
        crawl_scope="omninode/omniintelligence",
        source_ref=source_ref,
        correlation_id=correlation_id,
        requested_at_utc=datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC).isoformat(),
        trigger_source=EnumTriggerSource.MANUAL,
    )
