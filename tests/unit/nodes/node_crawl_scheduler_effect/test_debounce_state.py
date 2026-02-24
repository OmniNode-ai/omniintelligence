# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for DebounceStateManager.

Tests the core debounce guard logic:
  1. First trigger always passes
  2. Trigger within window is blocked
  3. Trigger after window expires is allowed
  4. clear_debounce resets window immediately
  5. clear_all resets all state

Reference: OMN-2384
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from omniintelligence.nodes.node_crawl_scheduler_effect.handlers.debounce_state import (
    DebounceStateManager,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.models.enum_crawler_type import (
    CrawlerType,
)

pytestmark = pytest.mark.unit

_SOURCE = "/Volumes/PRO-G40/Code/omniintelligence"
_WINDOW_S = 30

_T0 = datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def state() -> DebounceStateManager:
    return DebounceStateManager()


class TestDebounceStateFirstTrigger:
    """First trigger with no prior state must always be allowed."""

    def test_first_trigger_allowed(self, state: DebounceStateManager) -> None:
        allowed = state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=_WINDOW_S,
            now=_T0,
        )
        assert allowed is True

    def test_different_sources_independent(self, state: DebounceStateManager) -> None:
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        # Different source_ref — should still be allowed
        allowed = state.is_allowed(
            source_ref="/other/path",
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=_WINDOW_S,
            now=_T0,
        )
        assert allowed is True

    def test_different_crawler_types_independent(
        self, state: DebounceStateManager
    ) -> None:
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        # Same source_ref, different crawler type — should still be allowed
        allowed = state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.GIT_REPO,
            window_seconds=_WINDOW_S,
            now=_T0,
        )
        assert allowed is True


class TestDebounceStateWithinWindow:
    """Triggers within the window are blocked after first trigger."""

    def test_immediate_retry_blocked(self, state: DebounceStateManager) -> None:
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        blocked = state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=_WINDOW_S,
            now=_T0,  # same time
        )
        assert blocked is False

    def test_within_window_blocked(self, state: DebounceStateManager) -> None:
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        t1 = _T0 + timedelta(seconds=_WINDOW_S - 1)
        blocked = state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=_WINDOW_S,
            now=t1,
        )
        assert blocked is False

    def test_exactly_at_window_allowed(self, state: DebounceStateManager) -> None:
        """Trigger exactly at window boundary (>=) is allowed."""
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        t_boundary = _T0 + timedelta(seconds=_WINDOW_S)
        allowed = state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=_WINDOW_S,
            now=t_boundary,
        )
        assert allowed is True

    def test_after_window_allowed(self, state: DebounceStateManager) -> None:
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        t_after = _T0 + timedelta(seconds=_WINDOW_S + 1)
        allowed = state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=_WINDOW_S,
            now=t_after,
        )
        assert allowed is True


class TestDebounceStateClearDebounce:
    """clear_debounce resets the window immediately."""

    def test_clear_allows_next_trigger(self, state: DebounceStateManager) -> None:
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        # Still within window — would be blocked
        t_within = _T0 + timedelta(seconds=5)
        assert not state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=_WINDOW_S,
            now=t_within,
        )

        # Clear the window (simulating document-indexed.v1)
        cleared = state.clear_debounce(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
        )
        assert cleared is True

        # Now it should be allowed again
        assert state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=_WINDOW_S,
            now=t_within,
        )

    def test_clear_nonexistent_returns_false(self, state: DebounceStateManager) -> None:
        cleared = state.clear_debounce(
            source_ref="/nonexistent",
            crawler_type=CrawlerType.LINEAR,
        )
        assert cleared is False

    def test_clear_only_clears_specified_key(self, state: DebounceStateManager) -> None:
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.GIT_REPO,
            now=_T0,
        )

        # Clear only FILESYSTEM
        state.clear_debounce(source_ref=_SOURCE, crawler_type=CrawlerType.FILESYSTEM)

        # FILESYSTEM is now allowed
        assert state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=_WINDOW_S,
            now=_T0,
        )

        # GIT_REPO is still blocked
        assert not state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.GIT_REPO,
            window_seconds=300,  # 5 min
            now=_T0,
        )


class TestDebounceStateActiveKeyCount:
    """active_key_count returns correct count."""

    def test_empty_state_count_zero(self, state: DebounceStateManager) -> None:
        assert state.active_key_count() == 0

    def test_count_increases_on_record(self, state: DebounceStateManager) -> None:
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        assert state.active_key_count() == 1

    def test_count_decreases_on_clear(self, state: DebounceStateManager) -> None:
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        state.clear_debounce(source_ref=_SOURCE, crawler_type=CrawlerType.FILESYSTEM)
        assert state.active_key_count() == 0

    def test_clear_all_resets_to_zero(self, state: DebounceStateManager) -> None:
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        state.record_trigger(
            source_ref="/other",
            crawler_type=CrawlerType.GIT_REPO,
            now=_T0,
        )
        assert state.active_key_count() == 2
        state.clear_all()
        assert state.active_key_count() == 0


class TestDebounceStateDifferentWindows:
    """Debounce window is configurable per call."""

    def test_zero_window_always_allows(self, state: DebounceStateManager) -> None:
        """A window of 0s means every trigger is allowed."""
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        allowed = state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=0,
            now=_T0,
        )
        assert allowed is True

    def test_large_window_blocks_long_duration(
        self, state: DebounceStateManager
    ) -> None:
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.LINEAR,
            now=_T0,
        )
        # 59 min later — still within 60 min window
        t_near_end = _T0 + timedelta(minutes=59)
        blocked = state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.LINEAR,
            window_seconds=3600,  # 60 min
            now=t_near_end,
        )
        assert blocked is False

    def test_large_window_allows_after_expiry(
        self, state: DebounceStateManager
    ) -> None:
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.LINEAR,
            now=_T0,
        )
        t_after = _T0 + timedelta(hours=1)
        allowed = state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.LINEAR,
            window_seconds=3600,
            now=t_after,
        )
        assert allowed is True
