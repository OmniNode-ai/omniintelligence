# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for trigger record creation handler.

Ticket: OMN-3556
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_ci_failure_tracker_effect.handlers.handler_trigger_record import (
    handle_trigger_record,
)


@pytest.mark.unit
async def test_trigger_record_uses_streak_count_from_failure_streaks() -> None:
    """streak_count_at_trigger must come from failure_streaks, not row count."""
    store = AsyncMock()
    # failure_streaks says streak is 5
    store.get_streak.return_value = {"streak_count": 5}
    store.insert_trigger_record.return_value = {"id": str(uuid4())}

    result = await handle_trigger_record(
        repo="OmniNode-ai/test",
        branch="main",
        sha="deadbeef",
        failure_fingerprint="fp-abc",
        error_classification="test_failure",
        store=store,
        streak_threshold=3,
    )

    call_kwargs = store.insert_trigger_record.call_args.kwargs
    assert call_kwargs["streak_count_at_trigger"] == 5
    # Must NOT call count_failure_events
    assert not store.count_failure_events.called


@pytest.mark.unit
async def test_trigger_record_stores_observed_bad_sha_not_first_bad() -> None:
    """observed_bad_sha is the SHA present when threshold was crossed.
    It is NOT the first bad commit — just the first observed after threshold."""
    store = AsyncMock()
    store.get_streak.return_value = {"streak_count": 3}
    store.insert_trigger_record.return_value = {"id": str(uuid4())}

    await handle_trigger_record(
        repo="OmniNode-ai/test",
        branch="main",
        sha="the-sha-that-crossed-threshold",
        failure_fingerprint="fp-abc",
        error_classification="unknown",
        store=store,
        streak_threshold=3,
    )

    call_kwargs = store.insert_trigger_record.call_args.kwargs
    # Field must be observed_bad_sha (not first_bad_sha)
    assert "observed_bad_sha" in call_kwargs
    assert call_kwargs["observed_bad_sha"] == "the-sha-that-crossed-threshold"
    assert "first_bad_sha" not in call_kwargs


@pytest.mark.unit
async def test_trigger_record_streak_snapshot_in_ci_failure_event() -> None:
    """streak_snapshot in ci_failure_events must be copied from streak count,
    not computed fresh."""
    store = AsyncMock()
    store.get_streak.return_value = {"streak_count": 4}
    store.insert_trigger_record.return_value = {"id": str(uuid4())}

    await handle_trigger_record(
        repo="OmniNode-ai/test",
        branch="main",
        sha="abc",
        failure_fingerprint="fp",
        error_classification="unknown",
        store=store,
        streak_threshold=2,
    )

    event_kwargs = store.insert_ci_failure_event.call_args.kwargs
    # streak_snapshot must equal the streak count from failure_streaks
    assert event_kwargs["streak_snapshot"] == 4
    assert "consecutive_count" not in event_kwargs  # Old name must not appear


@pytest.mark.unit
async def test_trigger_record_not_created_below_threshold() -> None:
    """No trigger record if streak count is below threshold."""
    store = AsyncMock()
    store.get_streak.return_value = {"streak_count": 2}

    result = await handle_trigger_record(
        repo="OmniNode-ai/test",
        branch="main",
        sha="abc",
        failure_fingerprint="fp",
        error_classification="unknown",
        store=store,
        streak_threshold=3,
    )

    assert result is None
    store.insert_trigger_record.assert_not_called()
