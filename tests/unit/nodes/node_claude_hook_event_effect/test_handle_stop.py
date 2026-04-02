# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Tests for handle_stop handler in Claude Hook Event Effect.

Validates that Stop events trigger pattern learning command emission
to onex.cmd.omniintelligence.pattern-learning.v1.

Related:
    - OMN-2210: Wire intelligence nodes into registration + pattern extraction
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
    ProtocolKafkaPublisher,
    _extract_check_results_from_payload,
    handle_stop,
    route_hook_event,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models import (
    EnumClaudeCodeHookEventType,
    EnumHookProcessingStatus,
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
)


def _make_stop_event() -> ModelClaudeCodeHookEvent:
    """Create a Stop hook event for testing."""
    return ModelClaudeCodeHookEvent(
        event_type=EnumClaudeCodeHookEventType.STOP,
        session_id="test-session-123",
        correlation_id=uuid4(),
        timestamp_utc=datetime.now(UTC).isoformat(),
        payload=ModelClaudeCodeHookEventPayload(),
    )


def _make_mock_producer(**kwargs: object) -> AsyncMock:
    """Create a mock Kafka producer with protocol conformance verification."""
    mock_producer = AsyncMock()
    mock_producer.publish = AsyncMock(**kwargs)
    assert isinstance(mock_producer, ProtocolKafkaPublisher)
    return mock_producer


@pytest.mark.unit
class TestHandleStop:
    """Test handle_stop handler function."""

    @pytest.mark.asyncio
    async def test_returns_success_without_kafka(self) -> None:
        """Should return success even without Kafka producer."""
        event = _make_stop_event()
        result = await handle_stop(event=event, kafka_producer=None)

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.event_type == "Stop"
        assert result.session_id == "test-session-123"
        assert result.metadata is not None
        assert result.metadata["handler"] == "stop_trigger_pattern_learning"
        assert result.metadata["pattern_learning_emission"] == "no_producer"

    @pytest.mark.asyncio
    async def test_emits_pattern_learning_command(self) -> None:
        """Should emit pattern learning command to Kafka on Stop."""
        event = _make_stop_event()
        mock_producer = _make_mock_producer()

        result = await handle_stop(event=event, kafka_producer=mock_producer)

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.metadata is not None
        assert result.metadata["pattern_learning_emission"] == "success"
        assert (
            result.metadata["pattern_learning_topic"]
            == "onex.cmd.omniintelligence.pattern-learning.v1"
        )

        # Verify Kafka publish was called with correct topic
        mock_producer.publish.assert_awaited_once()
        call_kwargs = mock_producer.publish.call_args
        assert (
            call_kwargs.kwargs["topic"]
            == "onex.cmd.omniintelligence.pattern-learning.v1"
        )

    @pytest.mark.asyncio
    async def test_emitted_payload_structure(self) -> None:
        """Verify the emitted command payload has correct structure."""
        event = _make_stop_event()
        mock_producer = _make_mock_producer()

        await handle_stop(event=event, kafka_producer=mock_producer)

        # Get the value argument from the publish call (keyword args)
        call_args = mock_producer.publish.call_args
        payload = call_args.kwargs["value"]

        assert payload["event_type"] == "PatternLearningRequested"
        assert payload["session_id"] == "test-session-123"
        assert payload["trigger"] == "session_stop"
        assert payload["correlation_id"] == str(event.correlation_id)
        assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_handles_kafka_publish_failure(self) -> None:
        """Should return PARTIAL when Kafka producer was available but publish failed."""
        event = _make_stop_event()
        mock_producer = _make_mock_producer(
            side_effect=RuntimeError("Kafka unavailable"),
        )

        result = await handle_stop(event=event, kafka_producer=mock_producer)

        # Should return PARTIAL: Kafka was configured but emission failed
        assert result.status == EnumHookProcessingStatus.PARTIAL
        assert result.metadata is not None
        assert result.metadata["pattern_learning_emission"] == "failed"
        assert "Kafka unavailable" in result.metadata["pattern_learning_error"]

        # Verify DLQ routing was attempted: producer.publish should be called
        # twice -- once for the original topic (which fails) and once for the
        # DLQ topic (which also fails because the mock raises unconditionally).
        assert mock_producer.publish.await_count == 2
        dlq_call = mock_producer.publish.call_args_list[1]
        assert dlq_call.kwargs["topic"].endswith(".dlq")

        # DLQ publish also failed (same side_effect), so metadata reflects that
        assert result.metadata["pattern_learning_dlq"] == "failed"

    @pytest.mark.asyncio
    async def test_handle_stop_none_correlation_id(self) -> None:
        """Should generate a fallback UUID when event.correlation_id is None."""
        event = ModelClaudeCodeHookEvent(
            event_type=EnumClaudeCodeHookEventType.STOP,
            session_id="test-session-none-corr",
            correlation_id=None,
            timestamp_utc=datetime.now(UTC).isoformat(),
            payload=ModelClaudeCodeHookEventPayload(),
        )
        mock_producer = _make_mock_producer()

        result = await handle_stop(event=event, kafka_producer=mock_producer)

        # Handler should not fail due to None correlation_id
        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.metadata is not None
        assert result.metadata["pattern_learning_emission"] == "success"

        # The Kafka payload should contain a valid UUID string (fallback),
        # not None or "None"
        call_args = mock_producer.publish.call_args
        payload = call_args.kwargs["value"]
        fallback_corr = payload["correlation_id"]
        assert fallback_corr is not None
        assert fallback_corr != "None"
        # Verify it parses as a valid UUID
        UUID(fallback_corr)


@pytest.mark.unit
class TestExtractCheckResultsFromPayload:
    """Test _extract_check_results_from_payload (OMN-7378)."""

    def test_empty_payload_yields_empty_results(self) -> None:
        """Empty payload should produce empty check results."""
        payload = ModelClaudeCodeHookEventPayload()
        result = _extract_check_results_from_payload(
            payload=payload,
            run_id="run-1",
            session_id="sess-1",
            collected_at_utc="2026-04-02T00:00:00Z",
        )
        assert result.run_id == "run-1"
        assert result.session_id == "sess-1"
        assert result.gate_results == ()
        assert result.test_results == ()
        assert result.static_analysis_results == ()
        assert result.cost_usd is None
        assert result.latency_seconds is None

    def test_completion_status_success_creates_gate(self) -> None:
        """Successful completion_status should create a passing session_completion gate."""
        payload = ModelClaudeCodeHookEventPayload(completion_status="success")
        result = _extract_check_results_from_payload(
            payload=payload,
            run_id="run-1",
            session_id="sess-1",
            collected_at_utc="2026-04-02T00:00:00Z",
        )
        assert len(result.gate_results) == 1
        gate = result.gate_results[0]
        assert gate.gate_id == "session_completion"
        assert gate.passed is True
        assert gate.pass_rate == 1.0

    def test_completion_status_error_creates_failing_gate(self) -> None:
        """Error completion_status should create a failing session_completion gate."""
        payload = ModelClaudeCodeHookEventPayload(completion_status="error")
        result = _extract_check_results_from_payload(
            payload=payload,
            run_id="run-1",
            session_id="sess-1",
            collected_at_utc="2026-04-02T00:00:00Z",
        )
        assert len(result.gate_results) == 1
        gate = result.gate_results[0]
        assert gate.gate_id == "session_completion"
        assert gate.passed is False
        assert gate.pass_rate == 0.0

    def test_explicit_gate_results_parsed(self) -> None:
        """Explicit gate_results in payload should be parsed."""
        payload = ModelClaudeCodeHookEventPayload(
            completion_status="success",
            gate_results=[
                {
                    "gate_id": "mypy_strict",
                    "passed": True,
                    "pass_rate": 1.0,
                    "check_count": 10,
                    "pass_count": 10,
                }
            ],
        )
        result = _extract_check_results_from_payload(
            payload=payload,
            run_id="run-1",
            session_id="sess-1",
            collected_at_utc="2026-04-02T00:00:00Z",
        )
        # session_completion gate + explicit mypy_strict gate
        assert len(result.gate_results) == 2
        gate_ids = [g.gate_id for g in result.gate_results]
        assert "session_completion" in gate_ids
        assert "mypy_strict" in gate_ids

    def test_test_results_parsed(self) -> None:
        """Explicit test_results in payload should be parsed."""
        payload = ModelClaudeCodeHookEventPayload(
            test_results=[
                {
                    "test_suite": "unit",
                    "total_tests": 50,
                    "passed_tests": 48,
                    "failed_tests": 2,
                    "error_tests": 0,
                    "pass_rate": 0.96,
                    "duration_seconds": 12.5,
                }
            ],
        )
        result = _extract_check_results_from_payload(
            payload=payload,
            run_id="run-1",
            session_id="sess-1",
            collected_at_utc="2026-04-02T00:00:00Z",
        )
        assert len(result.test_results) == 1
        assert result.test_results[0].test_suite == "unit"
        assert result.test_results[0].total_tests == 50
        assert result.test_results[0].pass_rate == 0.96

    def test_cost_and_latency_extracted(self) -> None:
        """Cost and latency telemetry should be extracted from payload."""
        payload = ModelClaudeCodeHookEventPayload(
            cost_usd=0.42,
            latency_seconds=15.3,
        )
        result = _extract_check_results_from_payload(
            payload=payload,
            run_id="run-1",
            session_id="sess-1",
            collected_at_utc="2026-04-02T00:00:00Z",
        )
        assert result.cost_usd == 0.42
        assert result.latency_seconds == 15.3

    def test_malformed_gate_results_skipped(self) -> None:
        """Malformed gate result entries should be silently skipped."""
        payload = ModelClaudeCodeHookEventPayload(
            gate_results=[
                {"gate_id": "valid", "passed": True, "pass_rate": 1.0},
                {"no_gate_id": True},  # missing gate_id
                "not_a_dict",  # wrong type
            ],
        )
        result = _extract_check_results_from_payload(
            payload=payload,
            run_id="run-1",
            session_id="sess-1",
            collected_at_utc="2026-04-02T00:00:00Z",
        )
        # Only the valid gate result should be parsed
        assert len(result.gate_results) == 1
        assert result.gate_results[0].gate_id == "valid"

    def test_negative_cost_ignored(self) -> None:
        """Negative cost values should be ignored."""
        payload = ModelClaudeCodeHookEventPayload(cost_usd=-1.0)
        result = _extract_check_results_from_payload(
            payload=payload,
            run_id="run-1",
            session_id="sess-1",
            collected_at_utc="2026-04-02T00:00:00Z",
        )
        assert result.cost_usd is None


@pytest.mark.unit
class TestRouteHookEventStop:
    """Test that route_hook_event correctly routes Stop events."""

    @pytest.mark.asyncio
    async def test_stop_event_routed_to_handle_stop(self) -> None:
        """Stop events should be routed to handle_stop, not handle_no_op."""
        event = _make_stop_event()
        mock_producer = _make_mock_producer()

        result = await route_hook_event(
            event=event,
            kafka_producer=mock_producer,
        )

        assert result.status == EnumHookProcessingStatus.SUCCESS
        # Verify it went through handle_stop (has pattern_learning metadata)
        assert result.metadata is not None
        assert result.metadata["handler"] == "stop_trigger_pattern_learning"
