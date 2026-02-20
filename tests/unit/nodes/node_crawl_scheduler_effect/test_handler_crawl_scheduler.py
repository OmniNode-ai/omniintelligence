# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for CrawlSchedulerEffect handler functions.

Tests:
  1. schedule_crawl_tick — debounce drops duplicates within window
  2. schedule_crawl_tick — passes after window expires
  3. handle_crawl_requested — debounce drops duplicates
  4. handle_crawl_requested — manual trigger emits crawl-tick
  5. handle_document_indexed — resets debounce window
  6. No Kafka publisher — returns ERROR status
  7. Config defaults match design doc values

Reference: OMN-2384
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

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
    EnumTriggerSource,
    ModelCrawlRequestedEvent,
    ModelCrawlSchedulerConfig,
)
from omniintelligence.protocols import ProtocolKafkaPublisher

pytestmark = pytest.mark.unit

_SOURCE = "/Volumes/PRO-G40/Code/omniintelligence"
_SCOPE = "omninode/omniintelligence"
_T0 = datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC)

# Short window for testing (1 second)
_TEST_CONFIG = ModelCrawlSchedulerConfig(
    debounce_windows_seconds={
        CrawlerType.FILESYSTEM: 5,
        CrawlerType.GIT_REPO: 10,
        CrawlerType.LINEAR: 20,
        CrawlerType.WATCHDOG: 5,
    }
)


# =============================================================================
# Mock Kafka publisher
# =============================================================================


class _MockKafkaPublisher:
    """Minimal Kafka publisher mock capturing published messages."""

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, object],
    ) -> None:
        self.published.append({"topic": topic, "key": key, "value": dict(value)})


assert isinstance(_MockKafkaPublisher(), ProtocolKafkaPublisher)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def fresh_state() -> DebounceStateManager:
    """A fresh in-memory debounce state per test."""
    return DebounceStateManager()


@pytest.fixture()
def publisher() -> _MockKafkaPublisher:
    return _MockKafkaPublisher()


# =============================================================================
# Tests: schedule_crawl_tick
# =============================================================================


@pytest.mark.asyncio
class TestScheduleCrawlTick:
    """Tests for schedule_crawl_tick (periodic scheduler tick)."""

    async def test_first_tick_emits(
        self,
        fresh_state: DebounceStateManager,
        publisher: _MockKafkaPublisher,
    ) -> None:
        result = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref=_SOURCE,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=_T0,
        )
        assert result.status == EnumCrawlSchedulerStatus.EMITTED
        assert result.crawl_type == CrawlerType.FILESYSTEM
        assert result.source_ref == _SOURCE
        assert result.trigger_source == EnumTriggerSource.SCHEDULED
        assert len(publisher.published) == 1
        assert publisher.published[0]["topic"] == "onex.cmd.omnimemory.crawl-tick.v1"

    async def test_duplicate_within_window_is_debounced(
        self,
        fresh_state: DebounceStateManager,
        publisher: _MockKafkaPublisher,
    ) -> None:
        # First tick
        await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref=_SOURCE,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=_T0,
        )

        # Second tick within window (1 second later, window=5s)
        t1 = _T0 + timedelta(seconds=1)
        result = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref=_SOURCE,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=t1,
        )
        assert result.status == EnumCrawlSchedulerStatus.DEBOUNCED
        assert result.debounce_window_seconds == 5
        # Only the first tick should have been published
        assert len(publisher.published) == 1

    async def test_tick_after_window_expires_emits(
        self,
        fresh_state: DebounceStateManager,
        publisher: _MockKafkaPublisher,
    ) -> None:
        # First tick
        await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref=_SOURCE,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=_T0,
        )

        # Tick after window expires (6s later, window=5s)
        t_after = _T0 + timedelta(seconds=6)
        result = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref=_SOURCE,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=t_after,
        )
        assert result.status == EnumCrawlSchedulerStatus.EMITTED
        assert len(publisher.published) == 2

    async def test_different_sources_not_debounced_together(
        self,
        fresh_state: DebounceStateManager,
        publisher: _MockKafkaPublisher,
    ) -> None:
        await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref=_SOURCE,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=_T0,
        )

        # Different source_ref — should emit immediately
        result = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref="/other/repo",
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=_T0,
        )
        assert result.status == EnumCrawlSchedulerStatus.EMITTED
        assert len(publisher.published) == 2

    async def test_no_publisher_returns_error(
        self,
        fresh_state: DebounceStateManager,
    ) -> None:
        result = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref=_SOURCE,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=None,
            now=_T0,
        )
        assert result.status == EnumCrawlSchedulerStatus.ERROR
        assert result.error_message is not None
        # The debounce entry MUST be recorded even when kafka_publisher is None.
        # This prevents a retry burst when Kafka recovers: all triggers within
        # the window are dropped until the window expires.
        assert not fresh_state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=_TEST_CONFIG.get_window_seconds(CrawlerType.FILESYSTEM),
            now=_T0,
        ), "Debounce entry must be recorded even when kafka_publisher is None"

    async def test_emitted_command_has_correct_fields(
        self,
        fresh_state: DebounceStateManager,
        publisher: _MockKafkaPublisher,
    ) -> None:
        await schedule_crawl_tick(
            crawl_type=CrawlerType.GIT_REPO,
            crawl_scope=_SCOPE,
            source_ref=_SOURCE,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=_T0,
        )
        assert len(publisher.published) == 1
        payload = publisher.published[0]["value"]
        assert payload["event_type"] == "CrawlTickRequested"
        assert payload["crawl_type"] == CrawlerType.GIT_REPO.value
        assert payload["crawl_scope"] == _SCOPE
        assert payload["source_ref"] == _SOURCE
        assert payload["trigger_source"] == EnumTriggerSource.SCHEDULED.value
        assert "correlation_id" in payload
        assert "triggered_at_utc" in payload


# =============================================================================
# Tests: handle_crawl_requested
# =============================================================================


@pytest.mark.asyncio
class TestHandleCrawlRequested:
    """Tests for handle_crawl_requested (manual/external trigger)."""

    def _make_event(
        self,
        source_ref: str = _SOURCE,
        trigger_source: EnumTriggerSource = EnumTriggerSource.MANUAL,
    ) -> ModelCrawlRequestedEvent:
        return ModelCrawlRequestedEvent(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref=source_ref,
            requested_at_utc=_T0.isoformat(),
            trigger_source=trigger_source,
        )

    async def test_manual_trigger_emits(
        self,
        fresh_state: DebounceStateManager,
        publisher: _MockKafkaPublisher,
    ) -> None:
        event = self._make_event()
        result = await handle_crawl_requested(
            event=event,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=_T0,
        )
        assert result.status == EnumCrawlSchedulerStatus.EMITTED
        assert result.trigger_source == EnumTriggerSource.MANUAL
        assert len(publisher.published) == 1

    async def test_git_hook_trigger_preserves_source(
        self,
        fresh_state: DebounceStateManager,
        publisher: _MockKafkaPublisher,
    ) -> None:
        event = self._make_event(trigger_source=EnumTriggerSource.GIT_HOOK)
        result = await handle_crawl_requested(
            event=event,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=_T0,
        )
        assert result.status == EnumCrawlSchedulerStatus.EMITTED
        assert result.trigger_source == EnumTriggerSource.GIT_HOOK
        payload = publisher.published[0]["value"]
        assert payload["trigger_source"] == EnumTriggerSource.GIT_HOOK.value

    async def test_duplicate_manual_trigger_is_debounced(
        self,
        fresh_state: DebounceStateManager,
        publisher: _MockKafkaPublisher,
    ) -> None:
        event = self._make_event()
        # First trigger
        await handle_crawl_requested(
            event=event,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=_T0,
        )
        # Second trigger within window
        t1 = _T0 + timedelta(seconds=2)
        result = await handle_crawl_requested(
            event=event,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=t1,
        )
        assert result.status == EnumCrawlSchedulerStatus.DEBOUNCED
        assert len(publisher.published) == 1

    async def test_correlation_id_preserved_from_event(
        self,
        fresh_state: DebounceStateManager,
        publisher: _MockKafkaPublisher,
    ) -> None:
        fixed_id = uuid4()
        event = ModelCrawlRequestedEvent(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref=_SOURCE,
            correlation_id=fixed_id,
            requested_at_utc=_T0.isoformat(),
            trigger_source=EnumTriggerSource.MANUAL,
        )
        result = await handle_crawl_requested(
            event=event,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=_T0,
        )
        assert result.correlation_id == fixed_id
        payload = publisher.published[0]["value"]
        assert payload["correlation_id"] == str(fixed_id)


# =============================================================================
# Tests: handle_document_indexed
# =============================================================================


class TestHandleDocumentIndexed:
    """Tests for handle_document_indexed (debounce reset)."""

    def test_clears_existing_window(self, fresh_state: DebounceStateManager) -> None:
        fresh_state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        # Verify it's within window
        assert not fresh_state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=30,
            now=_T0,
        )

        cleared = handle_document_indexed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            debounce_state=fresh_state,
        )
        assert cleared is True

        # Now it should be allowed
        assert fresh_state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=30,
            now=_T0,
        )

    def test_returns_false_when_no_entry(
        self, fresh_state: DebounceStateManager
    ) -> None:
        cleared = handle_document_indexed(
            source_ref="/no/such/path",
            crawler_type=CrawlerType.GIT_REPO,
            debounce_state=fresh_state,
        )
        assert cleared is False

    def test_only_clears_specified_key(self, fresh_state: DebounceStateManager) -> None:
        fresh_state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,
        )
        fresh_state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.GIT_REPO,
            now=_T0,
        )

        handle_document_indexed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            debounce_state=fresh_state,
        )

        # FILESYSTEM cleared
        assert fresh_state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            window_seconds=30,
            now=_T0,
        )
        # GIT_REPO still blocked
        assert not fresh_state.is_allowed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.GIT_REPO,
            window_seconds=300,
            now=_T0,
        )


# =============================================================================
# Tests: record_trigger timezone guard
# =============================================================================


class TestRecordTriggerTimezoneGuard:
    """record_trigger() must reject naive datetimes to prevent silent corruption."""

    def test_record_trigger_naive_datetime_raises(self) -> None:
        state = DebounceStateManager()
        naive_now = datetime(2026, 2, 20, 12, 0, 0)  # no tzinfo
        with pytest.raises(ValueError, match="UTC-aware"):
            state.record_trigger(
                source_ref=_SOURCE,
                crawler_type=CrawlerType.FILESYSTEM,
                now=naive_now,
            )

    def test_record_trigger_utc_aware_does_not_raise(self) -> None:
        state = DebounceStateManager()
        state.record_trigger(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            now=_T0,  # _T0 has tzinfo=UTC
        )


# =============================================================================
# Tests: Cross-handler integration (debounce shared state)
# =============================================================================


@pytest.mark.asyncio
class TestCrossHandlerDebounce:
    """Scheduler tick and manual trigger share the same debounce state."""

    async def test_manual_trigger_blocks_scheduler_tick(
        self,
        fresh_state: DebounceStateManager,
        publisher: _MockKafkaPublisher,
    ) -> None:
        """Manual trigger should block a scheduler tick within the window."""
        event = ModelCrawlRequestedEvent(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref=_SOURCE,
            requested_at_utc=_T0.isoformat(),
            trigger_source=EnumTriggerSource.MANUAL,
        )
        await handle_crawl_requested(
            event=event,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=_T0,
        )

        # Scheduler tick immediately after — should be debounced
        t1 = _T0 + timedelta(seconds=1)
        result = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref=_SOURCE,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=t1,
        )
        assert result.status == EnumCrawlSchedulerStatus.DEBOUNCED
        assert len(publisher.published) == 1

    async def test_indexed_resets_debounce_for_next_tick(
        self,
        fresh_state: DebounceStateManager,
        publisher: _MockKafkaPublisher,
    ) -> None:
        """After document-indexed.v1, the next scheduled tick is allowed."""
        await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref=_SOURCE,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=_T0,
        )

        # Simulate document-indexed.v1
        handle_document_indexed(
            source_ref=_SOURCE,
            crawler_type=CrawlerType.FILESYSTEM,
            debounce_state=fresh_state,
        )

        # Next tick (still within original window) — should be allowed now
        t1 = _T0 + timedelta(seconds=2)
        result = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope=_SCOPE,
            source_ref=_SOURCE,
            debounce_state=fresh_state,
            config=_TEST_CONFIG,
            kafka_publisher=publisher,
            now=t1,
        )
        assert result.status == EnumCrawlSchedulerStatus.EMITTED
        assert len(publisher.published) == 2


# =============================================================================
# Tests: Config defaults
# =============================================================================


class TestConfigDefaults:
    """ModelCrawlSchedulerConfig default values match the design doc."""

    def test_filesystem_default_30s(self) -> None:
        config = ModelCrawlSchedulerConfig()
        assert config.get_window_seconds(CrawlerType.FILESYSTEM) == 30

    def test_git_repo_default_5min(self) -> None:
        config = ModelCrawlSchedulerConfig()
        assert config.get_window_seconds(CrawlerType.GIT_REPO) == 300

    def test_linear_default_60min(self) -> None:
        config = ModelCrawlSchedulerConfig()
        assert config.get_window_seconds(CrawlerType.LINEAR) == 3600

    def test_watchdog_default_30s(self) -> None:
        config = ModelCrawlSchedulerConfig()
        assert config.get_window_seconds(CrawlerType.WATCHDOG) == 30

    def test_custom_windows_respected(self) -> None:
        config = ModelCrawlSchedulerConfig(
            debounce_windows_seconds={
                CrawlerType.FILESYSTEM: 10,
                CrawlerType.GIT_REPO: 60,
                CrawlerType.LINEAR: 120,
                CrawlerType.WATCHDOG: 10,
            }
        )
        assert config.get_window_seconds(CrawlerType.FILESYSTEM) == 10
        assert config.get_window_seconds(CrawlerType.GIT_REPO) == 60
        assert config.get_window_seconds(CrawlerType.LINEAR) == 120
