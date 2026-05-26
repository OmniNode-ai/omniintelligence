# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Tests for payload extraction helpers and status determination in handler_claude_event.

Covers:
    - _extract_file_path_from_payload
    - _extract_tool_name_from_payload
    - _determine_processing_status
    - _route_to_dlq
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
    _determine_processing_status,
    _extract_file_path_from_payload,
    _extract_tool_name_from_payload,
    _route_to_dlq,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models import (
    EnumHookProcessingStatus,
    ModelClaudeCodeHookEventPayload,
)

# =============================================================================
# Helpers
# =============================================================================


def _payload(**extra: object) -> ModelClaudeCodeHookEventPayload:
    """Build a hook payload with arbitrary extra fields."""
    return ModelClaudeCodeHookEventPayload(**extra)


class MockKafkaPublisher:
    """Minimal Kafka publisher test double."""

    def __init__(self, *, raise_on_publish: Exception | None = None) -> None:
        self.published: list[dict[str, object]] = []
        self._raise = raise_on_publish

    async def publish(self, *, topic: str, key: str, value: dict[str, object]) -> None:
        if self._raise is not None:
            raise self._raise
        self.published.append({"topic": topic, "key": key, "value": value})


# =============================================================================
# _extract_file_path_from_payload
# =============================================================================


@pytest.mark.unit
class TestExtractFilePath:
    """Unit tests for _extract_file_path_from_payload."""

    def test_extracts_file_path_key(self) -> None:
        payload = _payload(file_path="/tmp/foo.py")
        assert _extract_file_path_from_payload(payload) == "/tmp/foo.py"

    def test_extracts_path_key(self) -> None:
        payload = _payload(path="/etc/config.yaml")
        assert _extract_file_path_from_payload(payload) == "/etc/config.yaml"

    def test_file_path_takes_priority_over_path(self) -> None:
        payload = _payload(file_path="/a.py", path="/b.py")
        assert _extract_file_path_from_payload(payload) == "/a.py"

    def test_extracts_file_path_from_nested_tool_input(self) -> None:
        payload = _payload(tool_input={"file_path": "/nested/file.py"})
        assert _extract_file_path_from_payload(payload) == "/nested/file.py"

    def test_extracts_path_from_nested_tool_input(self) -> None:
        payload = _payload(tool_input={"path": "/nested/path.py"})
        assert _extract_file_path_from_payload(payload) == "/nested/path.py"

    def test_returns_none_when_no_path_present(self) -> None:
        payload = _payload(tool_name="Bash")
        assert _extract_file_path_from_payload(payload) is None

    def test_returns_none_for_empty_payload(self) -> None:
        payload = _payload()
        assert _extract_file_path_from_payload(payload) is None

    def test_ignores_non_string_file_path(self) -> None:
        payload = _payload(file_path=123)
        assert _extract_file_path_from_payload(payload) is None

    def test_ignores_empty_string_file_path(self) -> None:
        payload = _payload(file_path="")
        assert _extract_file_path_from_payload(payload) is None

    def test_truncates_very_long_path(self) -> None:
        long_path = "x" * 5000
        payload = _payload(file_path=long_path)
        result = _extract_file_path_from_payload(payload)
        assert result is not None
        assert len(result) == 4096

    def test_prefers_top_level_over_nested_tool_input(self) -> None:
        payload = _payload(file_path="/top.py", tool_input={"file_path": "/nested.py"})
        assert _extract_file_path_from_payload(payload) == "/top.py"

    def test_returns_none_when_tool_input_not_a_dict(self) -> None:
        payload = _payload(tool_input="not-a-dict")
        assert _extract_file_path_from_payload(payload) is None


# =============================================================================
# _extract_tool_name_from_payload
# =============================================================================


@pytest.mark.unit
class TestExtractToolName:
    """Unit tests for _extract_tool_name_from_payload."""

    def test_extracts_tool_name_key(self) -> None:
        payload = _payload(tool_name="Bash")
        assert _extract_tool_name_from_payload(payload) == "Bash"

    def test_extracts_tool_name_raw_key(self) -> None:
        payload = _payload(tool_name_raw="Read")
        assert _extract_tool_name_from_payload(payload) == "Read"

    def test_extracts_tool_key(self) -> None:
        payload = _payload(tool="Write")
        assert _extract_tool_name_from_payload(payload) == "Write"

    def test_tool_name_takes_priority(self) -> None:
        payload = _payload(tool_name="Bash", tool_name_raw="Read", tool="Write")
        assert _extract_tool_name_from_payload(payload) == "Bash"

    def test_returns_none_when_no_tool_name(self) -> None:
        payload = _payload(file_path="/foo.py")
        assert _extract_tool_name_from_payload(payload) is None

    def test_returns_none_for_empty_payload(self) -> None:
        payload = _payload()
        assert _extract_tool_name_from_payload(payload) is None

    def test_ignores_non_string_tool_name(self) -> None:
        payload = _payload(tool_name=42)
        assert _extract_tool_name_from_payload(payload) is None

    def test_ignores_empty_string_tool_name(self) -> None:
        payload = _payload(tool_name="")
        assert _extract_tool_name_from_payload(payload) is None

    def test_truncates_very_long_tool_name(self) -> None:
        long_name = "T" * 500
        payload = _payload(tool_name=long_name)
        result = _extract_tool_name_from_payload(payload)
        assert result is not None
        assert len(result) == 255


# =============================================================================
# _determine_processing_status
# =============================================================================


@pytest.mark.unit
class TestDetermineProcessingStatus:
    """Unit tests for _determine_processing_status."""

    def test_emitted_to_kafka_returns_success(self) -> None:
        producer = MockKafkaPublisher()
        result = _determine_processing_status(
            emitted_to_kafka=True,
            kafka_producer=producer,
            publish_topic="some.topic",
        )
        assert result == EnumHookProcessingStatus.SUCCESS

    def test_no_producer_returns_success(self) -> None:
        result = _determine_processing_status(
            emitted_to_kafka=False,
            kafka_producer=None,
            publish_topic=None,
        )
        assert result == EnumHookProcessingStatus.SUCCESS

    def test_no_topic_returns_success(self) -> None:
        producer = MockKafkaPublisher()
        result = _determine_processing_status(
            emitted_to_kafka=False,
            kafka_producer=producer,
            publish_topic=None,
        )
        assert result == EnumHookProcessingStatus.SUCCESS

    def test_failed_emission_with_full_config_returns_partial(self) -> None:
        producer = MockKafkaPublisher()
        result = _determine_processing_status(
            emitted_to_kafka=False,
            kafka_producer=producer,
            publish_topic="some.topic",
        )
        assert result == EnumHookProcessingStatus.PARTIAL

    def test_emitted_true_always_success_regardless_of_producer(self) -> None:
        result = _determine_processing_status(
            emitted_to_kafka=True,
            kafka_producer=None,
            publish_topic=None,
        )
        assert result == EnumHookProcessingStatus.SUCCESS


# =============================================================================
# _route_to_dlq
# =============================================================================


@pytest.mark.unit
class TestRouteToDlq:
    """Unit tests for _route_to_dlq."""

    @pytest.mark.asyncio
    async def test_publishes_to_dlq_topic(self) -> None:
        producer = MockKafkaPublisher()
        metadata: dict[str, object] = {}
        await _route_to_dlq(
            producer=producer,
            topic="onex.cmd.omniintelligence.pattern-learning.v1",
            envelope={"session_id": "abc", "correlation_id": "xyz"},
            error_message="connection timeout",
            session_id="abc",
            metadata=metadata,
        )
        assert len(producer.published) == 1
        dlq_call = producer.published[0]
        assert dlq_call["topic"].endswith(".dlq")
        assert "connection timeout" in str(dlq_call["value"]["error_message"])

    @pytest.mark.asyncio
    async def test_dlq_topic_is_original_plus_dlq_suffix(self) -> None:
        producer = MockKafkaPublisher()
        metadata: dict[str, object] = {}
        original_topic = "onex.cmd.omniintelligence.pattern-learning.v1"
        await _route_to_dlq(
            producer=producer,
            topic=original_topic,
            envelope={},
            error_message="err",
            session_id="sess",
            metadata=metadata,
        )
        assert producer.published[0]["topic"] == f"{original_topic}.dlq"

    @pytest.mark.asyncio
    async def test_dlq_payload_contains_original_topic(self) -> None:
        producer = MockKafkaPublisher()
        metadata: dict[str, object] = {}
        original_topic = "onex.cmd.test.v1"
        await _route_to_dlq(
            producer=producer,
            topic=original_topic,
            envelope={"key": "val"},
            error_message="err",
            session_id="sess",
            metadata=metadata,
        )
        value = producer.published[0]["value"]
        assert value["original_topic"] == original_topic

    @pytest.mark.asyncio
    async def test_dlq_payload_has_retry_count_zero(self) -> None:
        producer = MockKafkaPublisher()
        metadata: dict[str, object] = {}
        await _route_to_dlq(
            producer=producer,
            topic="t",
            envelope={},
            error_message="e",
            session_id="s",
            metadata=metadata,
        )
        assert producer.published[0]["value"]["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_sets_metadata_dlq_topic_on_success(self) -> None:
        producer = MockKafkaPublisher()
        metadata: dict[str, object] = {}
        await _route_to_dlq(
            producer=producer,
            topic="orig.topic",
            envelope={},
            error_message="e",
            session_id="s",
            metadata=metadata,
        )
        assert metadata.get("pattern_learning_dlq") == "orig.topic.dlq"

    @pytest.mark.asyncio
    async def test_swallows_dlq_publish_failure(self) -> None:
        producer = MockKafkaPublisher(raise_on_publish=RuntimeError("Kafka down"))
        metadata: dict[str, object] = {}
        # Should NOT raise
        await _route_to_dlq(
            producer=producer,
            topic="t",
            envelope={},
            error_message="e",
            session_id="s",
            metadata=metadata,
        )
        assert metadata.get("pattern_learning_dlq") == "failed"

    @pytest.mark.asyncio
    async def test_sanitizes_envelope_string_values(self) -> None:
        producer = MockKafkaPublisher()
        metadata: dict[str, object] = {}
        await _route_to_dlq(
            producer=producer,
            topic="t",
            envelope={"session_id": "abc123"},
            error_message="safe error",
            session_id="abc123",
            metadata=metadata,
        )
        value = producer.published[0]["value"]
        original_envelope = value["original_envelope"]
        assert isinstance(original_envelope, dict)
        assert "session_id" in original_envelope
