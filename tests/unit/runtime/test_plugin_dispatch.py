# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Unit tests for PluginIntelligence dispatch engine wiring.

Validates:
    - wire_dispatchers() creates and stores dispatch engine with 5 handlers (7 routes)
    - start_consumers() uses dispatch callback for all 7 intelligence topics
    - start_consumers() returns skipped when engine is not wired (no noop fallback)
    - Dispatch engine is cleared on shutdown
    - INTELLIGENCE_SUBSCRIBE_TOPICS is contract-driven (OMN-2033)

Related:
    - OMN-2031: Replace _noop_handler with MessageDispatchEngine routing
    - OMN-2032: Register all 5 intelligence handlers (7 routes)
    - OMN-2033: Move intelligence topics to contract.yaml declarations
    - OMN-2091: Wire real dependencies into dispatch handlers (Phase 2)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from omniintelligence.runtime.plugin import (
    INTELLIGENCE_SUBSCRIBE_TOPICS,
    PluginIntelligence,
)

# ---------------------------------------------------------------------------
# Autouse fixture: reset introspection single-call guard between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_introspection_guard():
    """Reset the single-call introspection guard between tests.

    wire_dispatchers() calls publish_intelligence_introspection() which sets
    a global guard preventing repeated calls. Without resetting between tests,
    only the first test that calls wire_dispatchers() would succeed.
    """
    from omniintelligence.runtime.introspection import reset_introspection_guard

    reset_introspection_guard()
    yield
    reset_introspection_guard()


# ---------------------------------------------------------------------------
# Per-topic constants for tests that verify specific subscription behaviour.
# These MUST match the subscribe_topics declared in the corresponding
# effect node contract.yaml files (source of truth).
# ---------------------------------------------------------------------------
TOPIC_CLAUDE_HOOK_EVENT = "onex.cmd.omniintelligence.claude-hook-event.v1"
TOPIC_SESSION_OUTCOME = "onex.cmd.omniintelligence.session-outcome.v1"
TOPIC_PATTERN_LIFECYCLE = "onex.cmd.omniintelligence.pattern-lifecycle-transition.v1"

# =============================================================================
# Stubs
# =============================================================================


@dataclass
class _StubContainer:
    """Minimal container stub."""

    service_registry: Any = None


@dataclass
class _StubSubscription:
    """Tracks a single subscription."""

    topic: str
    group_id: str
    on_message: Callable[[Any], Awaitable[None]]
    _unsubscribed: bool = False

    async def unsubscribe(self) -> None:
        self._unsubscribed = True


class _StubEventBus:
    """Event bus stub that tracks subscriptions and can deliver messages."""

    def __init__(self) -> None:
        self.subscriptions: list[_StubSubscription] = []

    async def subscribe(
        self,
        topic: str,
        group_id: str = "",
        on_message: Callable[[Any], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> Callable[[], Awaitable[None]]:
        sub = _StubSubscription(
            topic=topic,
            group_id=group_id,
            on_message=on_message or (lambda _: None),
        )
        self.subscriptions.append(sub)
        return sub.unsubscribe

    def get_subscription(self, topic: str) -> _StubSubscription | None:
        for sub in self.subscriptions:
            if sub.topic == topic:
                return sub
        return None


def _make_config(
    event_bus: Any | None = None,
    correlation_id: UUID | None = None,
) -> Any:
    """Create a minimal ModelDomainPluginConfig-compatible object."""
    from omnibase_infra.runtime.models import ModelDomainPluginConfig

    return ModelDomainPluginConfig(
        container=_StubContainer(),  # type: ignore[arg-type]
        event_bus=event_bus or _StubEventBus(),
        correlation_id=correlation_id or uuid4(),
        input_topic="test.input",
        output_topic="test.output",
        consumer_group="test-consumer",
    )


def _make_mock_pool() -> MagicMock:
    """Create a mock asyncpg pool with async methods.

    The mock pool is used to satisfy wire_dispatchers() which creates
    protocol adapters from the pool. The key methods needed:
    - execute: For AdapterIdempotencyStorePostgres.ensure_table()
    - fetchrow: For AdapterPatternRepositoryPostgres
    - fetch: For AdapterPatternRepositoryPostgres
    """
    pool = MagicMock()
    pool.execute = AsyncMock(return_value="CREATE TABLE")
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetch = AsyncMock(return_value=[])
    pool.close = AsyncMock()
    return pool


async def _wire_plugin(
    plugin: PluginIntelligence,
    config: Any,
) -> Any:
    """Wire dispatchers on a plugin with a mocked pool.

    Sets plugin._pool to a mock and calls wire_dispatchers().
    Returns the wire_dispatchers result.
    """
    plugin._pool = _make_mock_pool()
    return await plugin.wire_dispatchers(config)


# =============================================================================
# Tests: wire_dispatchers
# =============================================================================


class TestPluginWireDispatchers:
    """Validate PluginIntelligence.wire_dispatchers() creates the dispatch engine."""

    @pytest.mark.asyncio
    async def test_wire_dispatchers_creates_engine(self) -> None:
        """wire_dispatchers should create and store a dispatch engine."""
        plugin = PluginIntelligence()
        config = _make_config()

        result = await _wire_plugin(plugin, config)

        assert result.success, f"wire_dispatchers failed: {result.error_message}"
        assert plugin._dispatch_engine is not None
        assert plugin._dispatch_engine.is_frozen

    @pytest.mark.asyncio
    async def test_wire_dispatchers_engine_has_seven_routes(self) -> None:
        """Engine should have exactly 7 routes (5 command + 2 event topics)."""
        plugin = PluginIntelligence()
        config = _make_config()

        await _wire_plugin(plugin, config)

        assert plugin._dispatch_engine is not None
        assert plugin._dispatch_engine.route_count == 7

    @pytest.mark.asyncio
    async def test_wire_dispatchers_engine_has_five_handlers(self) -> None:
        """Engine should have exactly 5 handlers."""
        plugin = PluginIntelligence()
        config = _make_config()

        await _wire_plugin(plugin, config)

        assert plugin._dispatch_engine is not None
        assert plugin._dispatch_engine.handler_count == 5

    @pytest.mark.asyncio
    async def test_wire_dispatchers_returns_resources_created(self) -> None:
        """Result should list dispatch_engine in resources_created."""
        plugin = PluginIntelligence()
        config = _make_config()

        result = await _wire_plugin(plugin, config)

        assert "dispatch_engine" in result.resources_created

    @pytest.mark.asyncio
    async def test_wire_dispatchers_returns_failed_without_pool(self) -> None:
        """wire_dispatchers should return failed result when pool is None."""
        plugin = PluginIntelligence()
        config = _make_config()

        # Do not set plugin._pool -- leave it None
        result = await plugin.wire_dispatchers(config)

        assert not result.success
        assert "pool not initialized" in result.error_message.lower()
        assert plugin._dispatch_engine is None

    @pytest.mark.asyncio
    async def test_wire_dispatchers_returns_failed_on_engine_error(self) -> None:
        """wire_dispatchers should return failed result when engine creation raises."""
        plugin = PluginIntelligence()
        plugin._pool = _make_mock_pool()
        config = _make_config()

        with patch(
            "omniintelligence.runtime.dispatch_handlers.create_intelligence_dispatch_engine",
            side_effect=RuntimeError("handler registration failed"),
        ):
            result = await plugin.wire_dispatchers(config)

        assert not result.success
        assert "handler registration failed" in result.error_message
        assert plugin._dispatch_engine is None


# =============================================================================
# Tests: start_consumers with dispatch engine
# =============================================================================


class TestPluginStartConsumersDispatch:
    """Validate start_consumers routes claude-hook-event through dispatch engine."""

    @pytest.mark.asyncio
    async def test_all_topics_subscribed(self) -> None:
        """All 7 intelligence topics must be subscribed."""
        event_bus = _StubEventBus()
        plugin = PluginIntelligence()
        config = _make_config(event_bus=event_bus)

        await _wire_plugin(plugin, config)
        result = await plugin.start_consumers(config)

        assert result.success
        assert len(event_bus.subscriptions) == len(INTELLIGENCE_SUBSCRIBE_TOPICS)

        subscribed_topics = {sub.topic for sub in event_bus.subscriptions}
        for topic in INTELLIGENCE_SUBSCRIBE_TOPICS:
            assert topic in subscribed_topics

    @pytest.mark.asyncio
    async def test_claude_hook_uses_dispatch_callback(self) -> None:
        """Claude hook event topic should NOT use noop handler."""
        event_bus = _StubEventBus()
        plugin = PluginIntelligence()
        config = _make_config(event_bus=event_bus)

        await _wire_plugin(plugin, config)
        await plugin.start_consumers(config)

        sub = event_bus.get_subscription(TOPIC_CLAUDE_HOOK_EVENT)
        assert sub is not None

        # The handler should be the dispatch callback, not the noop
        # Noop handler has "noop" in its qualname; dispatch callback does not
        handler_name = getattr(sub.on_message, "__qualname__", "")
        assert "noop" not in handler_name.lower(), (
            f"Claude hook topic should use dispatch callback, "
            f"got handler: {handler_name}"
        )

    @pytest.mark.asyncio
    async def test_claude_hook_dispatch_processes_message(self) -> None:
        """Dispatching a message through claude-hook should reach the handler."""
        event_bus = _StubEventBus()
        plugin = PluginIntelligence()
        config = _make_config(event_bus=event_bus)

        await _wire_plugin(plugin, config)
        await plugin.start_consumers(config)

        sub = event_bus.get_subscription(TOPIC_CLAUDE_HOOK_EVENT)
        assert sub is not None

        # Simulate a message delivery
        payload = {
            "event_type": "UserPromptSubmit",
            "session_id": "test-session",
            "correlation_id": str(uuid4()),
            "timestamp_utc": "2025-01-15T10:30:00Z",
            "payload": {"prompt": "test prompt"},
        }

        # Pass as dict (inmemory event bus style) - should not raise
        await sub.on_message(payload)

    @pytest.mark.asyncio
    async def test_all_topics_use_dispatch_callback(self) -> None:
        """All 7 intelligence topics should use dispatch callback (not noop)."""
        event_bus = _StubEventBus()
        plugin = PluginIntelligence()
        config = _make_config(event_bus=event_bus)

        await _wire_plugin(plugin, config)
        await plugin.start_consumers(config)

        for topic in INTELLIGENCE_SUBSCRIBE_TOPICS:
            sub = event_bus.get_subscription(topic)
            assert sub is not None
            handler_name = getattr(sub.on_message, "__qualname__", "")
            assert "noop" not in handler_name.lower(), (
                f"Topic {topic} should use dispatch callback, "
                f"got handler: {handler_name}"
            )

    @pytest.mark.asyncio
    async def test_session_outcome_dispatch_processes_message(self) -> None:
        """Dispatching a message through session-outcome should reach the handler."""
        event_bus = _StubEventBus()
        plugin = PluginIntelligence()
        config = _make_config(event_bus=event_bus)

        await _wire_plugin(plugin, config)
        await plugin.start_consumers(config)

        sub = event_bus.get_subscription(TOPIC_SESSION_OUTCOME)
        assert sub is not None

        payload = {
            "session_id": str(uuid4()),
            "success": True,
            "correlation_id": str(uuid4()),
        }

        # Pass as dict (inmemory event bus style) - should not raise
        await sub.on_message(payload)

    @pytest.mark.asyncio
    async def test_pattern_lifecycle_dispatch_processes_message(self) -> None:
        """Dispatching a message through pattern-lifecycle should reach the handler."""
        event_bus = _StubEventBus()
        plugin = PluginIntelligence()
        config = _make_config(event_bus=event_bus)

        await _wire_plugin(plugin, config)
        await plugin.start_consumers(config)

        sub = event_bus.get_subscription(TOPIC_PATTERN_LIFECYCLE)
        assert sub is not None

        payload = {
            "pattern_id": str(uuid4()),
            "request_id": str(uuid4()),
            "from_status": "provisional",
            "to_status": "validated",
            "trigger": "promote",
            "correlation_id": str(uuid4()),
        }

        # Pass as dict (inmemory event bus style) - should not raise
        await sub.on_message(payload)


# =============================================================================
# Tests: start_consumers without dispatch engine
# =============================================================================


class TestPluginStartConsumersSkipped:
    """Validate skipped behavior when dispatch engine is not wired."""

    @pytest.mark.asyncio
    async def test_returns_skipped_without_engine(self) -> None:
        """Without wire_dispatchers, start_consumers should return skipped."""
        plugin = PluginIntelligence()
        config = _make_config()

        # Skip wire_dispatchers -- go straight to start_consumers
        result = await plugin.start_consumers(config)

        # skipped() returns success=True with a skip message
        assert result.success
        assert "skipped" in result.message.lower()

    @pytest.mark.asyncio
    async def test_no_subscriptions_without_engine(self) -> None:
        """Without wire_dispatchers, no topics should be subscribed."""
        event_bus = _StubEventBus()
        plugin = PluginIntelligence()
        config = _make_config(event_bus=event_bus)

        # Skip wire_dispatchers -- go straight to start_consumers
        await plugin.start_consumers(config)

        assert len(event_bus.subscriptions) == 0


# =============================================================================
# Tests: shutdown clears dispatch engine
# =============================================================================


class TestPluginShutdownClearsEngine:
    """Validate shutdown clears the dispatch engine reference."""

    @pytest.mark.asyncio
    async def test_shutdown_clears_engine(self) -> None:
        """After shutdown, _dispatch_engine should be None."""
        plugin = PluginIntelligence()
        config = _make_config()

        await _wire_plugin(plugin, config)
        assert plugin._dispatch_engine is not None

        await plugin.shutdown(config)
        assert plugin._dispatch_engine is None
