# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for Claude Hook Event Effect handlers.

Tests the handler functions for processing Claude Code hook events.
Uses the canonical types from omnibase_core.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from omniintelligence.nodes.claude_hook_event_effect.handlers import (
    handle_no_op,
    handle_user_prompt_submit,
    route_hook_event,
)
from omniintelligence.nodes.claude_hook_event_effect.models import (
    EnumClaudeCodeHookEventType,
    EnumHookProcessingStatus,
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
)
from tests.fixtures.topic_constants import TOPIC_SUFFIX_INTENT_CLASSIFIED_V1

pytestmark = pytest.mark.unit


@pytest.fixture
def sample_user_prompt_event() -> ModelClaudeCodeHookEvent:
    """Create a sample UserPromptSubmit event."""
    payload = ModelClaudeCodeHookEventPayload(
        prompt="Fix the authentication bug in login.py"
    )
    return ModelClaudeCodeHookEvent(
        event_type=EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT,
        session_id="session-123",
        correlation_id=uuid4(),
        timestamp_utc=datetime.now(UTC),
        payload=payload,
    )


@pytest.fixture
def sample_stop_event() -> ModelClaudeCodeHookEvent:
    """Create a sample Stop event."""
    payload = ModelClaudeCodeHookEventPayload()
    return ModelClaudeCodeHookEvent(
        event_type=EnumClaudeCodeHookEventType.STOP,
        session_id="session-123",
        correlation_id=uuid4(),
        timestamp_utc=datetime.now(UTC),
        payload=payload,
    )


@pytest.fixture
def sample_session_start_event() -> ModelClaudeCodeHookEvent:
    """Create a sample SessionStart event."""
    payload = ModelClaudeCodeHookEventPayload(
        working_directory="/workspace/project"
    )
    return ModelClaudeCodeHookEvent(
        event_type=EnumClaudeCodeHookEventType.SESSION_START,
        session_id="session-123",
        correlation_id=uuid4(),
        timestamp_utc=datetime.now(UTC),
        payload=payload,
    )


class TestHandleNoOp:
    """Tests for handle_no_op function."""

    def test_returns_success(self, sample_stop_event: ModelClaudeCodeHookEvent) -> None:
        """Test that no-op handler returns success."""
        result = handle_no_op(sample_stop_event)
        assert result.status == EnumHookProcessingStatus.SUCCESS

    def test_no_intent_result(self, sample_stop_event: ModelClaudeCodeHookEvent) -> None:
        """Test that no-op handler has no intent result."""
        result = handle_no_op(sample_stop_event)
        assert result.intent_result is None

    def test_preserves_event_metadata(
        self, sample_stop_event: ModelClaudeCodeHookEvent
    ) -> None:
        """Test that handler preserves event metadata."""
        result = handle_no_op(sample_stop_event)
        assert result.event_type == "Stop"
        assert result.session_id == sample_stop_event.session_id
        assert result.correlation_id == sample_stop_event.correlation_id

    def test_includes_no_op_metadata(
        self, sample_stop_event: ModelClaudeCodeHookEvent
    ) -> None:
        """Test that handler includes no-op metadata."""
        result = handle_no_op(sample_stop_event)
        assert result.metadata["handler"] == "no_op"
        assert "not yet implemented" in result.metadata["reason"]


class TestHandleUserPromptSubmit:
    """Tests for handle_user_prompt_submit function."""

    @pytest.mark.asyncio
    async def test_success_without_adapters(
        self, sample_user_prompt_event: ModelClaudeCodeHookEvent
    ) -> None:
        """Test handling UserPromptSubmit without adapters configured."""
        result = await handle_user_prompt_submit(event=sample_user_prompt_event)
        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.intent_result is not None
        assert result.intent_result.intent_category == "unknown"
        assert result.intent_result.confidence == 0.0
        assert result.intent_result.emitted_to_kafka is False

    @pytest.mark.asyncio
    async def test_fails_without_prompt(self) -> None:
        """Test handling event without prompt in payload."""
        payload = ModelClaudeCodeHookEventPayload()  # No prompt
        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT,
            session_id="session-123",
            correlation_id=uuid4(),
            timestamp_utc=datetime.now(UTC),
            payload=payload,
        )
        result = await handle_user_prompt_submit(event=event)
        assert result.status == EnumHookProcessingStatus.FAILED
        assert "No prompt found" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_with_mock_classifier(
        self, sample_user_prompt_event: ModelClaudeCodeHookEvent
    ) -> None:
        """Test handling with mock intent classifier."""
        # Create mock classifier that returns a classification
        mock_classifier = MagicMock()

        # Create a mock output with the expected attributes
        mock_output = MagicMock()
        mock_output.intent_category = "debugging"
        mock_output.confidence = 0.92
        mock_output.secondary_intents = []

        mock_classifier.compute = AsyncMock(return_value=mock_output)

        result = await handle_user_prompt_submit(
            event=sample_user_prompt_event,
            intent_classifier=mock_classifier,
        )

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.intent_result is not None
        assert result.intent_result.intent_category == "debugging"
        assert result.intent_result.confidence == 0.92

    @pytest.mark.asyncio
    async def test_with_mock_kafka_producer(
        self, sample_user_prompt_event: ModelClaudeCodeHookEvent
    ) -> None:
        """Test handling with mock Kafka producer."""
        mock_producer = MagicMock()
        mock_producer.publish = AsyncMock(return_value=None)

        result = await handle_user_prompt_submit(
            event=sample_user_prompt_event,
            kafka_producer=mock_producer,
            publish_topic_suffix=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
        )

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.intent_result is not None
        assert result.intent_result.emitted_to_kafka is True
        mock_producer.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_partial_failure_on_kafka_error(
        self, sample_user_prompt_event: ModelClaudeCodeHookEvent
    ) -> None:
        """Test partial failure when Kafka emission fails."""
        mock_producer = MagicMock()
        mock_producer.publish = AsyncMock(side_effect=Exception("Kafka error"))

        result = await handle_user_prompt_submit(
            event=sample_user_prompt_event,
            kafka_producer=mock_producer,
            publish_topic_suffix=TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
        )

        assert result.status == EnumHookProcessingStatus.PARTIAL
        assert result.intent_result is not None
        assert result.intent_result.emitted_to_kafka is False
        assert "kafka_emission_error" in result.metadata


class TestRouteHookEvent:
    """Tests for route_hook_event function."""

    @pytest.mark.asyncio
    async def test_routes_user_prompt_submit(
        self, sample_user_prompt_event: ModelClaudeCodeHookEvent
    ) -> None:
        """Test that UserPromptSubmit events are routed correctly."""
        result = await route_hook_event(event=sample_user_prompt_event)
        assert result.event_type == "UserPromptSubmit"
        # Should have intent classification (even if unknown)
        assert result.intent_result is not None

    @pytest.mark.asyncio
    async def test_routes_stop_to_no_op(
        self, sample_stop_event: ModelClaudeCodeHookEvent
    ) -> None:
        """Test that Stop events go to no-op handler."""
        result = await route_hook_event(event=sample_stop_event)
        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.intent_result is None
        assert result.metadata["handler"] == "no_op"

    @pytest.mark.asyncio
    async def test_routes_session_start_to_no_op(
        self, sample_session_start_event: ModelClaudeCodeHookEvent
    ) -> None:
        """Test that SessionStart events go to no-op handler."""
        result = await route_hook_event(event=sample_session_start_event)
        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.intent_result is None

    @pytest.mark.asyncio
    async def test_measures_processing_time(
        self, sample_stop_event: ModelClaudeCodeHookEvent
    ) -> None:
        """Test that processing time is measured."""
        result = await route_hook_event(event=sample_stop_event)
        assert result.processing_time_ms >= 0.0

    @pytest.mark.asyncio
    async def test_handles_exception(self) -> None:
        """Test that exceptions are handled gracefully."""
        payload = ModelClaudeCodeHookEventPayload(prompt="test")
        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT,
            session_id="session-123",
            correlation_id=uuid4(),
            timestamp_utc=datetime.now(UTC),
            payload=payload,
        )

        # Mock a classifier that raises
        mock_classifier = MagicMock()
        mock_classifier.compute = AsyncMock(side_effect=RuntimeError("Test error"))

        result = await route_hook_event(
            event=event,
            intent_classifier=mock_classifier,
        )

        # Should still return a result (not raise)
        assert result.status in [
            EnumHookProcessingStatus.SUCCESS,
            EnumHookProcessingStatus.PARTIAL,
            EnumHookProcessingStatus.FAILED,
        ]

    @pytest.mark.asyncio
    async def test_all_event_types_handled(self) -> None:
        """Test that all event types are handled without error."""
        for event_type in EnumClaudeCodeHookEventType:
            # Create payload with prompt for UserPromptSubmit, empty otherwise
            if event_type == EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT:
                payload = ModelClaudeCodeHookEventPayload(prompt="test")
            else:
                payload = ModelClaudeCodeHookEventPayload()

            event = ModelClaudeCodeHookEvent(
                event_type=event_type,
                session_id="session-123",
                correlation_id=uuid4(),
                timestamp_utc=datetime.now(UTC),
                payload=payload,
            )
            result = await route_hook_event(event=event)
            assert result.status in [
                EnumHookProcessingStatus.SUCCESS,
                EnumHookProcessingStatus.PARTIAL,
                EnumHookProcessingStatus.FAILED,
                EnumHookProcessingStatus.SKIPPED,
            ]
