# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for ModelSavingsEstimatedEvent."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omniintelligence.models.events import ModelSavingsEstimatedEvent


def _event(**overrides: object) -> ModelSavingsEstimatedEvent:
    payload: dict[str, object] = {
        "event_timestamp": datetime(2026, 4, 29, 12, 0, tzinfo=UTC),
        "session_id": "sess-x",
        "model_local": "qwen3-coder-30b",
        "model_cloud_baseline": "claude-opus-4",
        "local_cost_usd": Decimal("0.000000"),
        "cloud_cost_usd": Decimal("12.340000"),
        "savings_usd": Decimal("12.340000"),
        "repo_name": "omniclaude",
        "machine_id": "m-201",
        "correlation_id": "corr-1",
        "emitted_at": datetime(2026, 4, 29, 12, 0, 1, tzinfo=UTC),
    }
    payload.update(overrides)
    return ModelSavingsEstimatedEvent(**payload)


def test_model_savings_estimated_event_accepts_exact_contract() -> None:
    event = _event()

    assert event.session_id == "sess-x"
    assert event.local_cost_usd == Decimal("0.000000")
    assert event.cloud_cost_usd == Decimal("12.340000")
    assert event.savings_usd == Decimal("12.340000")


def test_model_savings_estimated_event_rejects_inconsistent_savings() -> None:
    with pytest.raises(ValidationError, match="savings_usd must equal"):
        _event(savings_usd=Decimal("12.330000"))


def test_model_savings_estimated_event_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _event(event_timestamp=datetime(2026, 4, 29, 12, 0))


def test_model_savings_estimated_event_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _event(unexpected=True)
