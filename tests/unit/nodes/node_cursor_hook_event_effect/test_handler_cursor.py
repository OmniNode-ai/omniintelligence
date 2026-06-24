# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the Cursor Hook Event Effect handler.

Validates that the Cursor node delegates to the shared Claude handler core and
that emitted events / results are correctly tagged ``agent_source="cursor"``,
proving Cursor is an interchangeable-but-distinct dispatcher.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from omnibase_core.enums.hooks import EnumAgentSource
from omnibase_core.enums.hooks.claude_code.enum_claude_code_hook_event_type import (
    EnumClaudeCodeHookEventType,
)
from omnibase_core.enums.hooks.cursor.enum_cursor_hook_event_type import (
    EnumCursorHookEventType,
)
from omnibase_core.models.hooks.claude_code.model_claude_code_hook_event import (
    ModelClaudeCodeHookEvent,
)
from omnibase_core.models.hooks.claude_code.model_claude_code_hook_event_payload import (
    ModelClaudeCodeHookEventPayload,
)

from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
    route_hook_event,
)
from omniintelligence.nodes.node_cursor_hook_event_effect.handlers import (
    HandlerCursorHookEvent,
    route_cursor_hook_event,
)
from omniintelligence.nodes.node_cursor_hook_event_effect.handlers.handler_cursor_event import (
    _to_canonical_event,
)
from omniintelligence.nodes.node_cursor_hook_event_effect.models import (
    EnumHookProcessingStatus,
    ModelCursorHookEvent,
    ModelCursorHookEventPayload,
)
from tests.fixtures.topic_constants import TOPIC_SUFFIX_INTENT_CLASSIFIED_V1

pytestmark = pytest.mark.unit


@pytest.fixture
def cursor_prompt_event() -> ModelCursorHookEvent:
    """Create a sample Cursor prompt-submission event (canonical UserPromptSubmit)."""
    payload = ModelCursorHookEventPayload(
        prompt="Fix the authentication bug in login.py"
    )
    return ModelCursorHookEvent(
        event_type=EnumCursorHookEventType.USER_PROMPT_SUBMIT,
        session_id="cursor-session-123",
        correlation_id=uuid4(),
        timestamp_utc=datetime.now(UTC),
        payload=payload,
    )


class TestCursorIdentity:
    """The Cursor event is its own type and defaults agent_source to cursor."""

    def test_default_agent_source_is_cursor(
        self, cursor_prompt_event: ModelCursorHookEvent
    ) -> None:
        assert cursor_prompt_event.agent_source == "cursor"

    def test_to_canonical_event_preserves_fields(
        self, cursor_prompt_event: ModelCursorHookEvent
    ) -> None:
        canonical = _to_canonical_event(cursor_prompt_event)
        assert isinstance(canonical, ModelClaudeCodeHookEvent)
        # Cursor shares the canonical hook vocabulary, so event_type is preserved.
        assert canonical.event_type == cursor_prompt_event.event_type
        assert canonical.session_id == cursor_prompt_event.session_id
        assert canonical.correlation_id == cursor_prompt_event.correlation_id
        assert canonical.timestamp_utc == cursor_prompt_event.timestamp_utc


class TestRouteCursorHookEvent:
    """route_cursor_hook_event delegates to the shared core, tagged as cursor."""

    @pytest.mark.asyncio
    async def test_classifies_and_tags_agent_source(
        self, cursor_prompt_event: ModelCursorHookEvent
    ) -> None:
        mock_classifier = MagicMock()
        mock_output = MagicMock()
        mock_output.intent_category = "debugging"
        mock_output.confidence = 0.92
        mock_output.keywords = ["authentication", "bug", "login"]
        mock_output.secondary_intents = []
        mock_classifier.compute = AsyncMock(return_value=mock_output)

        result = await route_cursor_hook_event(
            event=cursor_prompt_event,
            intent_classifier=mock_classifier,
        )

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.intent_result is not None
        assert result.intent_result.intent_category == "debugging"
        assert result.metadata["agent_source"] == "cursor"

    @pytest.mark.asyncio
    async def test_emitted_intent_payload_tagged_cursor(
        self, cursor_prompt_event: ModelCursorHookEvent
    ) -> None:
        mock_producer = MagicMock()
        mock_producer.publish = AsyncMock(return_value=None)

        result = await route_cursor_hook_event(
            event=cursor_prompt_event,
            kafka_producer=mock_producer,
            publish_topic=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
        )

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.intent_result is not None
        assert result.intent_result.emitted_to_kafka is True
        mock_producer.publish.assert_called_once()

        call = mock_producer.publish.call_args
        kafka_payload = call.kwargs.get("value") or call[1].get("value")
        assert kafka_payload["agent_source"] == "cursor"
        assert kafka_payload["provenance"]["source_node"] == "cursor_hook_event_effect"

    @pytest.mark.asyncio
    async def test_handler_class_delegates(
        self, cursor_prompt_event: ModelCursorHookEvent
    ) -> None:
        handler = HandlerCursorHookEvent()
        result = await handler.handle(cursor_prompt_event)
        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.metadata["agent_source"] == "cursor"


class TestAgentSourceEnumSeam:
    """route_hook_event routes EnumAgentSource; claude and cursor stay distinct.

    H.4 regression: the ``agent_source`` seam is a real ``EnumAgentSource``, not a
    bare string. A canonical hook event consumed with
    ``agent_source=EnumAgentSource.CURSOR`` must be tagged distinctly from the
    default claude path; the legacy bare-string seam must still coerce; and an
    unrecognized source must be rejected rather than silently mis-attributed.
    """

    @staticmethod
    def _canonical_prompt_event() -> ModelClaudeCodeHookEvent:
        return ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT,
            session_id="canonical-session-1",
            correlation_id=uuid4(),
            timestamp_utc=datetime.now(UTC),
            payload=ModelClaudeCodeHookEventPayload(prompt="Fix the auth bug"),
        )

    @staticmethod
    def _classifier() -> MagicMock:
        mock_classifier = MagicMock()
        mock_output = MagicMock()
        mock_output.intent_category = "debugging"
        mock_output.confidence = 0.9
        mock_output.keywords = ["auth", "bug"]
        mock_output.secondary_intents = []
        mock_classifier.compute = AsyncMock(return_value=mock_output)
        return mock_classifier

    @pytest.mark.asyncio
    async def test_enum_cursor_tags_metadata(self) -> None:
        result = await route_hook_event(
            event=self._canonical_prompt_event(),
            intent_classifier=self._classifier(),
            agent_source=EnumAgentSource.CURSOR,
        )
        assert result.metadata["agent_source"] == EnumAgentSource.CURSOR.value

    @pytest.mark.asyncio
    async def test_claude_and_cursor_paths_are_distinct(self) -> None:
        producer_claude = MagicMock()
        producer_claude.publish = AsyncMock(return_value=None)
        producer_cursor = MagicMock()
        producer_cursor.publish = AsyncMock(return_value=None)

        await route_hook_event(
            event=self._canonical_prompt_event(),
            kafka_producer=producer_claude,
            publish_topic=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
            agent_source=EnumAgentSource.CLAUDE,
        )
        await route_hook_event(
            event=self._canonical_prompt_event(),
            kafka_producer=producer_cursor,
            publish_topic=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
            agent_source=EnumAgentSource.CURSOR,
        )

        claude_payload = producer_claude.publish.call_args.kwargs["value"]
        cursor_payload = producer_cursor.publish.call_args.kwargs["value"]
        assert claude_payload["agent_source"] == "claude"
        assert cursor_payload["agent_source"] == "cursor"
        assert claude_payload["agent_source"] != cursor_payload["agent_source"]
        assert claude_payload["provenance"]["source_node"] == "claude_hook_event_effect"
        assert cursor_payload["provenance"]["source_node"] == "cursor_hook_event_effect"

    @pytest.mark.asyncio
    async def test_bare_string_source_is_coerced(self) -> None:
        # Backward compatibility: legacy string callers still work at the seam.
        result = await route_hook_event(
            event=self._canonical_prompt_event(),
            intent_classifier=self._classifier(),
            agent_source="cursor",
        )
        assert result.metadata["agent_source"] == "cursor"

    @pytest.mark.asyncio
    async def test_unknown_source_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            await route_hook_event(
                event=self._canonical_prompt_event(),
                intent_classifier=self._classifier(),
                agent_source="codex",
            )
