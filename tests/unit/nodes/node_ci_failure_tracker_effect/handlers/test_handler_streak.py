# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for streak management handler.

Ticket: OMN-3556
"""

from unittest.mock import AsyncMock

import pytest

from omniintelligence.nodes.node_ci_failure_tracker_effect.handlers.handler_streak import (
    get_current_streak,
    increment_streak,
    reset_streak,
)


@pytest.mark.unit
async def test_increment_streak_returns_new_count() -> None:
    """increment_streak must call upsert_streak and return the result."""
    mock_store = AsyncMock()
    mock_store.upsert_streak.return_value = {"streak_count": 3, "id": "uuid-1"}
    result = await increment_streak(
        repo="OmniNode-ai/test", branch="main", sha="abc123", store=mock_store
    )
    assert result["streak_count"] == 3
    # Must call upsert_streak, NOT count ci_failure_events
    mock_store.upsert_streak.assert_called_once()
    # Verify count_failure_events was never called (method should not exist or not be called)
    assert not mock_store.count_failure_events.called


@pytest.mark.unit
async def test_reset_streak_sets_count_to_zero() -> None:
    """reset_streak must call store.reset_streak with correct kwargs."""
    mock_store = AsyncMock()
    await reset_streak(repo="OmniNode-ai/test", branch="main", store=mock_store)
    mock_store.reset_streak.assert_called_once_with(
        repo="OmniNode-ai/test", branch="main"
    )


@pytest.mark.unit
async def test_get_current_streak_reads_from_failure_streaks_table() -> None:
    """get_current_streak must read from failure_streaks via store.get_streak."""
    mock_store = AsyncMock()
    mock_store.get_streak.return_value = {"streak_count": 5}
    count = await get_current_streak(
        repo="OmniNode-ai/test", branch="main", store=mock_store
    )
    assert count == 5
    # Must call get_streak (reads failure_streaks), NOT count ci_failure_events
    mock_store.get_streak.assert_called_once()
    assert not mock_store.count_failure_events.called


@pytest.mark.unit
async def test_get_current_streak_returns_zero_when_no_row() -> None:
    """get_current_streak returns 0 when no streak row exists."""
    mock_store = AsyncMock()
    mock_store.get_streak.return_value = None
    count = await get_current_streak(
        repo="OmniNode-ai/test", branch="main", store=mock_store
    )
    assert count == 0
