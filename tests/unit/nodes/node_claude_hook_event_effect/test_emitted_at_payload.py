# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for emitted_at field in intent-classified.v1 event payload.

Validates that:
- emitted_at is present in the event payload emitted by _emit_intent_to_kafka
- emitted_at == timestamp (computed once, reused — no drift)
- emitted_at is a valid ISO 8601 UTC string with +00:00 offset

Reference: OMN-2921 (OMN-2840 timestamp drift fix)
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
    _emit_intent_to_kafka,
)

pytestmark = pytest.mark.unit


class TestEmittedAtPayloadField:
    """Tests for the emitted_at field added to intent-classified.v1 payload (OMN-2921)."""

    @pytest.fixture
    def mock_producer(self) -> AsyncMock:
        """Mock Kafka producer that captures published payloads."""
        producer = AsyncMock()
        producer.publish = AsyncMock()
        return producer

    @pytest.mark.asyncio
    async def test_emitted_at_present_in_payload(
        self, mock_producer: AsyncMock
    ) -> None:
        """emitted_at must be present in the event payload."""
        await _emit_intent_to_kafka(
            session_id="session-test-001",
            correlation_id=uuid4(),
            intent_category="code_review",
            confidence=0.95,
            keywords=["code", "review"],
            secondary_intents=[],
            success=True,
            processing_time_ms=12.5,
            classifier_version_str="1.0.0",
            producer=mock_producer,
            topic="onex.evt.omniintelligence.intent-classified.v1",
        )

        mock_producer.publish.assert_called_once()
        call_kwargs = mock_producer.publish.call_args.kwargs
        payload = call_kwargs["value"]

        assert "emitted_at" in payload, "emitted_at must be present in event payload"

    @pytest.mark.asyncio
    async def test_emitted_at_equals_timestamp(self, mock_producer: AsyncMock) -> None:
        """emitted_at must equal timestamp — both computed from the same _now value."""
        await _emit_intent_to_kafka(
            session_id="session-test-002",
            correlation_id=uuid4(),
            intent_category="debugging",
            confidence=0.88,
            keywords=["debug", "error"],
            secondary_intents=[],
            success=True,
            processing_time_ms=8.3,
            classifier_version_str="1.0.0",
            producer=mock_producer,
            topic="onex.evt.omniintelligence.intent-classified.v1",
        )

        call_kwargs = mock_producer.publish.call_args.kwargs
        payload = call_kwargs["value"]

        assert payload["emitted_at"] == payload["timestamp"], (
            "emitted_at and timestamp must be identical strings "
            "(both computed from the same _now value)"
        )

    @pytest.mark.asyncio
    async def test_emitted_at_is_valid_iso8601_utc(
        self, mock_producer: AsyncMock
    ) -> None:
        """emitted_at must be a valid ISO 8601 string with +00:00 UTC offset."""
        await _emit_intent_to_kafka(
            session_id="session-test-003",
            correlation_id=uuid4(),
            intent_category="feature_development",
            confidence=0.91,
            keywords=["feature", "implementation"],
            secondary_intents=[],
            success=True,
            processing_time_ms=15.7,
            classifier_version_str="1.0.0",
            producer=mock_producer,
            topic="onex.evt.omniintelligence.intent-classified.v1",
        )

        call_kwargs = mock_producer.publish.call_args.kwargs
        payload = call_kwargs["value"]

        emitted_at = payload["emitted_at"]
        assert isinstance(emitted_at, str), "emitted_at must be a string"
        assert emitted_at.endswith("+00:00"), (
            f"emitted_at must end with +00:00 UTC offset, got: {emitted_at!r}"
        )

        # Must parse cleanly without raising
        parsed = datetime.fromisoformat(emitted_at)
        assert parsed.tzinfo is not None, "emitted_at must be timezone-aware"
