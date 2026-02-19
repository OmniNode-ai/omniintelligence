# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Unit tests for PluginIntelligence dispatch engine wiring.

Validates:
    - wire_dispatchers() creates and stores dispatch engine with 6 handlers (8 routes)
    - start_consumers() uses dispatch callback for all intelligence topics (contract-driven)
    - start_consumers() returns skipped when engine is not wired (no noop fallback)
    - Dispatch engine is cleared on shutdown
    - INTELLIGENCE_SUBSCRIBE_TOPICS is contract-driven (OMN-2033)

Related:
    - OMN-2031: Replace _noop_handler with MessageDispatchEngine routing
    - OMN-2032: Register all 6 intelligence handlers (8 routes)
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
from omnibase_core.protocols.event_bus.protocol_event_bus import ProtocolEventBus

from omniintelligence.runtime.plugin import (
    INTELLIGENCE_SUBSCRIBE_TOPICS,
    PluginIntelligence,
    _introspection_publishing_enabled,
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

    async def publish(
        self,
        topic: str,
        key: bytes | None,
        value: bytes,
        headers: Any = None,
    ) -> None:
        return None

    async def publish_envelope(self, envelope: Any, topic: str) -> None:
        return None

    async def broadcast_to_environment(
        self,
        command: str,
        payload: dict[str, Any],
        target_environment: str | None = None,
    ) -> None:
        return None

    async def send_to_group(
        self,
        command: str,
        payload: dict[str, Any],
        target_group: str,
    ) -> None:
        return None

    async def start(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def health_check(self) -> Any:
        return {"healthy": True, "connected": True}

    async def start_consuming(self) -> None:
        return None

    @property
    def adapter(self) -> Any:
        return None

    @property
    def environment(self) -> str:
        return "test"

    @property
    def group(self) -> str:
        return "test-group"

    def get_subscription(self, topic: str) -> _StubSubscription | None:
        for sub in self.subscriptions:
            if sub.topic == topic:
                return sub
        return None


assert isinstance(_StubEventBus(), ProtocolEventBus)


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
    protocol adapters from the pool.
    """
    pool = MagicMock()
    pool.execute = AsyncMock(return_value="CREATE TABLE")
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetch = AsyncMock(return_value=[])
    pool.close = AsyncMock()
    return pool


def _make_mock_runtime() -> MagicMock:
    """Create a mock PostgresRepositoryRuntime with a mock pool."""
    runtime = MagicMock()
    runtime._pool = _make_mock_pool()
    runtime.contract = MagicMock()
    runtime.call = AsyncMock(return_value=None)

    # Mock the contract ops for AdapterPatternStore._build_positional_args
    runtime.contract.ops = {}
    return runtime


def _make_mock_idempotency_store() -> MagicMock:
    """Create a mock omnibase_infra idempotency store."""
    store = MagicMock()
    store.check_and_record = AsyncMock(return_value=True)
    store.is_processed = AsyncMock(return_value=False)
    store.mark_processed = AsyncMock()
    store.shutdown = AsyncMock()
    return store


async def _wire_plugin(
    plugin: PluginIntelligence,
    config: Any,
) -> Any:
    """Wire dispatchers on a plugin with mocked infra resources.

    Sets plugin._pool, _pattern_runtime, and _idempotency_store to mocks
    and calls wire_dispatchers().
    Returns the wire_dispatchers result.
    """
    plugin._pool = _make_mock_pool()
    plugin._pattern_runtime = _make_mock_runtime()
    plugin._idempotency_store = _make_mock_idempotency_store()
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
    async def test_wire_dispatchers_engine_has_eight_routes(self) -> None:
        """Engine should have exactly 8 routes (6 command + 2 event topics, OMN-2339 adds compliance-evaluate)."""
        plugin = PluginIntelligence()
        config = _make_config()

        await _wire_plugin(plugin, config)

        assert plugin._dispatch_engine is not None
        assert plugin._dispatch_engine.route_count == 8

    @pytest.mark.asyncio
    async def test_wire_dispatchers_engine_has_six_handlers(self) -> None:
        """Engine should have exactly 6 handlers (OMN-2339 adds compliance-evaluate)."""
        plugin = PluginIntelligence()
        config = _make_config()

        await _wire_plugin(plugin, config)

        assert plugin._dispatch_engine is not None
        assert plugin._dispatch_engine.handler_count == 6

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
        assert "not initialized" in result.error_message.lower()
        assert plugin._dispatch_engine is None

    @pytest.mark.asyncio
    async def test_wire_dispatchers_returns_failed_on_engine_error(self) -> None:
        """wire_dispatchers should return failed result when engine creation raises."""
        plugin = PluginIntelligence()
        plugin._pool = _make_mock_pool()
        plugin._pattern_runtime = _make_mock_runtime()
        plugin._idempotency_store = _make_mock_idempotency_store()
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
        """All 8 intelligence topics must be subscribed."""
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
        """All 8 intelligence topics should use dispatch callback (not noop)."""
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


# =============================================================================
# Tests: OMNIINTELLIGENCE_PUBLISH_INTROSPECTION gate (OMN-2342)
# =============================================================================


class TestIntrospectionPublishingGate:
    """Validate the OMNIINTELLIGENCE_PUBLISH_INTROSPECTION env var gate.

    R1: Exactly 1 heartbeat source — only the designated container publishes.
    R2: Workers still process intelligence events (only publishing is gated).
    R3: Env var defaults to false/off safely.
    """

    # -------------------------------------------------------------------------
    # _introspection_publishing_enabled() unit tests
    # -------------------------------------------------------------------------

    @pytest.mark.unit
    def test_enabled_when_var_is_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns True when env var is 'true'."""
        monkeypatch.setenv("OMNIINTELLIGENCE_PUBLISH_INTROSPECTION", "true")
        assert _introspection_publishing_enabled() is True

    @pytest.mark.unit
    def test_enabled_when_var_is_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns True when env var is '1'."""
        monkeypatch.setenv("OMNIINTELLIGENCE_PUBLISH_INTROSPECTION", "1")
        assert _introspection_publishing_enabled() is True

    @pytest.mark.unit
    def test_enabled_when_var_is_yes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns True when env var is 'yes'."""
        monkeypatch.setenv("OMNIINTELLIGENCE_PUBLISH_INTROSPECTION", "yes")
        assert _introspection_publishing_enabled() is True

    @pytest.mark.unit
    def test_enabled_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns True for 'TRUE', 'True', 'YES', 'Yes' (case-insensitive)."""
        for value in ("TRUE", "True", "YES", "Yes"):
            monkeypatch.setenv("OMNIINTELLIGENCE_PUBLISH_INTROSPECTION", value)
            assert _introspection_publishing_enabled() is True, (
                f"Expected True for value={value!r}"
            )

    @pytest.mark.unit
    def test_disabled_when_var_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns False (R3: safe default) when env var is not set."""
        monkeypatch.delenv("OMNIINTELLIGENCE_PUBLISH_INTROSPECTION", raising=False)
        assert _introspection_publishing_enabled() is False

    @pytest.mark.unit
    def test_disabled_when_var_is_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns False when env var is 'false'."""
        monkeypatch.setenv("OMNIINTELLIGENCE_PUBLISH_INTROSPECTION", "false")
        assert _introspection_publishing_enabled() is False

    @pytest.mark.unit
    def test_disabled_when_var_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns False when env var is empty string."""
        monkeypatch.setenv("OMNIINTELLIGENCE_PUBLISH_INTROSPECTION", "")
        assert _introspection_publishing_enabled() is False

    @pytest.mark.unit
    def test_disabled_when_var_is_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns False when env var is '0'."""
        monkeypatch.setenv("OMNIINTELLIGENCE_PUBLISH_INTROSPECTION", "0")
        assert _introspection_publishing_enabled() is False

    # -------------------------------------------------------------------------
    # wire_dispatchers() gate integration tests
    # -------------------------------------------------------------------------

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_wire_dispatchers_skips_introspection_when_gate_off(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """R3: introspection is skipped when OMNIINTELLIGENCE_PUBLISH_INTROSPECTION absent.

        Validates R1 (no duplicate publishers) and R2 (dispatch engine still
        created; handler wiring unaffected).
        """
        monkeypatch.delenv("OMNIINTELLIGENCE_PUBLISH_INTROSPECTION", raising=False)

        plugin = PluginIntelligence()
        config = _make_config()

        result = await _wire_plugin(plugin, config)

        assert result.success, f"wire_dispatchers failed: {result.error_message}"
        # Dispatch engine must still be created (R2: processing unaffected)
        assert plugin._dispatch_engine is not None
        # No introspection nodes registered (R1: no publishing from this container)
        assert plugin._introspection_nodes == []
        assert plugin._introspection_proxies == []
        # _event_bus not captured (gate off → shutdown skips publish_intelligence_shutdown)
        assert plugin._event_bus is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_wire_dispatchers_publishes_introspection_when_gate_on(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """R1: introspection is published when OMNIINTELLIGENCE_PUBLISH_INTROSPECTION=true."""
        monkeypatch.setenv("OMNIINTELLIGENCE_PUBLISH_INTROSPECTION", "true")

        event_bus = _StubEventBus()
        # Make publish_envelope available so introspection proxy can publish
        event_bus.publish_envelope = AsyncMock(return_value=None)

        plugin = PluginIntelligence()
        config = _make_config(event_bus=event_bus)

        result = await _wire_plugin(plugin, config)

        assert result.success, f"wire_dispatchers failed: {result.error_message}"
        assert plugin._dispatch_engine is not None
        # Introspection nodes and proxies registered (gate is open)
        assert len(plugin._introspection_nodes) > 0
        assert len(plugin._introspection_proxies) > 0
        # _event_bus captured (gate on → shutdown path will call publish_intelligence_shutdown)
        assert plugin._event_bus is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_wire_dispatchers_gate_off_still_starts_consumers(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """R2: workers without gate still subscribe to all intelligence topics."""
        monkeypatch.delenv("OMNIINTELLIGENCE_PUBLISH_INTROSPECTION", raising=False)

        event_bus = _StubEventBus()
        plugin = PluginIntelligence()
        config = _make_config(event_bus=event_bus)

        await _wire_plugin(plugin, config)
        result = await plugin.start_consumers(config)

        assert result.success
        # All topics subscribed (event processing unaffected by the gate)
        subscribed_topics = {sub.topic for sub in event_bus.subscriptions}
        for topic in INTELLIGENCE_SUBSCRIBE_TOPICS:
            assert topic in subscribed_topics, (
                f"Topic {topic} not subscribed despite gate being off"
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_shutdown_clears_event_bus_when_gate_on(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When gate is on, shutdown clears _event_bus and publishes shutdown introspection."""
        monkeypatch.setenv("OMNIINTELLIGENCE_PUBLISH_INTROSPECTION", "true")

        event_bus = _StubEventBus()
        event_bus.publish_envelope = AsyncMock(return_value=None)
        plugin = PluginIntelligence()
        config = _make_config(event_bus=event_bus)

        result = await _wire_plugin(plugin, config)
        assert result.success
        assert plugin._event_bus is not None  # captured during wire

        await plugin.shutdown(config)
        assert plugin._event_bus is None  # cleared after shutdown
        # publish_intelligence_shutdown must have attempted to publish via the event bus
        assert event_bus.publish_envelope.called, (
            "shutdown must call publish_intelligence_shutdown which publishes "
            "via event_bus.publish_envelope"
        )
