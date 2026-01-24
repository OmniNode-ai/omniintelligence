# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for Claude Hook Event Effect models.

Tests the input and output models for the unified Claude Code hook handler.
Uses the canonical types from omnibase_core for input models.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from omniintelligence.nodes.claude_hook_event_effect.models import (
    EnumClaudeCodeHookEventType,
    EnumHookProcessingStatus,
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
    ModelClaudeHookResult,
    ModelIntentResult,
)


class TestEnumClaudeCodeHookEventType:
    """Tests for EnumClaudeCodeHookEventType enum (from omnibase_core)."""

    def test_all_event_types_defined(self) -> None:
        """Verify all expected Claude Code hook event types are defined."""
        expected_types = {
            "SessionStart",
            "UserPromptSubmit",
            "PreToolUse",
            "PermissionRequest",
            "PostToolUse",
            "PostToolUseFailure",
            "SubagentStart",
            "SubagentStop",
            "Notification",
            "Stop",
            "PreCompact",
            "SessionEnd",
        }
        actual_types = {e.value for e in EnumClaudeCodeHookEventType}
        assert expected_types == actual_types

    def test_enum_values_are_strings(self) -> None:
        """Verify enum values are strings matching Claude Code names."""
        assert EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT == "UserPromptSubmit"
        assert EnumClaudeCodeHookEventType.SESSION_START == "SessionStart"

    def test_helper_methods(self) -> None:
        """Test the helper classification methods."""
        # Agentic loop events
        assert EnumClaudeCodeHookEventType.is_agentic_loop_event(
            EnumClaudeCodeHookEventType.PRE_TOOL_USE
        )
        assert EnumClaudeCodeHookEventType.is_agentic_loop_event(
            EnumClaudeCodeHookEventType.POST_TOOL_USE
        )
        assert not EnumClaudeCodeHookEventType.is_agentic_loop_event(
            EnumClaudeCodeHookEventType.SESSION_START
        )

        # Session lifecycle events
        assert EnumClaudeCodeHookEventType.is_session_lifecycle_event(
            EnumClaudeCodeHookEventType.SESSION_START
        )
        assert EnumClaudeCodeHookEventType.is_session_lifecycle_event(
            EnumClaudeCodeHookEventType.SESSION_END
        )
        assert not EnumClaudeCodeHookEventType.is_session_lifecycle_event(
            EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT
        )


class TestModelClaudeCodeHookEvent:
    """Tests for ModelClaudeCodeHookEvent input model (from omnibase_core)."""

    def test_create_valid_event_with_payload(self) -> None:
        """Test creating a valid hook event with typed payload."""
        correlation_id = uuid4()
        # Create payload with extra fields (prompt is an extra field)
        payload = ModelClaudeCodeHookEventPayload(prompt="Fix the bug")
        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT,
            session_id="session-123",
            correlation_id=correlation_id,
            timestamp_utc=datetime.now(UTC),
            payload=payload,
        )
        assert event.event_type == EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT
        assert event.session_id == "session-123"
        assert event.correlation_id == correlation_id
        # Extra fields stored in model_extra
        assert event.payload.model_extra.get("prompt") == "Fix the bug"

    def test_create_event_without_correlation_id(self) -> None:
        """Test that correlation_id is optional."""
        payload = ModelClaudeCodeHookEventPayload()
        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.STOP,
            session_id="session-123",
            timestamp_utc=datetime.now(UTC),
            payload=payload,
        )
        assert event.correlation_id is None

    def test_event_type_as_string(self) -> None:
        """Test that event_type can be provided as string."""
        payload = ModelClaudeCodeHookEventPayload()
        event = ModelClaudeCodeHookEvent(
            event_type="SessionStart",  # type: ignore[arg-type]
            session_id="session-123",
            timestamp_utc=datetime.now(UTC),
            payload=payload,
        )
        assert event.event_type == EnumClaudeCodeHookEventType.SESSION_START

    def test_frozen_model(self) -> None:
        """Test that model is immutable (frozen)."""
        payload = ModelClaudeCodeHookEventPayload()
        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.STOP,
            session_id="session-123",
            timestamp_utc=datetime.now(UTC),
            payload=payload,
        )
        with pytest.raises(ValidationError):
            event.session_id = "new-session"  # type: ignore[misc]

    def test_payload_accepts_extra_fields(self) -> None:
        """Test that payload accepts extra fields via model_extra."""
        payload = ModelClaudeCodeHookEventPayload(
            prompt="Hello",
            custom_field="value",
            another_field=123,
        )
        assert payload.model_extra.get("prompt") == "Hello"
        assert payload.model_extra.get("custom_field") == "value"
        assert payload.model_extra.get("another_field") == 123


class TestModelIntentResult:
    """Tests for ModelIntentResult model."""

    def test_create_valid_intent_result(self) -> None:
        """Test creating a valid intent result."""
        result = ModelIntentResult(
            intent_category="debugging",
            confidence=0.92,
            secondary_intents=[{"intent_category": "code_review", "confidence": 0.45}],
            emitted_to_kafka=True,
        )
        assert result.intent_category == "debugging"
        assert result.confidence == 0.92
        assert len(result.secondary_intents) == 1
        assert result.emitted_to_kafka is True

    def test_confidence_bounds(self) -> None:
        """Test confidence must be between 0.0 and 1.0."""
        # Valid bounds
        result = ModelIntentResult(intent_category="test", confidence=0.0)
        assert result.confidence == 0.0

        result = ModelIntentResult(intent_category="test", confidence=1.0)
        assert result.confidence == 1.0

        # Invalid bounds
        with pytest.raises(ValidationError):
            ModelIntentResult(intent_category="test", confidence=-0.1)

        with pytest.raises(ValidationError):
            ModelIntentResult(intent_category="test", confidence=1.1)


class TestModelClaudeHookResult:
    """Tests for ModelClaudeHookResult output model."""

    def test_create_success_result(self) -> None:
        """Test creating a successful result."""
        correlation_id = uuid4()
        result = ModelClaudeHookResult(
            status=EnumHookProcessingStatus.SUCCESS,
            event_type="UserPromptSubmit",
            session_id="session-123",
            correlation_id=correlation_id,
            processing_time_ms=45.2,
            processed_at=datetime.now(UTC),
        )
        assert result.status == "success"
        assert result.intent_result is None
        assert result.error_message is None

    def test_create_result_without_correlation_id(self) -> None:
        """Test creating a result without correlation_id (now optional)."""
        result = ModelClaudeHookResult(
            status=EnumHookProcessingStatus.SUCCESS,
            event_type="Stop",
            session_id="session-123",
            processing_time_ms=1.0,
            processed_at=datetime.now(UTC),
        )
        assert result.correlation_id is None

    def test_create_result_with_intent(self) -> None:
        """Test creating a result with intent classification."""
        intent = ModelIntentResult(
            intent_category="debugging",
            confidence=0.92,
        )
        result = ModelClaudeHookResult(
            status=EnumHookProcessingStatus.SUCCESS,
            event_type="UserPromptSubmit",
            session_id="session-123",
            correlation_id=uuid4(),
            intent_result=intent,
            processing_time_ms=45.2,
            processed_at=datetime.now(UTC),
        )
        assert result.intent_result is not None
        assert result.intent_result.intent_category == "debugging"

    def test_create_failed_result(self) -> None:
        """Test creating a failed result with error message."""
        result = ModelClaudeHookResult(
            status=EnumHookProcessingStatus.FAILED,
            event_type="UserPromptSubmit",
            session_id="session-123",
            correlation_id=uuid4(),
            processing_time_ms=10.5,
            processed_at=datetime.now(UTC),
            error_message="Failed to classify intent",
            metadata={"exception_type": "ValueError"},
        )
        assert result.status == "failed"
        assert result.error_message == "Failed to classify intent"
        assert result.metadata["exception_type"] == "ValueError"

    def test_processing_time_non_negative(self) -> None:
        """Test that processing_time_ms must be non-negative."""
        with pytest.raises(ValidationError):
            ModelClaudeHookResult(
                status=EnumHookProcessingStatus.SUCCESS,
                event_type="Stop",
                session_id="session-123",
                processing_time_ms=-1.0,
                processed_at=datetime.now(UTC),
            )
