# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Tests for ModelLLMCallCompletedEvent additive GPU fields."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from omniintelligence.models.events.model_llm_call_completed_event import (
    ModelLLMCallCompletedEvent,
)


def _event_kwargs() -> dict[str, object]:
    return {
        "model_id": "qwen3-coder-30b-a3b",
        "endpoint_url": "http://localhost:8000",
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "cost_usd": 0.0,
        "usage_source": "ESTIMATED",
        "latency_ms": 123,
        "request_type": "completion",
        "correlation_id": "corr-1",
        "session_id": "sess-1",
        "emitted_at": datetime.now(UTC),
    }


@pytest.mark.unit
class TestModelLLMCallCompletedEventGpuFields:
    def test_gpu_fields_are_optional_for_backward_compatibility(self) -> None:
        event = ModelLLMCallCompletedEvent(**_event_kwargs())

        assert event.gpu_seconds is None
        assert event.gpu_type is None
        assert event.gpu_count is None
        assert event.compute_usage_source is None

    def test_accepts_gpu_compute_evidence_fields(self) -> None:
        event = ModelLLMCallCompletedEvent(
            **_event_kwargs(),
            gpu_seconds=7200.0,
            gpu_type="rtx_5090",
            gpu_count=1,
            compute_usage_source="API",
        )

        assert event.gpu_seconds == 7200.0
        assert event.gpu_type == "rtx_5090"
        assert event.gpu_count == 1
        assert event.compute_usage_source == "API"

    def test_rejects_negative_gpu_seconds(self) -> None:
        with pytest.raises(ValidationError, match="gpu_seconds"):
            ModelLLMCallCompletedEvent(**_event_kwargs(), gpu_seconds=-0.001)

    def test_rejects_invalid_compute_usage_source(self) -> None:
        with pytest.raises(ValidationError, match="compute_usage_source"):
            ModelLLMCallCompletedEvent(
                **_event_kwargs(),
                compute_usage_source="MEASURED",
            )
