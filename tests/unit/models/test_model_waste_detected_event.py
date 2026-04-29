# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for ModelWasteDetectedEvent."""

from __future__ import annotations

from datetime import UTC, datetime, tzinfo

import pytest

from omniintelligence.models.events.model_waste_detected_event import (
    ModelWasteDetectedEvent,
)


class NoneOffsetTimezone(tzinfo):
    """tzinfo implementation that is present but not offset-aware."""

    def utcoffset(self, dt: datetime | None) -> None:
        return None

    def dst(self, dt: datetime | None) -> None:
        return None


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
def test_detected_at_rejects_tzinfo_without_offset(
    valid_event_kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ModelWasteDetectedEvent(
            **{
                **valid_event_kwargs,
                "detected_at": datetime(
                    2026,
                    4,
                    29,
                    12,
                    0,
                    0,
                    tzinfo=NoneOffsetTimezone(),
                ),
            }
        )  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.parametrize("waste_tokens", [-1, -100])
def test_rejects_negative_waste_tokens(
    valid_event_kwargs: dict[str, object],
    waste_tokens: int,
) -> None:
    with pytest.raises(ValueError):
        ModelWasteDetectedEvent(**{**valid_event_kwargs, "waste_tokens": waste_tokens})  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.parametrize("waste_cost_usd", [-0.01, -1.0])
def test_rejects_negative_waste_cost_usd(
    valid_event_kwargs: dict[str, object],
    waste_cost_usd: float,
) -> None:
    with pytest.raises(ValueError):
        ModelWasteDetectedEvent(
            **{**valid_event_kwargs, "waste_cost_usd": waste_cost_usd}
        )  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.parametrize("evidence_hash", ["a" * 63, "a" * 65, "g" * 64, " " * 64])
def test_rejects_invalid_evidence_hash(
    valid_event_kwargs: dict[str, object],
    evidence_hash: str,
) -> None:
    with pytest.raises(ValueError):
        ModelWasteDetectedEvent(
            **{**valid_event_kwargs, "evidence_hash": evidence_hash}
        )  # type: ignore[arg-type]


@pytest.mark.unit
def test_re_export_from_package() -> None:
    from omniintelligence.models import ModelWasteDetectedEvent as ReExported

    assert ReExported is ModelWasteDetectedEvent
