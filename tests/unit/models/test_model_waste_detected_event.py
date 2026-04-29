# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for ModelWasteDetectedEvent."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from omniintelligence.models.events.model_waste_detected_event import (
    ModelWasteDetectedEvent,
)


@pytest.fixture()
def valid_event_kwargs() -> dict[str, object]:
    """Minimal valid kwargs for constructing a ModelWasteDetectedEvent."""
    return {
        "session_id": "sess-456",
        "rule_id": "agent_loop",
        "severity": "MEDIUM",
        "waste_tokens": 1200,
        "waste_cost_usd": 0.018,
        "evidence": {"repeat_count": 3},
        "evidence_hash": "a" * 64,
        "dedup_key": "sess-456:agent_loop:" + ("a" * 64),
        "recommendation": "Avoid repeating identical tool calls.",
        "repo_name": "omnibase_infra",
        "machine_id": "devbox-1",
        "detected_at": datetime(2026, 4, 29, 12, 0, 0, tzinfo=UTC),
    }


@pytest.mark.unit
def test_construct_valid(valid_event_kwargs: dict[str, object]) -> None:
    event = ModelWasteDetectedEvent(**valid_event_kwargs)  # type: ignore[arg-type]
    assert event.session_id == "sess-456"
    assert event.rule_id == "agent_loop"
    assert event.severity == "MEDIUM"
    assert event.waste_tokens == 1200
    assert event.waste_cost_usd == 0.018


@pytest.mark.unit
def test_frozen_and_extra_forbidden(valid_event_kwargs: dict[str, object]) -> None:
    event = ModelWasteDetectedEvent(**valid_event_kwargs)  # type: ignore[arg-type]
    with pytest.raises(Exception):
        event.rule_id = "other"  # type: ignore[misc]

    with pytest.raises(ValueError):
        ModelWasteDetectedEvent(
            **{**valid_event_kwargs, "unexpected_field": "surprise"}
        )  # type: ignore[arg-type]


@pytest.mark.unit
def test_rejects_unknown_severity(valid_event_kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ModelWasteDetectedEvent(**{**valid_event_kwargs, "severity": "CRITICAL"})  # type: ignore[arg-type]


@pytest.mark.unit
def test_detected_at_must_be_tz_aware(
    valid_event_kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ModelWasteDetectedEvent(
            **{
                **valid_event_kwargs,
                "detected_at": datetime(2026, 4, 29, 12, 0, 0),
            }
        )  # type: ignore[arg-type]


@pytest.mark.unit
def test_re_export_from_package() -> None:
    from omniintelligence.models import ModelWasteDetectedEvent as ReExported

    assert ReExported is ModelWasteDetectedEvent
