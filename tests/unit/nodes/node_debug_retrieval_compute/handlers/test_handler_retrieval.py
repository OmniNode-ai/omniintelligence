# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for debug retrieval handler — time-decay logic and store delegation.

Tickets: OMN-11577, OMN-11581
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from omniintelligence.nodes.node_debug_retrieval_compute.handlers.handler_retrieval import (
    _time_decay_weight,
    query_fix_records_with_decay,
)

# ---------------------------------------------------------------------------
# _time_decay_weight
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_time_decay_weight_at_zero_age() -> None:
    """A record created right now should have weight ~1.0."""
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    weight = _time_decay_weight(now, now=now)
    assert abs(weight - 1.0) < 1e-9


@pytest.mark.unit
def test_time_decay_weight_at_half_life() -> None:
    """A record aged exactly 30 days should have weight ~0.5."""
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    created = now - timedelta(days=30)
    weight = _time_decay_weight(created, now=now)
    assert abs(weight - 0.5) < 1e-6


@pytest.mark.unit
def test_time_decay_weight_at_double_half_life() -> None:
    """A record aged 60 days (two half-lives) should have weight ~0.25."""
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    created = now - timedelta(days=60)
    weight = _time_decay_weight(created, now=now)
    assert abs(weight - 0.25) < 1e-6


@pytest.mark.unit
def test_time_decay_weight_older_is_smaller() -> None:
    """Older records must have strictly smaller weight than newer ones."""
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    w_new = _time_decay_weight(now - timedelta(days=1), now=now)
    w_old = _time_decay_weight(now - timedelta(days=10), now=now)
    assert w_new > w_old


@pytest.mark.unit
def test_time_decay_weight_naive_datetime_treated_as_utc() -> None:
    """Naive datetimes (no tzinfo) are treated as UTC without raising."""
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    naive = datetime(2025, 6, 1, 12, 0, 0)  # no tzinfo
    weight = _time_decay_weight(naive, now=now)
    assert abs(weight - 1.0) < 1e-9


@pytest.mark.unit
def test_time_decay_weight_future_date_clamps_to_one() -> None:
    """Records with future timestamps (age < 0) are clamped to weight 1.0."""
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    future = now + timedelta(days=1)
    weight = _time_decay_weight(future, now=now)
    # age_seconds=0 after max(0, ...) clamp → exp(0) = 1.0
    assert abs(weight - 1.0) < 1e-9


@pytest.mark.unit
def test_time_decay_weight_is_strictly_positive() -> None:
    """Weight is always > 0 regardless of age."""
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    very_old = now - timedelta(days=3650)  # ~10 years
    weight = _time_decay_weight(very_old, now=now)
    assert weight > 0.0
    assert math.isfinite(weight)


# ---------------------------------------------------------------------------
# query_fix_records_with_decay
# ---------------------------------------------------------------------------


def _make_store(records: list[dict[str, Any]]) -> AsyncMock:
    """Build a mock ProtocolDebugStore that returns the given records."""
    store = AsyncMock()
    store.query_fix_records = AsyncMock(return_value=records)
    return store


@pytest.mark.unit
async def test_query_returns_empty_when_store_returns_empty() -> None:
    """Empty store response produces empty output with no errors."""
    store = _make_store([])
    result = await query_fix_records_with_decay(
        failure_fingerprint="abc123", store=store, limit=10
    )
    assert result == []
    store.query_fix_records.assert_awaited_once_with(
        failure_fingerprint="abc123", limit=10
    )


@pytest.mark.unit
async def test_query_annotates_records_with_decay_weight() -> None:
    """Each returned record gains a 'time_decay_weight' key."""
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    record = {"id": "r1", "sha": "deadbeef", "created_at_utc": now}
    store = _make_store([record])

    result = await query_fix_records_with_decay(
        failure_fingerprint="fp1", store=store, limit=5, now=now
    )

    assert len(result) == 1
    assert "time_decay_weight" in result[0]
    assert abs(result[0]["time_decay_weight"] - 1.0) < 1e-9


@pytest.mark.unit
async def test_query_preserves_original_record_fields() -> None:
    """Original record fields are preserved alongside the injected weight."""
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    record = {
        "id": "r2",
        "repo": "omniclaude",
        "created_at_utc": now - timedelta(days=15),
    }
    store = _make_store([record])

    result = await query_fix_records_with_decay(
        failure_fingerprint="fp2", store=store, now=now
    )

    assert result[0]["id"] == "r2"
    assert result[0]["repo"] == "omniclaude"
    assert "time_decay_weight" in result[0]


@pytest.mark.unit
async def test_query_weight_zero_when_created_at_missing() -> None:
    """Records without 'created_at_utc' receive a fallback weight of 0.0."""
    store = _make_store([{"id": "r3", "sha": "cafebabe"}])

    result = await query_fix_records_with_decay(failure_fingerprint="fp3", store=store)

    assert result[0]["time_decay_weight"] == 0.0


@pytest.mark.unit
async def test_query_weight_zero_when_created_at_not_datetime() -> None:
    """Records where created_at_utc is a string (bad data) get weight 0.0."""
    store = _make_store([{"id": "r4", "created_at_utc": "2025-01-01T00:00:00Z"}])

    result = await query_fix_records_with_decay(failure_fingerprint="fp4", store=store)

    assert result[0]["time_decay_weight"] == 0.0


@pytest.mark.unit
async def test_query_respects_limit_parameter() -> None:
    """The limit parameter is forwarded to the store without modification."""
    store = _make_store([])

    await query_fix_records_with_decay(failure_fingerprint="fp5", store=store, limit=42)

    store.query_fix_records.assert_awaited_once_with(
        failure_fingerprint="fp5", limit=42
    )


@pytest.mark.unit
async def test_query_multiple_records_ordered_by_decay() -> None:
    """Multiple records each receive correct individual decay weights."""
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    records = [
        {"id": "new", "created_at_utc": now - timedelta(days=1)},
        {"id": "mid", "created_at_utc": now - timedelta(days=30)},
        {"id": "old", "created_at_utc": now - timedelta(days=60)},
    ]
    store = _make_store(records)

    result = await query_fix_records_with_decay(
        failure_fingerprint="fp6", store=store, now=now
    )

    weights = [r["time_decay_weight"] for r in result]
    # Newer records must have higher weight
    assert weights[0] > weights[1] > weights[2]
    # Spot-check the 30-day half-life record
    assert abs(weights[1] - 0.5) < 1e-6
