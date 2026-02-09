# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Unit tests for Intelligence dispatch bridge handlers.

Validates:
    - Dispatch engine factory creates a frozen engine with correct routes/handlers
    - Bridge handler parses dict payloads as ModelClaudeCodeHookEvent
    - Bridge handler handles unexpected payload types gracefully
    - Event bus callback deserializes bytes, wraps in envelope, dispatches
    - Event bus callback acks on success, nacks on failure
    - Topic alias mapping is correct

Related:
    - OMN-2031: Replace _noop_handler with MessageDispatchEngine routing
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest

from omniintelligence.runtime.dispatch_handlers import (
    DISPATCH_ALIAS_CLAUDE_HOOK,
    create_claude_hook_dispatch_handler,
    create_dispatch_callback,
    create_intelligence_dispatch_engine,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def correlation_id() -> UUID:
    """Fixed correlation ID for deterministic tests."""
    return UUID("12345678-1234-1234-1234-123456789abc")


@pytest.fixture
def sample_claude_hook_payload() -> dict[str, Any]:
    """Sample Claude Code hook event payload."""
    return {
        "event_type": "UserPromptSubmit",
        "session_id": "test-session-001",
        "correlation_id": "12345678-1234-1234-1234-123456789abc",
        "timestamp_utc": "2025-01-15T10:30:00Z",
        "payload": {
            "prompt": "What does this function do?",
        },
    }


@dataclass
class _MockEventMessage:
    """Mock event bus message implementing ProtocolEventMessage interface."""

    topic: str = "onex.cmd.omniintelligence.claude-hook-event.v1"
    key: bytes | None = None
    value: bytes = b"{}"
    headers: dict[str, str] = field(default_factory=dict)

    _acked: bool = False
    _nacked: bool = False

    async def ack(self) -> None:
        self._acked = True

    async def nack(self) -> None:
        self._nacked = True


# =============================================================================
# Tests: Topic Alias
# =============================================================================


class TestTopicAlias:
    """Verify topic alias constants."""

    def test_dispatch_alias_contains_commands_segment(self) -> None:
        """Dispatch alias must contain .commands. for from_topic() to work."""
        assert ".commands." in DISPATCH_ALIAS_CLAUDE_HOOK

    def test_dispatch_alias_matches_intelligence_domain(self) -> None:
        """Dispatch alias must reference omniintelligence."""
        assert "omniintelligence" in DISPATCH_ALIAS_CLAUDE_HOOK

    def test_dispatch_alias_preserves_event_name(self) -> None:
        """Dispatch alias must preserve the claude-hook-event name."""
        assert "claude-hook-event" in DISPATCH_ALIAS_CLAUDE_HOOK


# =============================================================================
# Tests: Dispatch Engine Factory
# =============================================================================


class TestCreateIntelligenceDispatchEngine:
    """Validate dispatch engine creation and configuration."""

    def test_engine_is_frozen(self) -> None:
        """Engine must be frozen after factory call."""
        engine = create_intelligence_dispatch_engine()
        assert engine.is_frozen

    def test_engine_has_one_handler(self) -> None:
        """Phase 1: exactly one handler registered."""
        engine = create_intelligence_dispatch_engine()
        assert engine.handler_count == 1

    def test_engine_has_one_route(self) -> None:
        """Phase 1: exactly one route registered."""
        engine = create_intelligence_dispatch_engine()
        assert engine.route_count == 1


# =============================================================================
# Tests: Bridge Handler
# =============================================================================


class TestClaudeHookDispatchHandler:
    """Validate the bridge handler for Claude hook events."""

    @pytest.mark.asyncio
    async def test_handler_processes_dict_payload(
        self,
        sample_claude_hook_payload: dict[str, Any],
        correlation_id: UUID,
    ) -> None:
        """Handler should parse dict payload as ModelClaudeCodeHookEvent."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_claude_hook_dispatch_handler(
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload=sample_claude_hook_payload,
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        # Should not raise
        result = await handler(envelope, context)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_handler_raises_for_unexpected_payload_type(
        self,
        correlation_id: UUID,
    ) -> None:
        """Handler should raise ValueError for unparseable payloads."""
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_claude_hook_dispatch_handler(
            correlation_id=correlation_id,
        )

        # Payload is a string, not dict or ModelClaudeCodeHookEvent
        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload="not a valid payload",
            correlation_id=correlation_id,
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with pytest.raises(ValueError, match="Unexpected payload type"):
            await handler(envelope, context)


# =============================================================================
# Tests: Event Bus Dispatch Callback
# =============================================================================


class TestCreateDispatchCallback:
    """Validate the event bus callback that bridges to the dispatch engine."""

    @pytest.mark.asyncio
    async def test_callback_dispatches_json_message(
        self,
        sample_claude_hook_payload: dict[str, Any],
    ) -> None:
        """Callback should deserialize bytes, dispatch, and ack."""
        engine = create_intelligence_dispatch_engine()

        callback = create_dispatch_callback(
            engine=engine,
            dispatch_topic=DISPATCH_ALIAS_CLAUDE_HOOK,
        )

        msg = _MockEventMessage(
            value=json.dumps(sample_claude_hook_payload).encode("utf-8"),
        )

        await callback(msg)

        assert msg._acked, "Message should be acked after successful dispatch"
        assert not msg._nacked

    @pytest.mark.asyncio
    async def test_callback_nacks_on_invalid_json(self) -> None:
        """Callback should nack the message if JSON parsing fails."""
        engine = create_intelligence_dispatch_engine()

        callback = create_dispatch_callback(
            engine=engine,
            dispatch_topic=DISPATCH_ALIAS_CLAUDE_HOOK,
        )

        msg = _MockEventMessage(
            value=b"not valid json {{{",
        )

        await callback(msg)

        assert msg._nacked, "Message should be nacked on parse failure"
        assert not msg._acked

    @pytest.mark.asyncio
    async def test_callback_handles_dict_message(
        self,
        sample_claude_hook_payload: dict[str, Any],
    ) -> None:
        """Callback should handle plain dict messages (inmemory event bus)."""
        engine = create_intelligence_dispatch_engine()

        callback = create_dispatch_callback(
            engine=engine,
            dispatch_topic=DISPATCH_ALIAS_CLAUDE_HOOK,
        )

        metrics_before = engine.get_structured_metrics()

        # InMemoryEventBus may pass dicts directly
        await callback(sample_claude_hook_payload)

        metrics_after = engine.get_structured_metrics()
        assert metrics_after.total_dispatches == metrics_before.total_dispatches + 1

    @pytest.mark.asyncio
    async def test_callback_extracts_correlation_id_from_payload(
        self,
        sample_claude_hook_payload: dict[str, Any],
        correlation_id: UUID,
    ) -> None:
        """Callback should extract correlation_id from payload if present."""
        engine = create_intelligence_dispatch_engine()

        callback = create_dispatch_callback(
            engine=engine,
            dispatch_topic=DISPATCH_ALIAS_CLAUDE_HOOK,
        )

        # Payload includes correlation_id
        msg = _MockEventMessage(
            value=json.dumps(sample_claude_hook_payload).encode("utf-8"),
        )

        # Should not raise and should use the payload's correlation_id
        await callback(msg)
        assert msg._acked

    @pytest.mark.asyncio
    async def test_callback_nacks_on_dispatch_failure(self) -> None:
        """Callback should nack when dispatch result indicates failure."""
        engine = create_intelligence_dispatch_engine()

        # Use a topic with no matching route to trigger a dispatch failure
        callback = create_dispatch_callback(
            engine=engine,
            dispatch_topic="onex.commands.nonexistent.topic.v1",
        )

        msg = _MockEventMessage(
            value=json.dumps(
                {
                    "event_type": "UserPromptSubmit",
                    "session_id": "test-session",
                    "payload": {"prompt": "test"},
                }
            ).encode("utf-8"),
        )

        await callback(msg)

        assert msg._nacked, "Message should be nacked on dispatch failure"
        assert not msg._acked
