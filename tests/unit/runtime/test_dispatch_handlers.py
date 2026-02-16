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
    - OMN-2032: Register all 5 intelligence handlers (7 routes)
    - OMN-2091: Wire real dependencies into dispatch handlers (Phase 2)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from omniintelligence.runtime.dispatch_handlers import (
    DISPATCH_ALIAS_CLAUDE_HOOK,
    DISPATCH_ALIAS_PATTERN_DISCOVERED,
    DISPATCH_ALIAS_PATTERN_LEARNED,
    DISPATCH_ALIAS_PATTERN_LEARNING_CMD,
    DISPATCH_ALIAS_PATTERN_LIFECYCLE,
    DISPATCH_ALIAS_SESSION_OUTCOME,
    create_claude_hook_dispatch_handler,
    create_dispatch_callback,
    create_intelligence_dispatch_engine,
    create_pattern_lifecycle_dispatch_handler,
    create_pattern_storage_dispatch_handler,
    create_session_outcome_dispatch_handler,
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


@pytest.fixture
def mock_repository() -> MagicMock:
    """Mock ProtocolPatternRepository for dispatch handler tests."""
    repo = MagicMock()
    repo.fetch = AsyncMock(return_value=[])
    repo.fetchrow = AsyncMock(return_value=None)
    repo.execute = AsyncMock(return_value="UPDATE 0")
    return repo


@pytest.fixture
def mock_idempotency_store() -> MagicMock:
    """Mock ProtocolIdempotencyStore for dispatch handler tests."""
    store = MagicMock()
    store.exists = AsyncMock(return_value=False)
    store.record = AsyncMock(return_value=None)
    store.check_and_record = AsyncMock(return_value=False)
    return store


@pytest.fixture
def mock_intent_classifier() -> MagicMock:
    """Mock ProtocolIntentClassifier for dispatch handler tests."""
    classifier = MagicMock()
    mock_output = MagicMock()
    mock_output.intent_category = "unknown"
    mock_output.confidence = 0.0
    mock_output.keywords = []
    mock_output.secondary_intents = []
    classifier.compute = AsyncMock(return_value=mock_output)
    return classifier


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
# Tests: Protocol Conformance (dispatch_handlers locals vs handler canonicals)
# =============================================================================
# dispatch_handlers.py duplicates four protocols to avoid circular imports.
# These tests verify the local copies have not diverged from the canonical
# definitions in handler modules. If a handler protocol gains or renames a
# method, these tests will fail, signalling that the dispatch_handlers copy
# must be updated.


class TestProtocolConformance:
    """Verify dispatch_handlers protocols match canonical handler protocols."""

    @staticmethod
    def _abstract_methods(proto: type) -> set[str]:
        """Extract the set of protocol method names via __protocol_attrs__."""
        # runtime_checkable Protocol stores checked attrs here
        return set(getattr(proto, "__protocol_attrs__", set()))

    def test_pattern_repository_matches_lifecycle_handler(self) -> None:
        """Local ProtocolPatternRepository must match lifecycle handler's."""
        from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
            ProtocolPatternRepository as CanonicalRepo,
        )
        from omniintelligence.runtime.dispatch_handlers import (
            ProtocolPatternRepository as LocalRepo,
        )

        canonical = self._abstract_methods(CanonicalRepo)
        local = self._abstract_methods(LocalRepo)
        assert local == canonical, (
            f"ProtocolPatternRepository diverged: local={local}, canonical={canonical}"
        )

    def test_idempotency_store_matches_lifecycle_handler(self) -> None:
        """Local ProtocolIdempotencyStore must match lifecycle handler's."""
        from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
            ProtocolIdempotencyStore as CanonicalStore,
        )
        from omniintelligence.runtime.dispatch_handlers import (
            ProtocolIdempotencyStore as LocalStore,
        )

        canonical = self._abstract_methods(CanonicalStore)
        local = self._abstract_methods(LocalStore)
        assert local == canonical, (
            f"ProtocolIdempotencyStore diverged: local={local}, canonical={canonical}"
        )

    def test_intent_classifier_matches_hook_handler(self) -> None:
        """Local ProtocolIntentClassifier must match hook handler's."""
        from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
            ProtocolIntentClassifier as CanonicalClassifier,
        )
        from omniintelligence.runtime.dispatch_handlers import (
            ProtocolIntentClassifier as LocalClassifier,
        )

        canonical = self._abstract_methods(CanonicalClassifier)
        local = self._abstract_methods(LocalClassifier)
        assert local == canonical, (
            f"ProtocolIntentClassifier diverged: local={local}, canonical={canonical}"
        )

    def test_kafka_publisher_matches_hook_handler(self) -> None:
        """Local ProtocolKafkaPublisher must match hook handler's."""
        from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
            ProtocolKafkaPublisher as CanonicalPublisher,
        )
        from omniintelligence.runtime.dispatch_handlers import (
            ProtocolKafkaPublisher as LocalPublisher,
        )

        canonical = self._abstract_methods(CanonicalPublisher)
        local = self._abstract_methods(LocalPublisher)
        assert local == canonical, (
            f"ProtocolKafkaPublisher diverged: local={local}, canonical={canonical}"
        )


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

    # --- Session Outcome alias ---

    def test_session_outcome_alias_contains_commands_segment(self) -> None:
        """Session outcome alias must contain .commands. for from_topic()."""
        assert ".commands." in DISPATCH_ALIAS_SESSION_OUTCOME

    def test_session_outcome_alias_matches_intelligence_domain(self) -> None:
        """Session outcome alias must reference omniintelligence."""
        assert "omniintelligence" in DISPATCH_ALIAS_SESSION_OUTCOME

    def test_session_outcome_alias_preserves_event_name(self) -> None:
        """Session outcome alias must preserve the session-outcome name."""
        assert "session-outcome" in DISPATCH_ALIAS_SESSION_OUTCOME

    # --- Pattern Lifecycle alias ---

    def test_pattern_lifecycle_alias_contains_commands_segment(self) -> None:
        """Pattern lifecycle alias must contain .commands. for from_topic()."""
        assert ".commands." in DISPATCH_ALIAS_PATTERN_LIFECYCLE

    def test_pattern_lifecycle_alias_matches_intelligence_domain(self) -> None:
        """Pattern lifecycle alias must reference omniintelligence."""
        assert "omniintelligence" in DISPATCH_ALIAS_PATTERN_LIFECYCLE

    def test_pattern_lifecycle_alias_preserves_event_name(self) -> None:
        """Pattern lifecycle alias must preserve the transition name."""
        assert "pattern-lifecycle-transition" in DISPATCH_ALIAS_PATTERN_LIFECYCLE

    # --- Pattern Learned alias ---

    def test_pattern_learned_alias_contains_events_segment(self) -> None:
        """Pattern learned alias must contain .events. for from_topic()."""
        assert ".events." in DISPATCH_ALIAS_PATTERN_LEARNED

    def test_pattern_learned_alias_matches_intelligence_domain(self) -> None:
        """Pattern learned alias must reference omniintelligence."""
        assert "omniintelligence" in DISPATCH_ALIAS_PATTERN_LEARNED

    def test_pattern_learned_alias_preserves_event_name(self) -> None:
        """Pattern learned alias must preserve the pattern-learned name."""
        assert "pattern-learned" in DISPATCH_ALIAS_PATTERN_LEARNED

    # --- Pattern Discovered alias ---

    def test_pattern_discovered_alias_contains_events_segment(self) -> None:
        """Pattern discovered alias must contain .events. for from_topic()."""
        assert ".events." in DISPATCH_ALIAS_PATTERN_DISCOVERED

    def test_pattern_discovered_alias_preserves_event_name(self) -> None:
        """Pattern discovered alias must preserve the discovered name."""
        assert "discovered" in DISPATCH_ALIAS_PATTERN_DISCOVERED

    # --- Pattern Learning CMD alias ---

    def test_pattern_learning_cmd_alias_contains_commands_segment(self) -> None:
        """Pattern learning cmd alias must contain .commands. for from_topic()."""
        assert ".commands." in DISPATCH_ALIAS_PATTERN_LEARNING_CMD

    def test_pattern_learning_cmd_alias_matches_intelligence_domain(self) -> None:
        """Pattern learning cmd alias must reference omniintelligence."""
        assert "omniintelligence" in DISPATCH_ALIAS_PATTERN_LEARNING_CMD

    def test_pattern_learning_cmd_alias_preserves_event_name(self) -> None:
        """Pattern learning cmd alias must preserve the pattern-learning name."""
        assert "pattern-learning" in DISPATCH_ALIAS_PATTERN_LEARNING_CMD


# =============================================================================
# Tests: Dispatch Engine Factory
# =============================================================================


class TestCreateIntelligenceDispatchEngine:
    """Validate dispatch engine creation and configuration."""

    def test_engine_is_frozen(
        self,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
    ) -> None:
        """Engine must be frozen after factory call."""
        engine = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
        )
        assert engine.is_frozen

    def test_engine_has_five_handlers(
        self,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
    ) -> None:
        """All 5 intelligence domain handlers must be registered."""
        engine = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
        )
        assert engine.handler_count == 5

    def test_engine_has_seven_routes(
        self,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
    ) -> None:
        """All 7 intelligence domain routes must be registered."""
        engine = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
        )
        assert engine.route_count == 7


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
        mock_intent_classifier: MagicMock,
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
            intent_classifier=mock_intent_classifier,
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
        mock_intent_classifier: MagicMock,
    ) -> None:
        """Handler should raise ValueError for unparseable payloads."""
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_claude_hook_dispatch_handler(
            intent_classifier=mock_intent_classifier,
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

    @pytest.mark.asyncio
    async def test_handler_reshapes_flat_omniclaude_payload(
        self,
        correlation_id: UUID,
        mock_intent_classifier: MagicMock,
    ) -> None:
        """Handler should reshape flat omniclaude publisher payloads.

        The omniclaude publisher emits events with all fields at the top level
        (no nested payload wrapper, emitted_at instead of timestamp_utc).
        The handler should reshape into ModelClaudeCodeHookEvent format.
        """
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        flat_payload = {
            "session_id": "test-session-flat",
            "event_type": "UserPromptSubmit",
            "correlation_id": str(correlation_id),
            "prompt_preview": "Hello world",
            "prompt_length": 11,
            "prompt_b64": "SGVsbG8gd29ybGQ=",
            "causation_id": None,
            "emitted_at": "2026-02-14T23:21:25.925410+00:00",
            "schema_version": "1.0.0",
        }

        handler = create_claude_hook_dispatch_handler(
            intent_classifier=mock_intent_classifier,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload=flat_payload,
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        result = await handler(envelope, context)
        assert isinstance(result, str)


# =============================================================================
# Tests: Session Outcome Handler
# =============================================================================


class TestSessionOutcomeDispatchHandler:
    """Validate the bridge handler for session outcome events."""

    @pytest.mark.asyncio
    async def test_handler_processes_dict_payload(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Handler should parse dict payload and return empty string."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_session_outcome_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "session_id": str(uuid4()),
                "success": True,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        result = await handler(envelope, context)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_handler_raises_for_non_dict_payload(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Handler should raise ValueError for non-dict payloads."""
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_session_outcome_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload="not a dict payload",
            correlation_id=correlation_id,
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with pytest.raises(ValueError, match="Unexpected payload type"):
            await handler(envelope, context)

    @pytest.mark.asyncio
    async def test_handler_rejects_dict_missing_session_id(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Handler should raise ValueError when dict payload lacks session_id."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_session_outcome_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "success": True,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with pytest.raises(ValueError, match="missing required field 'session_id'"):
            await handler(envelope, context)


# =============================================================================
# Tests: Session Outcome -- `outcome` field mapping (OMN-2189 Bug 1)
# =============================================================================


class TestSessionOutcomeFieldMapping:
    """Validate that session outcome reads `outcome` field, not `success`.

    OMN-2189 Bug 1: The wire payload sends ``outcome: "success"`` but the
    dispatch handler was reading ``success: true``. This caused every session
    outcome to be recorded as FAILED because ``payload.get("success", False)``
    always returned False when the field was not present.

    These tests verify the fix maps via ClaudeCodeSessionOutcome.is_successful().
    """

    @pytest.mark.asyncio
    async def test_outcome_success_maps_to_success_true(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """outcome='success' must result in success=True passed to handler."""
        from unittest.mock import patch

        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_session_outcome_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        session_id = uuid4()
        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "session_id": str(session_id),
                "outcome": "success",
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with patch(
            "omniintelligence.nodes.node_pattern_feedback_effect.handlers"
            ".record_session_outcome",
            new_callable=AsyncMock,
        ) as mock_record:
            mock_result = MagicMock()
            mock_result.patterns_updated = 0
            mock_record.return_value = mock_result

            await handler(envelope, context)

            mock_record.assert_called_once()
            # record_session_outcome(session_id=..., success=..., ...)
            # success is passed as keyword arg
            call_kwargs = mock_record.call_args.kwargs
            assert call_kwargs["success"] is True, (
                f"Expected success=True for outcome='success', got {call_kwargs['success']}"
            )

    @pytest.mark.asyncio
    async def test_outcome_failed_maps_to_success_false(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """outcome='failed' must result in success=False passed to handler."""
        from unittest.mock import patch

        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_session_outcome_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        session_id = uuid4()
        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "session_id": str(session_id),
                "outcome": "failed",
                "failure_reason": "test failure",
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with patch(
            "omniintelligence.nodes.node_pattern_feedback_effect.handlers"
            ".record_session_outcome",
            new_callable=AsyncMock,
        ) as mock_record:
            mock_result = MagicMock()
            mock_result.patterns_updated = 0
            mock_record.return_value = mock_result

            await handler(envelope, context)

            mock_record.assert_called_once()
            all_kwargs = mock_record.call_args.kwargs
            assert all_kwargs["success"] is False, (
                f"Expected success=False for outcome='failed', got {all_kwargs['success']}"
            )

    @pytest.mark.asyncio
    async def test_outcome_abandoned_maps_to_success_false(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """outcome='abandoned' must result in success=False."""
        from unittest.mock import patch

        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_session_outcome_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        session_id = uuid4()
        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "session_id": str(session_id),
                "outcome": "abandoned",
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with patch(
            "omniintelligence.nodes.node_pattern_feedback_effect.handlers"
            ".record_session_outcome",
            new_callable=AsyncMock,
        ) as mock_record:
            mock_result = MagicMock()
            mock_result.patterns_updated = 0
            mock_record.return_value = mock_result

            await handler(envelope, context)

            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args.kwargs
            assert call_kwargs["success"] is False, (
                f"Expected success=False for outcome='abandoned', got {call_kwargs['success']}"
            )

    @pytest.mark.asyncio
    async def test_legacy_success_field_still_works(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Legacy payload with `success: true` (no `outcome`) must still work."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_session_outcome_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        session_id = uuid4()
        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "session_id": str(session_id),
                "success": True,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        # Legacy format should not raise
        await handler(envelope, context)

    @pytest.mark.asyncio
    async def test_outcome_field_takes_precedence_over_success(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """When both `outcome` and `success` present, `outcome` wins."""
        from unittest.mock import patch

        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_session_outcome_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        session_id = uuid4()
        # outcome says "failed" but success says True -- outcome should win
        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "session_id": str(session_id),
                "outcome": "failed",
                "success": True,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with patch(
            "omniintelligence.nodes.node_pattern_feedback_effect.handlers"
            ".record_session_outcome",
            new_callable=AsyncMock,
        ) as mock_record:
            mock_result = MagicMock()
            mock_result.patterns_updated = 0
            mock_record.return_value = mock_result

            await handler(envelope, context)

            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args.kwargs
            assert call_kwargs["success"] is False, (
                f"Expected success=False for outcome='failed' (overriding success=True), "
                f"got {call_kwargs['success']}"
            )


# =============================================================================
# Tests: Pattern Lifecycle Handler
# =============================================================================


class TestPatternLifecycleDispatchHandler:
    """Validate the bridge handler for pattern lifecycle transition events."""

    @pytest.mark.asyncio
    async def test_handler_processes_dict_payload(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
    ) -> None:
        """Handler should parse dict payload and return empty string."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_lifecycle_dispatch_handler(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "pattern_id": str(uuid4()),
                "request_id": str(uuid4()),
                "from_status": "provisional",
                "to_status": "validated",
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        result = await handler(envelope, context)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_handler_raises_for_non_dict_payload(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
    ) -> None:
        """Handler should raise ValueError for non-dict payloads."""
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_lifecycle_dispatch_handler(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload=12345,
            correlation_id=correlation_id,
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with pytest.raises(ValueError, match="Unexpected payload type"):
            await handler(envelope, context)

    @pytest.mark.asyncio
    async def test_handler_raises_for_invalid_session_uuid(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Handler should raise ValueError with clear message for invalid UUID."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_session_outcome_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "session_id": "not-a-valid-uuid",
                "success": True,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with pytest.raises(ValueError, match="Invalid UUID for 'session_id'"):
            await handler(envelope, context)

    @pytest.mark.asyncio
    async def test_handler_rejects_dict_missing_pattern_id(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
    ) -> None:
        """Handler should raise ValueError when dict payload lacks pattern_id."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_lifecycle_dispatch_handler(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "from_status": "provisional",
                "to_status": "validated",
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with pytest.raises(ValueError, match="missing required field 'pattern_id'"):
            await handler(envelope, context)

    @pytest.mark.asyncio
    async def test_handler_raises_for_invalid_lifecycle_status(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
    ) -> None:
        """Handler should raise ValueError with clear message for invalid enum."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_lifecycle_dispatch_handler(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "pattern_id": str(uuid4()),
                "request_id": str(uuid4()),
                "from_status": "nonexistent_status",
                "to_status": "validated",
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with pytest.raises(
            ValueError, match="Invalid lifecycle status for 'from_status'"
        ):
            await handler(envelope, context)

    @pytest.mark.asyncio
    async def test_handler_raises_for_invalid_transition_at(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
    ) -> None:
        """Handler should raise ValueError with clear message for invalid datetime."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_lifecycle_dispatch_handler(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "pattern_id": str(uuid4()),
                "request_id": str(uuid4()),
                "from_status": "provisional",
                "to_status": "validated",
                "transition_at": "not-a-datetime",
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "command"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with pytest.raises(
            ValueError, match="Invalid ISO datetime for 'transition_at'"
        ):
            await handler(envelope, context)


# =============================================================================
# Tests: Pattern Storage Handler
# =============================================================================


class TestPatternStorageDispatchHandler:
    """Validate the bridge handler for pattern storage events.

    Tests cover:
        - Happy path with all fields present
        - Missing pattern_id / discovery_id rejection
        - Empty signature rejection
        - Confidence clamping (below 0.5 and above 1.0)
        - Version clamping (below 1)
        - Kafka optional (SQL still works without producer)
        - ForeignKeyViolationError surfaced as ValueError
        - discovery_id fallback when pattern_id absent
        - Invalid session IDs dropped from source_session_ids
    """

    @pytest.mark.asyncio
    async def test_pattern_storage_handler_happy_path(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Valid payload with all fields must execute SQL and publish to Kafka."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        mock_kafka = MagicMock()
        mock_kafka.publish = AsyncMock(return_value=None)

        handler = create_pattern_storage_dispatch_handler(
            repository=mock_repository,
            kafka_producer=mock_kafka,
            correlation_id=correlation_id,
        )

        pattern_id = uuid4()
        session_id_1 = uuid4()
        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "event_type": "PatternLearned",
                "pattern_id": str(pattern_id),
                "signature": "def foo(): pass",
                "signature_hash": "abc123hash",
                "domain_id": "python",
                "domain_version": "1.0.0",
                "confidence": 0.85,
                "version": 2,
                "source_session_ids": [str(session_id_1)],
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "event"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        result = await handler(envelope, context)
        assert isinstance(result, str)

        # SQL must have been executed
        mock_repository.execute.assert_called_once()
        call_args = mock_repository.execute.call_args
        # Positional args: SQL, pattern_id, signature, signature_hash,
        #   domain_id, domain_version, confidence, version, source_session_ids
        assert call_args[0][1] == pattern_id
        assert call_args[0][2] == "def foo(): pass"
        assert call_args[0][3] == "abc123hash"
        assert call_args[0][4] == "python"
        assert call_args[0][6] == 0.85
        assert call_args[0][7] == 2
        assert call_args[0][8] == [session_id_1]

        # Kafka must have been called
        mock_kafka.publish.assert_called_once()
        kafka_call = mock_kafka.publish.call_args
        assert kafka_call.kwargs["key"] == str(pattern_id)
        assert kafka_call.kwargs["value"]["event_type"] == "PatternStored"

    @pytest.mark.asyncio
    async def test_pattern_storage_handler_missing_pattern_id(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Payload without pattern_id or discovery_id generates a new UUID."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_storage_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "event_type": "PatternLearned",
                "signature": "def bar(): pass",
                "signature_hash": "hash456",
                "confidence": 0.7,
                "version": 1,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "event"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        # Should not raise -- generates a new UUID internally
        result = await handler(envelope, context)
        assert isinstance(result, str)

        # SQL should have been called with a generated UUID
        mock_repository.execute.assert_called_once()
        stored_pattern_id = mock_repository.execute.call_args[0][1]
        assert isinstance(stored_pattern_id, UUID)

    @pytest.mark.asyncio
    async def test_pattern_storage_handler_empty_signature_rejected(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Empty signature must be rejected with ValueError."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_storage_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "event_type": "PatternLearned",
                "pattern_id": str(uuid4()),
                "signature": "",
                "signature_hash": "hash789",
                "confidence": 0.8,
                "version": 1,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "event"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with pytest.raises(ValueError, match="missing pattern_signature"):
            await handler(envelope, context)

        # SQL must NOT have been called
        mock_repository.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_pattern_storage_handler_confidence_clamped_below(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Confidence below 0.5 must be clamped to 0.5."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_storage_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "event_type": "PatternLearned",
                "pattern_id": str(uuid4()),
                "signature": "def baz(): pass",
                "signature_hash": "hash_clamp_low",
                "confidence": 0.1,
                "version": 1,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "event"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        await handler(envelope, context)

        mock_repository.execute.assert_called_once()
        stored_confidence = mock_repository.execute.call_args[0][6]
        assert stored_confidence == 0.5, (
            f"Expected confidence clamped to 0.5, got {stored_confidence}"
        )

    @pytest.mark.asyncio
    async def test_pattern_storage_handler_confidence_clamped_above(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Confidence above 1.0 must be clamped to 1.0."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_storage_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "event_type": "PatternLearned",
                "pattern_id": str(uuid4()),
                "signature": "def baz(): pass",
                "signature_hash": "hash_clamp_high",
                "confidence": 5.0,
                "version": 1,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "event"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        await handler(envelope, context)

        mock_repository.execute.assert_called_once()
        stored_confidence = mock_repository.execute.call_args[0][6]
        assert stored_confidence == 1.0, (
            f"Expected confidence clamped to 1.0, got {stored_confidence}"
        )

    @pytest.mark.asyncio
    async def test_pattern_storage_handler_version_clamped(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Version below 1 must be clamped to 1."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_storage_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "event_type": "PatternLearned",
                "pattern_id": str(uuid4()),
                "signature": "def baz(): pass",
                "signature_hash": "hash_ver_clamp",
                "confidence": 0.7,
                "version": 0,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "event"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        await handler(envelope, context)

        mock_repository.execute.assert_called_once()
        stored_version = mock_repository.execute.call_args[0][7]
        assert stored_version == 1, (
            f"Expected version clamped to 1, got {stored_version}"
        )

    @pytest.mark.asyncio
    async def test_pattern_storage_handler_kafka_optional(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """No Kafka producer must not prevent SQL from executing."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_storage_dispatch_handler(
            repository=mock_repository,
            kafka_producer=None,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "event_type": "PatternLearned",
                "pattern_id": str(uuid4()),
                "signature": "def no_kafka(): pass",
                "signature_hash": "hash_no_kafka",
                "confidence": 0.9,
                "version": 1,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "event"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        result = await handler(envelope, context)
        assert isinstance(result, str)

        # SQL must still have been called
        mock_repository.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_pattern_storage_handler_fk_violation(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """ForeignKeyViolationError from repository must raise ValueError."""
        from asyncpg import ForeignKeyViolationError
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        mock_repository.execute = AsyncMock(
            side_effect=ForeignKeyViolationError(
                "insert or update on table violates foreign key constraint"
            ),
        )

        handler = create_pattern_storage_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "event_type": "PatternLearned",
                "pattern_id": str(uuid4()),
                "signature": "def fk_test(): pass",
                "signature_hash": "hash_fk",
                "domain_id": "nonexistent_domain",
                "confidence": 0.7,
                "version": 1,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "event"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with pytest.raises(ValueError, match="Unknown domain_id"):
            await handler(envelope, context)

    @pytest.mark.asyncio
    async def test_pattern_storage_handler_discovery_id_fallback(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """discovery_id must be used when pattern_id is absent."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_storage_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        discovery_id = uuid4()
        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "event_type": "PatternDiscovered",
                "discovery_id": str(discovery_id),
                "signature": "def discovered(): pass",
                "signature_hash": "hash_disc",
                "confidence": 0.75,
                "version": 1,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "event"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        await handler(envelope, context)

        mock_repository.execute.assert_called_once()
        stored_pattern_id = mock_repository.execute.call_args[0][1]
        assert stored_pattern_id == discovery_id, (
            f"Expected discovery_id {discovery_id} to be used as pattern_id, "
            f"got {stored_pattern_id}"
        )

    @pytest.mark.asyncio
    async def test_pattern_storage_handler_drops_invalid_session_ids(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Invalid UUIDs in source_session_ids must be silently dropped."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_storage_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        valid_session_id = uuid4()
        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "event_type": "PatternLearned",
                "pattern_id": str(uuid4()),
                "signature": "def sessions(): pass",
                "signature_hash": "hash_sessions",
                "confidence": 0.8,
                "version": 1,
                "source_session_ids": [
                    str(valid_session_id),
                    "not-a-uuid",
                    "also-invalid",
                ],
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "event"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        await handler(envelope, context)

        mock_repository.execute.assert_called_once()
        stored_session_ids = mock_repository.execute.call_args[0][8]
        assert len(stored_session_ids) == 1, (
            f"Expected 1 valid session ID, got {len(stored_session_ids)}"
        )
        assert stored_session_ids[0] == valid_session_id

    @pytest.mark.asyncio
    async def test_pattern_storage_handler_raises_for_non_dict_payload(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Handler should raise ValueError for non-dict payloads."""
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_storage_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload="not a dict payload",
            correlation_id=correlation_id,
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with pytest.raises(ValueError, match="Unexpected payload type"):
            await handler(envelope, context)

    @pytest.mark.asyncio
    async def test_pattern_storage_handler_missing_signature_hash_rejected(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Missing signature_hash must be rejected with ValueError."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_storage_dispatch_handler(
            repository=mock_repository,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "event_type": "PatternLearned",
                "pattern_id": str(uuid4()),
                "signature": "def no_hash(): pass",
                "confidence": 0.7,
                "version": 1,
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "event"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with pytest.raises(ValueError, match="missing signature_hash"):
            await handler(envelope, context)

        mock_repository.execute.assert_not_called()


# =============================================================================
# Tests: Event Bus Dispatch Callback
# =============================================================================


class TestCreateDispatchCallback:
    """Validate the event bus callback that bridges to the dispatch engine."""

    @pytest.mark.asyncio
    async def test_callback_dispatches_json_message(
        self,
        sample_claude_hook_payload: dict[str, Any],
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
    ) -> None:
        """Callback should deserialize bytes, dispatch, and ack."""
        engine = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
        )

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
    async def test_callback_acks_on_invalid_json(
        self,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
    ) -> None:
        """Callback should ACK malformed JSON to prevent infinite retry.

        Malformed JSON will never succeed on retry, so the message is ACKed
        (not nacked) and routed to DLQ as best-effort.
        """
        engine = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
        )

        callback = create_dispatch_callback(
            engine=engine,
            dispatch_topic=DISPATCH_ALIAS_CLAUDE_HOOK,
        )

        msg = _MockEventMessage(
            value=b"not valid json {{{",
        )

        await callback(msg)

        assert msg._acked, "Message should be acked to prevent infinite retry"
        assert not msg._nacked

    @pytest.mark.asyncio
    async def test_callback_handles_dict_message(
        self,
        sample_claude_hook_payload: dict[str, Any],
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
    ) -> None:
        """Callback should handle plain dict messages (inmemory event bus)."""
        engine = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
        )

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
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
    ) -> None:
        """Callback should extract correlation_id from payload if present."""
        engine = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
        )

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
    async def test_callback_nacks_on_dispatch_failure(
        self,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
    ) -> None:
        """Callback should nack when dispatch result indicates failure."""
        engine = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
        )

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
