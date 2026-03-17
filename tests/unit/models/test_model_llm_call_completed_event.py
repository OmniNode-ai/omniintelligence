# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for ModelLLMCallCompletedEvent.

Tests:
    1. Construction with valid data succeeds and fields are accessible
    2. Model is frozen (immutable) and rejects extra fields
    3. JSON serialization produces exactly the 11 expected keys

Reference: OMN-5184 Task 1
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from omniintelligence.models.events.model_llm_call_completed_event import (
    ModelLLMCallCompletedEvent,
)


@pytest.fixture()
def valid_event_kwargs() -> dict[str, object]:
    """Minimal valid kwargs for constructing a ModelLLMCallCompletedEvent."""
    return {
        "model_id": "qwen3-coder-30b",
        "endpoint_url": "http://192.168.86.201:8000",
        "input_tokens": 1200,
        "output_tokens": 350,
        "total_tokens": 1550,
        "cost_usd": 0.0,
        "latency_ms": 823,
        "request_type": "completion",
        "correlation_id": "abc-123-def",
        "session_id": "sess-456",
        "emitted_at": datetime(2026, 3, 17, 12, 0, 0, tzinfo=UTC),
    }


@pytest.mark.unit
class TestModelLLMCallCompletedEventConstruction:
    """Test construction with valid data."""

    def test_construct_valid(self, valid_event_kwargs: dict[str, object]) -> None:
        event = ModelLLMCallCompletedEvent(**valid_event_kwargs)  # type: ignore[arg-type]
        assert event.model_id == "qwen3-coder-30b"
        assert event.endpoint_url == "http://192.168.86.201:8000"
        assert event.input_tokens == 1200
        assert event.output_tokens == 350
        assert event.total_tokens == 1550
        assert event.cost_usd == 0.0
        assert event.latency_ms == 823
        assert event.request_type == "completion"
        assert event.correlation_id == "abc-123-def"
        assert event.session_id == "sess-456"

    def test_emitted_at_must_be_tz_aware(
        self, valid_event_kwargs: dict[str, object]
    ) -> None:
        kwargs = {**valid_event_kwargs, "emitted_at": datetime(2026, 3, 17, 12, 0, 0)}
        with pytest.raises(ValueError, match="timezone-aware"):
            ModelLLMCallCompletedEvent(**kwargs)  # type: ignore[arg-type]

    def test_negative_tokens_rejected(
        self, valid_event_kwargs: dict[str, object]
    ) -> None:
        kwargs = {**valid_event_kwargs, "input_tokens": -1}
        with pytest.raises(ValueError):
            ModelLLMCallCompletedEvent(**kwargs)  # type: ignore[arg-type]


@pytest.mark.unit
class TestModelLLMCallCompletedEventFrozenAndStrict:
    """Test frozen immutability and extra field rejection."""

    def test_frozen_immutable(self, valid_event_kwargs: dict[str, object]) -> None:
        event = ModelLLMCallCompletedEvent(**valid_event_kwargs)  # type: ignore[arg-type]
        with pytest.raises(Exception):
            event.model_id = "other-model"  # type: ignore[misc]

    def test_extra_fields_forbidden(
        self, valid_event_kwargs: dict[str, object]
    ) -> None:
        kwargs = {**valid_event_kwargs, "unexpected_field": "surprise"}
        with pytest.raises(ValueError):
            ModelLLMCallCompletedEvent(**kwargs)  # type: ignore[arg-type]


@pytest.mark.unit
class TestModelLLMCallCompletedEventSerialization:
    """Test JSON serialization matches omnidash contract."""

    EXPECTED_KEYS = frozenset(
        {
            "model_id",
            "endpoint_url",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cost_usd",
            "latency_ms",
            "request_type",
            "correlation_id",
            "session_id",
            "emitted_at",
        }
    )

    def test_json_keys_match_contract(
        self, valid_event_kwargs: dict[str, object]
    ) -> None:
        event = ModelLLMCallCompletedEvent(**valid_event_kwargs)  # type: ignore[arg-type]
        data = event.model_dump(mode="json")
        assert set(data.keys()) == self.EXPECTED_KEYS

    def test_roundtrip_serialization(
        self, valid_event_kwargs: dict[str, object]
    ) -> None:
        event = ModelLLMCallCompletedEvent(**valid_event_kwargs)  # type: ignore[arg-type]
        data = event.model_dump(mode="json")
        reconstructed = ModelLLMCallCompletedEvent.model_validate(data)
        assert reconstructed == event

    def test_re_export_from_package(self) -> None:
        """Verify re-export from models package works."""
        from omniintelligence.models import ModelLLMCallCompletedEvent as ReExported

        assert ReExported is ModelLLMCallCompletedEvent
