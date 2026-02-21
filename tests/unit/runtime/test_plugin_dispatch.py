# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Unit tests for PluginIntelligence dispatch engine wiring.

Validates:
    - wire_dispatchers() creates and stores dispatch engine with 9 handlers (13 routes)
    - start_consumers() uses dispatch callback for all intelligence topics (contract-driven)
    - start_consumers() returns skipped when engine is not wired (no noop fallback)
    - Dispatch engine is cleared on shutdown
    - INTELLIGENCE_SUBSCRIBE_TOPICS is contract-driven (OMN-2033)

Related:
    - OMN-2031: Replace _noop_handler with MessageDispatchEngine routing
    - OMN-2032: Register all 6 intelligence handlers (8 routes)
    - OMN-2033: Move intelligence topics to contract.yaml declarations
    - OMN-2091: Wire real dependencies into dispatch handlers (Phase 2)
    - OMN-2430: NodeCrawlSchedulerEffect adds 2 handlers, 2 routes (9 handlers, 13 routes); NodeWatchdogEffect has no Kafka subscribe topics and adds no dispatch routes
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
    _INTELLIGENCE_CONSUMER_GROUP_DEFAULT,
    _INTELLIGENCE_CONSUMER_GROUP_ENV_VAR,
    INTELLIGENCE_SUBSCRIBE_TOPICS,
    PluginIntelligence,
    _intelligence_consumer_group,
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
    plugin._handshake_validated = (
        True  # bypass guard — these tests don't exercise handshake
    )
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
    async def test_wire_dispatchers_engine_has_twelve_routes(self) -> None:
        """Engine should have exactly 12 routes (OMN-2384 adds crawl-scheduler routes; OMN-2424 adds 2 projection routes; OMN-2430 adds WatchdogEffect — no new dispatch routes)."""
        plugin = PluginIntelligence()
        config = _make_config()

        await _wire_plugin(plugin, config)

        assert plugin._dispatch_engine is not None
        assert plugin._dispatch_engine.route_count == 12

    @pytest.mark.asyncio
    async def test_wire_dispatchers_engine_has_nine_handlers(self) -> None:
        """Engine should have exactly 9 handlers (OMN-2384 adds crawl-scheduler handlers; OMN-2424 adds pattern-projection handler; OMN-2430 adds WatchdogEffect — no new dispatch handlers)."""
        plugin = PluginIntelligence()
        config = _make_config()

        await _wire_plugin(plugin, config)

        assert plugin._dispatch_engine is not None
        assert plugin._dispatch_engine.handler_count == 9

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


# =============================================================================
# Tests: shared consumer group (OMN-2439)
# =============================================================================


class TestSharedConsumerGroup:
    """Validate that all containers use the same Kafka consumer group (OMN-2439).

    All runtime containers (omninode-runtime, omninode-runtime-effects,
    runtime-worker-*) must subscribe to intelligence topics with the SAME
    consumer group ID so Kafka load-balances across them rather than
    delivering each message to every container independently.

    Without a shared group, 3 containers -> 3 independent consumer groups ->
    every hook event processed 3x -> 3x duplicate intent-classified events.
    """

    # -------------------------------------------------------------------------
    # _intelligence_consumer_group() unit tests
    # -------------------------------------------------------------------------

    @pytest.mark.unit
    def test_default_group_is_omniintelligence_hooks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default consumer group is 'omniintelligence-hooks' when env var absent."""
        monkeypatch.delenv(_INTELLIGENCE_CONSUMER_GROUP_ENV_VAR, raising=False)
        assert _intelligence_consumer_group() == _INTELLIGENCE_CONSUMER_GROUP_DEFAULT
        assert _intelligence_consumer_group() == "omniintelligence-hooks"

    @pytest.mark.unit
    def test_env_var_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OMNIINTELLIGENCE_CONSUMER_GROUP overrides the built-in default."""
        monkeypatch.setenv(_INTELLIGENCE_CONSUMER_GROUP_ENV_VAR, "my-custom-group")
        assert _intelligence_consumer_group() == "my-custom-group"

    @pytest.mark.unit
    def test_empty_env_var_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty env var string is treated as absent; default is used."""
        monkeypatch.setenv(_INTELLIGENCE_CONSUMER_GROUP_ENV_VAR, "")
        assert _intelligence_consumer_group() == _INTELLIGENCE_CONSUMER_GROUP_DEFAULT

    @pytest.mark.unit
    def test_whitespace_env_var_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Whitespace-only env var is stripped and treated as absent; default is used."""
        monkeypatch.setenv(_INTELLIGENCE_CONSUMER_GROUP_ENV_VAR, "   ")
        assert _intelligence_consumer_group() == _INTELLIGENCE_CONSUMER_GROUP_DEFAULT

    # -------------------------------------------------------------------------
    # _intelligence_consumer_group() whitespace validation tests (OMN-2438)
    # -------------------------------------------------------------------------

    @pytest.mark.unit
    def test_raises_on_group_with_embedded_spaces(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises ValueError when resolved group contains embedded spaces."""
        monkeypatch.setenv(_INTELLIGENCE_CONSUMER_GROUP_ENV_VAR, "my group")
        with pytest.raises(ValueError, match="whitespace"):
            _intelligence_consumer_group()

    @pytest.mark.unit
    def test_raises_on_group_with_embedded_tab(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises ValueError when resolved group contains an embedded tab."""
        monkeypatch.setenv(_INTELLIGENCE_CONSUMER_GROUP_ENV_VAR, "my\tgroup")
        with pytest.raises(ValueError):
            _intelligence_consumer_group()

    @pytest.mark.unit
    def test_raises_on_group_with_embedded_newline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises ValueError when resolved group contains an embedded newline."""
        monkeypatch.setenv(_INTELLIGENCE_CONSUMER_GROUP_ENV_VAR, "my\ngroup")
        with pytest.raises(ValueError):
            _intelligence_consumer_group()

    # -------------------------------------------------------------------------
    # start_consumers() group_id integration tests
    # -------------------------------------------------------------------------

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_subscriptions_use_shared_group_not_container_group(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All subscriptions use the shared group ID, not config.consumer_group.

        Simulates three different containers by calling start_consumers() with
        three different config.consumer_group values (as each container would
        supply).  All must produce the same group_id on their subscriptions
        so Kafka treats them as members of the same consumer group.
        """
        from omniintelligence.runtime.introspection import reset_introspection_guard

        monkeypatch.delenv(_INTELLIGENCE_CONSUMER_GROUP_ENV_VAR, raising=False)

        container_groups = [
            "onex-runtime-main",
            "onex-runtime-effects",
            "onex-runtime-workers",
        ]

        for container_group in container_groups:
            # autouse fixture only resets between test functions, not between loop iterations
            reset_introspection_guard()

            event_bus = _StubEventBus()
            plugin = PluginIntelligence()
            # Build a config that mimics the per-container ONEX_GROUP_ID
            from omnibase_infra.runtime.models import ModelDomainPluginConfig

            config = ModelDomainPluginConfig(
                container=_StubContainer(),  # type: ignore[arg-type]
                event_bus=event_bus,
                correlation_id=uuid4(),
                input_topic="test.input",
                output_topic="test.output",
                consumer_group=container_group,
            )

            await _wire_plugin(plugin, config)
            result = await plugin.start_consumers(config)
            assert result.success, (
                f"start_consumers failed for container_group={container_group!r}: "
                f"{result.error_message}"
            )
            assert len(event_bus.subscriptions) > 0, (
                f"No subscriptions for container_group={container_group!r}"
            )

            for sub in event_bus.subscriptions:
                assert sub.group_id == _INTELLIGENCE_CONSUMER_GROUP_DEFAULT, (
                    f"Container with consumer_group={container_group!r} used "
                    f"group_id={sub.group_id!r} for topic {sub.topic!r}; "
                    f"expected shared group {_INTELLIGENCE_CONSUMER_GROUP_DEFAULT!r}"
                )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_subscriptions_use_env_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When OMNIINTELLIGENCE_CONSUMER_GROUP is set, that value is used for all topics."""
        custom_group = "intelligence-staging-hooks"
        monkeypatch.setenv(_INTELLIGENCE_CONSUMER_GROUP_ENV_VAR, custom_group)

        event_bus = _StubEventBus()
        plugin = PluginIntelligence()
        config = _make_config(event_bus=event_bus)

        await _wire_plugin(plugin, config)
        await plugin.start_consumers(config)

        for sub in event_bus.subscriptions:
            assert sub.group_id == custom_group, (
                f"Topic {sub.topic!r} used group_id={sub.group_id!r}; "
                f"expected env override {custom_group!r}"
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_all_topics_use_same_group_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All subscribed topics must share a single consumer group ID."""
        monkeypatch.delenv(_INTELLIGENCE_CONSUMER_GROUP_ENV_VAR, raising=False)

        event_bus = _StubEventBus()
        plugin = PluginIntelligence()
        config = _make_config(event_bus=event_bus)

        await _wire_plugin(plugin, config)
        await plugin.start_consumers(config)

        group_ids = {sub.group_id for sub in event_bus.subscriptions}
        assert len(group_ids) == 1, (
            f"Expected all topics to use the same consumer group; "
            f"found {len(group_ids)} distinct group IDs: {group_ids}"
        )
        (actual_group,) = group_ids
        assert actual_group == _INTELLIGENCE_CONSUMER_GROUP_DEFAULT
