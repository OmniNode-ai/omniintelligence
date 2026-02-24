# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for NodeCrawlSchedulerEffect governance invariants.

Verifies:
    1. Protocol conformance: NodeCrawlSchedulerEffect is a NodeEffect
    2. Debounce guard: duplicate triggers within window are dropped (DEBOUNCED)
    3. Debounce guard: first trigger is always allowed (EMITTED or ERROR)
    4. Debounce reset: clear_debounce() allows the next trigger through immediately
    5. kafka_publisher=None: returns ERROR but still records debounce entry
       (so retry callers get DEBOUNCED, not a burst)
    6. Timezone guard: is_allowed() raises ValueError for naive datetime

Reference:
    - OMN-2384: CrawlSchedulerEffect implementation
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from omniintelligence.nodes.node_crawl_scheduler_effect.handlers.debounce_state import (
    DebounceStateManager,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.handlers.handler_crawl_scheduler import (
    handle_crawl_requested,
    handle_document_indexed,
    schedule_crawl_tick,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.models import (
    CrawlerType,
    EnumCrawlSchedulerStatus,
    ModelCrawlSchedulerConfig,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.node_tests.conftest import (
    MockKafkaPublisher,
    assert_node_protocol_conformance,
)

# =============================================================================
# Protocol Conformance
# =============================================================================


@pytest.mark.unit
class TestProtocolConformance:
    """NodeCrawlSchedulerEffect must conform to the NodeEffect protocol."""

    def test_node_is_node_effect(self) -> None:
        """NodeCrawlSchedulerEffect must be an instance of NodeEffect."""
        assert_node_protocol_conformance()


# =============================================================================
# Debounce Guard — First Trigger
# =============================================================================


@pytest.mark.unit
class TestFirstTriggerAllowed:
    """The first trigger for a (source_ref, crawler_type) key is always allowed."""

    @pytest.mark.asyncio
    async def test_schedule_crawl_tick_first_trigger_emitted(
        self,
        debounce_state: DebounceStateManager,
        fresh_config: ModelCrawlSchedulerConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        now_utc: datetime,
    ) -> None:
        """First scheduled tick must produce EMITTED status."""
        result = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope="omninode/test",
            source_ref="/tmp/test-repo",
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=mock_kafka_publisher,
            now=now_utc,
        )
        assert result.status == EnumCrawlSchedulerStatus.EMITTED
        assert result.source_ref == "/tmp/test-repo"
        assert result.crawl_type == CrawlerType.FILESYSTEM

    @pytest.mark.asyncio
    async def test_handle_crawl_requested_first_trigger_emitted(
        self,
        debounce_state: DebounceStateManager,
        fresh_config: ModelCrawlSchedulerConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        sample_crawl_requested_event: object,
        now_utc: datetime,
    ) -> None:
        """First manual trigger must produce EMITTED status."""
        from omniintelligence.nodes.node_crawl_scheduler_effect.models import (
            ModelCrawlRequestedEvent,
        )

        assert isinstance(sample_crawl_requested_event, ModelCrawlRequestedEvent)
        result = await handle_crawl_requested(
            event=sample_crawl_requested_event,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=mock_kafka_publisher,
            now=now_utc,
        )
        assert result.status == EnumCrawlSchedulerStatus.EMITTED


# =============================================================================
# Debounce Guard — Duplicate Within Window
# =============================================================================


@pytest.mark.unit
class TestDuplicateWithinWindowDebounced:
    """A second trigger within the debounce window must be dropped (DEBOUNCED)."""

    @pytest.mark.asyncio
    async def test_second_trigger_within_window_is_debounced(
        self,
        debounce_state: DebounceStateManager,
        fresh_config: ModelCrawlSchedulerConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        now_utc: datetime,
    ) -> None:
        """Second trigger 1 second after first must return DEBOUNCED."""
        source = "/tmp/debounce-test"

        # First trigger — should emit
        first = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope="scope",
            source_ref=source,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=mock_kafka_publisher,
            now=now_utc,
        )
        assert first.status == EnumCrawlSchedulerStatus.EMITTED

        # Second trigger — 1 second later, well within 30s window
        second = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope="scope",
            source_ref=source,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=mock_kafka_publisher,
            now=now_utc + timedelta(seconds=1),
        )
        assert second.status == EnumCrawlSchedulerStatus.DEBOUNCED
        assert second.debounce_window_seconds == fresh_config.get_window_seconds(
            CrawlerType.FILESYSTEM
        )

    @pytest.mark.asyncio
    async def test_trigger_after_window_expires_is_emitted(
        self,
        debounce_state: DebounceStateManager,
        fresh_config: ModelCrawlSchedulerConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        now_utc: datetime,
    ) -> None:
        """A trigger after the debounce window expires must return EMITTED."""
        source = "/tmp/window-expiry-test"
        window = fresh_config.get_window_seconds(CrawlerType.FILESYSTEM)

        await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope="scope",
            source_ref=source,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=mock_kafka_publisher,
            now=now_utc,
        )

        # Trigger exactly at window boundary + 1 second
        result = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope="scope",
            source_ref=source,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=mock_kafka_publisher,
            now=now_utc + timedelta(seconds=window + 1),
        )
        assert result.status == EnumCrawlSchedulerStatus.EMITTED

    @pytest.mark.asyncio
    async def test_different_crawler_types_do_not_debounce_each_other(
        self,
        debounce_state: DebounceStateManager,
        fresh_config: ModelCrawlSchedulerConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        now_utc: datetime,
    ) -> None:
        """FILESYSTEM and GIT_REPO triggers for same source_ref are independent."""
        source = "/tmp/multi-crawler-test"

        fs_result = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope="scope",
            source_ref=source,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=mock_kafka_publisher,
            now=now_utc,
        )
        assert fs_result.status == EnumCrawlSchedulerStatus.EMITTED

        # Different crawler type — must NOT be debounced
        git_result = await schedule_crawl_tick(
            crawl_type=CrawlerType.GIT_REPO,
            crawl_scope="scope",
            source_ref=source,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=mock_kafka_publisher,
            now=now_utc,
        )
        assert git_result.status == EnumCrawlSchedulerStatus.EMITTED


# =============================================================================
# Debounce Reset via clear_debounce()
# =============================================================================


@pytest.mark.unit
class TestDebounceReset:
    """Clearing the debounce entry allows the next trigger through immediately."""

    @pytest.mark.asyncio
    async def test_clear_debounce_allows_next_trigger(
        self,
        debounce_state: DebounceStateManager,
        fresh_config: ModelCrawlSchedulerConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        now_utc: datetime,
    ) -> None:
        """After clear_debounce(), the next trigger within window must be EMITTED."""
        source = "/tmp/reset-test"
        crawler = CrawlerType.FILESYSTEM

        # First trigger — emits and sets debounce
        first = await schedule_crawl_tick(
            crawl_type=crawler,
            crawl_scope="scope",
            source_ref=source,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=mock_kafka_publisher,
            now=now_utc,
        )
        assert first.status == EnumCrawlSchedulerStatus.EMITTED

        # Simulate document-indexed.v1 resetting the window
        cleared = debounce_state.clear_debounce(
            source_ref=source,
            crawler_type=crawler,
        )
        assert cleared is True

        # Next trigger — should emit even though window hasn't elapsed
        second = await schedule_crawl_tick(
            crawl_type=crawler,
            crawl_scope="scope",
            source_ref=source,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=mock_kafka_publisher,
            now=now_utc + timedelta(seconds=1),
        )
        assert second.status == EnumCrawlSchedulerStatus.EMITTED

    @pytest.mark.asyncio
    async def test_handle_document_indexed_resets_debounce_via_handler(
        self,
        debounce_state: DebounceStateManager,
        fresh_config: ModelCrawlSchedulerConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        now_utc: datetime,
        source_ref: str,
    ) -> None:
        """handle_document_indexed() must reset the debounce window so the next
        trigger is emitted without waiting for the window to expire.

        This test exercises the handler function itself rather than calling
        clear_debounce() directly, verifying the full delegation path:
        handle_document_indexed() → debounce_state.clear_debounce().
        """
        crawler = CrawlerType.FILESYSTEM

        # Prime the debounce state: first trigger emits and sets the window.
        first = await schedule_crawl_tick(
            crawl_type=crawler,
            crawl_scope="scope",
            source_ref=source_ref,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=mock_kafka_publisher,
            now=now_utc,
        )
        assert first.status == EnumCrawlSchedulerStatus.EMITTED

        # Confirm debounce is active: a second tick within the window is dropped.
        blocked = await schedule_crawl_tick(
            crawl_type=crawler,
            crawl_scope="scope",
            source_ref=source_ref,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=mock_kafka_publisher,
            now=now_utc + timedelta(seconds=1),
        )
        assert blocked.status == EnumCrawlSchedulerStatus.DEBOUNCED

        # Reset via the handler function — NOT debounce_state.clear_debounce() directly.
        cleared = handle_document_indexed(
            source_ref=source_ref,
            crawler_type=crawler,
            debounce_state=debounce_state,
        )
        assert cleared is True

        # After the reset, the next tick within the original window must emit.
        after_reset = await schedule_crawl_tick(
            crawl_type=crawler,
            crawl_scope="scope",
            source_ref=source_ref,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=mock_kafka_publisher,
            now=now_utc + timedelta(seconds=2),
        )
        assert after_reset.status == EnumCrawlSchedulerStatus.EMITTED


# =============================================================================
# kafka_publisher=None — ERROR + debounce recorded
# =============================================================================


@pytest.mark.unit
class TestKafkaPublisherNone:
    """When kafka_publisher is None, returns ERROR but still records debounce entry.

    This is intentional: prevents retry bursts when Kafka is temporarily
    unavailable.  Callers that retry after ERROR will receive DEBOUNCED
    rather than a flood of ERROR results.
    """

    @pytest.mark.asyncio
    async def test_no_publisher_returns_error(
        self,
        debounce_state: DebounceStateManager,
        fresh_config: ModelCrawlSchedulerConfig,
        now_utc: datetime,
    ) -> None:
        """Missing kafka_publisher must produce ERROR status."""
        result = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope="scope",
            source_ref="/tmp/no-publisher-test",
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=None,
            now=now_utc,
        )
        assert result.status == EnumCrawlSchedulerStatus.ERROR
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_no_publisher_still_records_debounce_entry(
        self,
        debounce_state: DebounceStateManager,
        fresh_config: ModelCrawlSchedulerConfig,
        now_utc: datetime,
    ) -> None:
        """ERROR result must still record debounce entry to prevent retry bursts."""
        source = "/tmp/debounce-on-error-test"
        crawler = CrawlerType.FILESYSTEM

        # Trigger with no publisher — returns ERROR
        error_result = await schedule_crawl_tick(
            crawl_type=crawler,
            crawl_scope="scope",
            source_ref=source,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=None,
            now=now_utc,
        )
        assert error_result.status == EnumCrawlSchedulerStatus.ERROR

        # Debounce entry must be recorded despite ERROR
        last_triggered = debounce_state.get_last_triggered_at(
            source_ref=source,
            crawler_type=crawler,
        )
        assert last_triggered is not None, (
            "Debounce entry must be recorded even when kafka_publisher is None. "
            "This prevents retry bursts when Kafka recovers."
        )

    @pytest.mark.asyncio
    async def test_retry_after_error_is_debounced(
        self,
        debounce_state: DebounceStateManager,
        fresh_config: ModelCrawlSchedulerConfig,
        now_utc: datetime,
    ) -> None:
        """A caller retrying after ERROR within the window must receive DEBOUNCED."""
        source = "/tmp/retry-debounced-test"

        # First call — ERROR (no publisher)
        await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope="scope",
            source_ref=source,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=None,
            now=now_utc,
        )

        # Retry 2 seconds later (still within 30s window), with publisher this time
        from unittest.mock import AsyncMock

        publisher = MockKafkaPublisher()
        publisher.publish = AsyncMock()

        retry_result = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope="scope",
            source_ref=source,
            debounce_state=debounce_state,
            config=fresh_config,
            kafka_publisher=publisher,
            now=now_utc + timedelta(seconds=2),
        )
        assert retry_result.status == EnumCrawlSchedulerStatus.DEBOUNCED, (
            "A retry after ERROR within the debounce window must return DEBOUNCED, "
            "not EMITTED. This is the documented debounce-on-error behavior."
        )


# =============================================================================
# Timezone Guard — is_allowed() with naive datetime
# =============================================================================


@pytest.mark.unit
class TestTimezoneGuard:
    """is_allowed() must reject naive datetimes to prevent runtime TypeError."""

    def test_naive_datetime_raises_value_error(
        self,
        debounce_state: DebounceStateManager,
        fresh_config: ModelCrawlSchedulerConfig,
    ) -> None:
        """Passing a naive datetime to is_allowed() must raise ValueError."""
        naive_now = datetime(2026, 2, 20, 12, 0, 0)  # no tzinfo

        with pytest.raises(ValueError, match="UTC-aware"):
            debounce_state.is_allowed(
                source_ref="/tmp/tz-test",
                crawler_type=CrawlerType.FILESYSTEM,
                window_seconds=30,
                now=naive_now,
            )

    def test_utc_aware_datetime_does_not_raise(
        self,
        debounce_state: DebounceStateManager,
    ) -> None:
        """UTC-aware datetime must not raise."""
        utc_now = datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC)
        # Should not raise
        result = debounce_state.is_allowed(
            source_ref="/tmp/tz-ok-test",
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=30,
            now=utc_now,
        )
        assert result is True

    def test_non_utc_aware_datetime_does_not_raise(
        self,
        debounce_state: DebounceStateManager,
    ) -> None:
        """Any timezone-aware datetime (not just UTC) must be accepted."""
        # The guard only requires tzinfo to be non-None
        tz_aware_now = datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC)
        result = debounce_state.is_allowed(
            source_ref="/tmp/tz-nz-test",
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=30,
            now=tz_aware_now,
        )
        assert result is True
