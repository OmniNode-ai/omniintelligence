# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""In-memory debounce state manager for CrawlSchedulerEffect.

Maintains per-``(source_ref, crawler_type)`` debounce windows.
State is stored in-memory (not persisted to PostgreSQL) because:
  - Debounce windows are short (30s-60min)
  - Loss on restart is acceptable (just allows one extra crawl)
  - No DB dependency = no DB failure modes in the scheduler hot path

Thread Safety:
    The state dict is not protected by a lock.  This is intentional:
    CrawlSchedulerEffect runs in a single asyncio event loop.  Concurrent
    access via separate threads is not expected.  If that assumption changes,
    add asyncio.Lock wrapping.

Reference: OMN-2384
"""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple

from omniintelligence.nodes.node_crawl_scheduler_effect.models.enum_crawler_type import (
    CrawlerType,
)


class _DebounceKey(NamedTuple):
    """Composite key for debounce state lookup."""

    source_ref: str
    crawler_type: CrawlerType


class DebounceStateManager:
    """In-memory manager for per-source debounce windows.

    Maintains a mapping of ``(source_ref, crawler_type)`` → ``last_triggered_at``
    timestamps.  A trigger is allowed through when:
      - No entry exists for the key, OR
      - ``now - last_triggered_at >= debounce_window_seconds``

    Debounce windows are reset (cleared) by ``clear_debounce()`` when a
    ``document-indexed.v1`` event confirms successful crawl completion.

    Usage:
        state = DebounceStateManager()

        # Check whether a trigger is allowed
        allowed = state.is_allowed(
            source_ref="/path/to/file",
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=30,
            now=datetime.now(UTC),
        )

        if allowed:
            state.record_trigger(
                source_ref="/path/to/file",
                crawler_type=CrawlerType.FILESYSTEM,
                now=datetime.now(UTC),
            )
    """

    def __init__(self) -> None:
        self._state: dict[_DebounceKey, datetime] = {}

    def is_allowed(
        self,
        *,
        source_ref: str,
        crawler_type: CrawlerType,
        window_seconds: int,
        now: datetime,
    ) -> bool:
        """Return True if the trigger should be allowed through.

        A trigger is allowed when no debounce entry exists, or when the
        debounce window has fully expired.

        Args:
            source_ref: Canonical source identifier.
            crawler_type: Crawler type for the trigger.
            window_seconds: Active debounce window in seconds.
            now: Current UTC datetime (injected for testability).

        Returns:
            True if the trigger should be processed; False if it should be
            dropped silently.

        Raises:
            ValueError: If ``now`` is a naive datetime (no tzinfo).  Naive
                datetimes cannot be safely subtracted from UTC-aware stored
                timestamps and would raise a ``TypeError`` at runtime.
        """
        if now.tzinfo is None:
            raise ValueError(
                "now must be UTC-aware (tzinfo required). "
                "Pass datetime.now(UTC) or equivalent — naive datetimes "
                "cannot be compared with UTC-aware stored timestamps."
            )
        key = _DebounceKey(source_ref=source_ref, crawler_type=crawler_type)
        last = self._state.get(key)
        if last is None:
            return True
        elapsed = (now - last).total_seconds()
        return elapsed >= window_seconds

    def record_trigger(
        self,
        *,
        source_ref: str,
        crawler_type: CrawlerType,
        now: datetime,
    ) -> None:
        """Record that a trigger was processed, starting the debounce window.

        This MUST be called immediately after deciding to emit a crawl-tick,
        before the Kafka publish.  If called after the publish, a race between
        two rapid triggers could both pass the ``is_allowed`` check.

        Args:
            source_ref: Canonical source identifier.
            crawler_type: Crawler type for the trigger.
            now: Current UTC datetime (injected for testability).
        """
        key = _DebounceKey(source_ref=source_ref, crawler_type=crawler_type)
        self._state[key] = now

    def clear_debounce(
        self,
        *,
        source_ref: str,
        crawler_type: CrawlerType,
    ) -> bool:
        """Clear the debounce window for a (source_ref, crawler_type) key.

        Called when a ``document-indexed.v1`` event confirms that a crawl
        completed successfully.  Clearing the window allows the next trigger
        to pass through immediately.

        Args:
            source_ref: Canonical source identifier.
            crawler_type: Crawler type.

        Returns:
            True if an entry was cleared; False if no entry existed.
        """
        key = _DebounceKey(source_ref=source_ref, crawler_type=crawler_type)
        if key in self._state:
            del self._state[key]
            return True
        return False

    def get_last_triggered_at(
        self,
        *,
        source_ref: str,
        crawler_type: CrawlerType,
    ) -> datetime | None:
        """Return the last trigger timestamp for a key, or None.

        Used for diagnostics and testing.
        """
        key = _DebounceKey(source_ref=source_ref, crawler_type=crawler_type)
        return self._state.get(key)

    def active_key_count(self) -> int:
        """Return the number of active debounce entries."""
        return len(self._state)

    def clear_all(self) -> None:
        """Clear all debounce state.

        Should only be called in tests or on process shutdown.
        """
        self._state.clear()


# Module-level singleton used by the registry.
# Tests must call ``_DEBOUNCE_STATE.clear_all()`` in setup/teardown.
_DEBOUNCE_STATE = DebounceStateManager()


def get_debounce_state() -> DebounceStateManager:
    """Return the module-level singleton debounce state manager."""
    return _DEBOUNCE_STATE


__all__ = ["DebounceStateManager", "get_debounce_state"]
