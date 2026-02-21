# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for NodeWatchdogEffect governance invariants.

Verifies:
    1. Protocol conformance: NodeWatchdogEffect is a NodeEffect
    2. start_watching() with mock observer returns STARTED status
    3. start_watching() with no kafka_publisher still returns STARTED
    4. stop_watching() with registered observer returns STOPPED
    5. stop_watching() with no registered observer returns STOPPED (no-op)
    6. File change event triggers publish to crawl-requested.v1 topic
    7. Ignored file suffixes are filtered silently (via _AsyncKafkaEventHandler)
    8. ModelWatchdogConfig rejects relative paths
    9. ModelWatchdogConfig.is_ignored() matches configured suffixes

Reference:
    - OMN-2386: WatchdogEffect implementation
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_watchdog_effect.handlers.handler_watchdog import (
    TOPIC_CRAWL_REQUESTED_V1,
    _AsyncKafkaEventHandler,
    start_watching,
    stop_watching,
)
from omniintelligence.nodes.node_watchdog_effect.models import (
    EnumWatchdogObserverType,
    EnumWatchdogStatus,
    ModelWatchdogConfig,
)
from omniintelligence.nodes.node_watchdog_effect.node_tests.conftest import (
    MockKafkaPublisher,
    MockObserver,
    assert_node_protocol_conformance,
)
from omniintelligence.nodes.node_watchdog_effect.registry.registry_watchdog_effect import (
    RegistryWatchdogEffect,
)

# =============================================================================
# Protocol Conformance
# =============================================================================


@pytest.mark.unit
class TestProtocolConformance:
    """NodeWatchdogEffect must conform to the NodeEffect protocol."""

    def test_node_is_node_effect(self) -> None:
        """NodeWatchdogEffect must be an instance of NodeEffect."""
        assert_node_protocol_conformance()


# =============================================================================
# start_watching() — happy path
# =============================================================================


@pytest.mark.unit
class TestStartWatching:
    """start_watching() must start the observer and return STARTED."""

    @pytest.mark.asyncio
    async def test_start_watching_returns_started(
        self,
        default_config: ModelWatchdogConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        polling_observer_factory: Any,
    ) -> None:
        """start_watching() with a mock observer must return STARTED."""
        result = await start_watching(
            config=default_config,
            correlation_id=uuid4(),
            kafka_publisher=mock_kafka_publisher,
            observer_factory=polling_observer_factory,
        )
        assert result.status == EnumWatchdogStatus.STARTED
        assert result.observer_type == EnumWatchdogObserverType.POLLING
        assert len(result.watched_paths) == 1

    @pytest.mark.asyncio
    async def test_start_watching_registers_observer_in_registry(
        self,
        default_config: ModelWatchdogConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        polling_observer_factory: Any,
    ) -> None:
        """start_watching() must register the observer in RegistryWatchdogEffect."""
        await start_watching(
            config=default_config,
            correlation_id=uuid4(),
            kafka_publisher=mock_kafka_publisher,
            observer_factory=polling_observer_factory,
        )
        assert RegistryWatchdogEffect.get_observer() is not None
        assert (
            RegistryWatchdogEffect.get_observer_type()
            == EnumWatchdogObserverType.POLLING
        )

    @pytest.mark.asyncio
    async def test_start_watching_calls_observer_start(
        self,
        default_config: ModelWatchdogConfig,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """start_watching() must call observer.start()."""
        mock_observer = MockObserver(observer_type=EnumWatchdogObserverType.POLLING)

        def factory() -> tuple[MockObserver, EnumWatchdogObserverType]:
            return mock_observer, EnumWatchdogObserverType.POLLING

        await start_watching(
            config=default_config,
            correlation_id=uuid4(),
            kafka_publisher=mock_kafka_publisher,
            observer_factory=factory,
        )
        assert mock_observer.started is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_start_watching_schedules_watches_for_all_paths(
        self,
        tmp_path: Any,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """start_watching() must call observer.schedule() for each configured path."""
        mock_observer = MockObserver(observer_type=EnumWatchdogObserverType.POLLING)

        def factory() -> tuple[MockObserver, EnumWatchdogObserverType]:
            return mock_observer, EnumWatchdogObserverType.POLLING

        config = ModelWatchdogConfig(watched_paths=(str(tmp_path),))
        await start_watching(
            config=config,
            correlation_id=uuid4(),
            kafka_publisher=mock_kafka_publisher,
            observer_factory=factory,
        )
        scheduled_paths = [w["path"] for w in mock_observer.scheduled_watches]
        assert str(tmp_path) in scheduled_paths, (
            f"Expected {tmp_path} in scheduled watches, got: {scheduled_paths}"
        )

    @pytest.mark.asyncio
    async def test_start_watching_watched_paths_in_result(
        self,
        tmp_path: Any,
        mock_kafka_publisher: MockKafkaPublisher,
        polling_observer_factory: Any,
    ) -> None:
        """start_watching() result must include the configured watched paths."""
        config = ModelWatchdogConfig(
            watched_paths=(str(tmp_path),),
            crawl_scope="omninode/test",
        )
        result = await start_watching(
            config=config,
            correlation_id=uuid4(),
            kafka_publisher=mock_kafka_publisher,
            observer_factory=polling_observer_factory,
        )
        assert result.status == EnumWatchdogStatus.STARTED
        assert str(tmp_path) in result.watched_paths

    @pytest.mark.asyncio
    async def test_start_watching_twice_returns_early_with_started(
        self,
        default_config: ModelWatchdogConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        caplog: Any,
    ) -> None:
        """Calling start_watching() a second time must return STARTED early and log a warning.

        The expected behavior after the double-start guard is in place:
        - First call: starts observer, returns STARTED, registers in registry.
        - Second call: detects existing observer in registry, returns STARTED
          immediately (no new observer started), and logs a warning.
        Only one observer must be started across both calls.
        """
        import logging

        from omniintelligence.nodes.node_watchdog_effect.node_tests.conftest import (
            make_mock_observer_factory,
        )

        factory, _ = make_mock_observer_factory(EnumWatchdogObserverType.POLLING)

        # First call — must start the observer
        first_result = await start_watching(
            config=default_config,
            correlation_id=uuid4(),
            kafka_publisher=mock_kafka_publisher,
            observer_factory=factory,
        )
        assert first_result.status == EnumWatchdogStatus.STARTED
        assert len(factory.created_observers) == 1
        first_observer = factory.created_observers[0]
        assert first_observer.started is True

        # Second call — must return early without starting a new observer
        with caplog.at_level(logging.WARNING, logger="omniintelligence"):
            second_result = await start_watching(
                config=default_config,
                correlation_id=uuid4(),
                kafka_publisher=mock_kafka_publisher,
                observer_factory=factory,
            )

        assert second_result.status == EnumWatchdogStatus.STARTED
        # No second observer should have been created
        assert len(factory.created_observers) == 1, (
            "start_watching() called twice must not create a second observer"
        )
        # A warning must have been emitted to signal the double-start attempt
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any(
            "already" in msg.lower() or "running" in msg.lower()
            for msg in warning_messages
        ), f"Expected a warning about observer already running, got: {warning_messages}"

    @pytest.mark.asyncio
    async def test_start_watching_no_publisher_then_with_publisher_hits_guard(
        self,
        default_config: ModelWatchdogConfig,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """start_watching(kafka_publisher=None) starts the observer; a subsequent
        call with a valid publisher hits the double-start guard and returns STARTED
        without creating a second observer."""
        from omniintelligence.nodes.node_watchdog_effect.node_tests.conftest import (
            make_mock_observer_factory,
        )

        factory, _ = make_mock_observer_factory(EnumWatchdogObserverType.POLLING)

        # First call with no publisher — observer starts idle
        first_result = await start_watching(
            config=default_config,
            correlation_id=uuid4(),
            kafka_publisher=None,
            observer_factory=factory,
        )
        assert first_result.status == EnumWatchdogStatus.STARTED
        assert len(factory.created_observers) == 1
        assert factory.created_observers[0].started is True

        # Second call with a valid publisher — hits double-start guard
        second_result = await start_watching(
            config=default_config,
            correlation_id=uuid4(),
            kafka_publisher=mock_kafka_publisher,
            observer_factory=factory,
        )
        assert second_result.status == EnumWatchdogStatus.STARTED
        # No second observer must have been created
        assert len(factory.created_observers) == 1, (
            "double-start guard must prevent a second observer from being created"
        )


# =============================================================================
# start_watching() — no kafka_publisher
# =============================================================================


@pytest.mark.unit
class TestStartWatchingNoPublisher:
    """start_watching() with no kafka_publisher still starts the observer."""

    @pytest.mark.asyncio
    async def test_start_watching_no_publisher_returns_started(
        self,
        default_config: ModelWatchdogConfig,
        polling_observer_factory: Any,
    ) -> None:
        """start_watching() with kafka_publisher=None must return STARTED (not ERROR)."""
        result = await start_watching(
            config=default_config,
            correlation_id=uuid4(),
            kafka_publisher=None,
            observer_factory=polling_observer_factory,
        )
        assert result.status == EnumWatchdogStatus.STARTED

    @pytest.mark.asyncio
    async def test_start_watching_no_publisher_observer_started(
        self,
        default_config: ModelWatchdogConfig,
    ) -> None:
        """Observer must start even when kafka_publisher=None."""
        mock_observer = MockObserver()

        def factory() -> tuple[MockObserver, EnumWatchdogObserverType]:
            return mock_observer, EnumWatchdogObserverType.POLLING

        await start_watching(
            config=default_config,
            correlation_id=uuid4(),
            kafka_publisher=None,
            observer_factory=factory,
        )
        assert mock_observer.started is True


# =============================================================================
# stop_watching()
# =============================================================================


@pytest.mark.unit
class TestStopWatching:
    """stop_watching() must gracefully stop the active observer."""

    @pytest.mark.asyncio
    async def test_stop_watching_after_start_returns_stopped(
        self,
        default_config: ModelWatchdogConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        polling_observer_factory: Any,
    ) -> None:
        """stop_watching() after start must return STOPPED."""
        await start_watching(
            config=default_config,
            correlation_id=uuid4(),
            kafka_publisher=mock_kafka_publisher,
            observer_factory=polling_observer_factory,
        )
        result = await stop_watching(correlation_id=uuid4())
        assert result.status == EnumWatchdogStatus.STOPPED

    @pytest.mark.asyncio
    async def test_stop_watching_calls_stop_and_join(
        self,
        default_config: ModelWatchdogConfig,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """stop_watching() must call observer.stop() and observer.join()."""
        mock_observer = MockObserver()

        def factory() -> tuple[MockObserver, EnumWatchdogObserverType]:
            return mock_observer, EnumWatchdogObserverType.POLLING

        await start_watching(
            config=default_config,
            correlation_id=uuid4(),
            kafka_publisher=mock_kafka_publisher,
            observer_factory=factory,
        )
        await stop_watching(correlation_id=uuid4())

        assert mock_observer.stopped is True
        assert mock_observer.joined is True

    @pytest.mark.asyncio
    async def test_stop_watching_clears_registry(
        self,
        default_config: ModelWatchdogConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        polling_observer_factory: Any,
    ) -> None:
        """stop_watching() must clear the registry after stopping."""
        await start_watching(
            config=default_config,
            correlation_id=uuid4(),
            kafka_publisher=mock_kafka_publisher,
            observer_factory=polling_observer_factory,
        )
        await stop_watching(correlation_id=uuid4())
        assert RegistryWatchdogEffect.get_observer() is None

    @pytest.mark.asyncio
    async def test_stop_watching_no_observer_returns_stopped(self) -> None:
        """stop_watching() with no registered observer must return STOPPED (no-op)."""
        result = await stop_watching(correlation_id=uuid4())
        assert result.status == EnumWatchdogStatus.STOPPED


# =============================================================================
# _AsyncKafkaEventHandler — event dispatch
# =============================================================================


@pytest.mark.unit
class TestAsyncKafkaEventHandler:
    """_AsyncKafkaEventHandler must publish crawl-requested.v1 on file events."""

    @pytest.mark.asyncio
    async def test_dispatch_file_event_publishes_crawl_requested(
        self,
        default_config: ModelWatchdogConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        tmp_path: Any,
    ) -> None:
        """A file change event must publish to crawl-requested.v1."""
        loop = asyncio.get_running_loop()
        handler = _AsyncKafkaEventHandler(
            kafka_publisher=mock_kafka_publisher,
            config=default_config,
            loop=loop,
            correlation_id=uuid4(),
        )

        # Simulate a file event
        class FakeFileEvent:
            src_path = str(tmp_path / "CLAUDE.md")
            is_directory = False

        handler.dispatch(FakeFileEvent())

        # Allow the scheduled coroutine to complete
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert len(mock_kafka_publisher.published_messages) == 1
        msg = mock_kafka_publisher.published_messages[0]
        assert msg["topic"] == TOPIC_CRAWL_REQUESTED_V1
        assert msg["key"] == str(tmp_path / "CLAUDE.md")
        payload = msg["value"]
        assert isinstance(payload, dict)
        assert payload["crawl_type"] == "watchdog"
        assert payload["trigger_source"] == "filesystem_watch"
        assert payload["source_ref"] == str(tmp_path / "CLAUDE.md")

    @pytest.mark.asyncio
    async def test_dispatch_directory_event_is_skipped(
        self,
        default_config: ModelWatchdogConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        tmp_path: Any,
    ) -> None:
        """Directory change events must NOT publish to Kafka."""
        loop = asyncio.get_running_loop()
        handler = _AsyncKafkaEventHandler(
            kafka_publisher=mock_kafka_publisher,
            config=default_config,
            loop=loop,
            correlation_id=uuid4(),
        )

        class FakeDirEvent:
            src_path = str(tmp_path)
            is_directory = True

        handler.dispatch(FakeDirEvent())
        await asyncio.sleep(0)

        assert len(mock_kafka_publisher.published_messages) == 0

    @pytest.mark.asyncio
    async def test_dispatch_ignored_suffix_is_skipped(
        self,
        default_config: ModelWatchdogConfig,
        mock_kafka_publisher: MockKafkaPublisher,
        tmp_path: Any,
    ) -> None:
        """Files with ignored suffixes must NOT publish to Kafka."""
        loop = asyncio.get_running_loop()
        handler = _AsyncKafkaEventHandler(
            kafka_publisher=mock_kafka_publisher,
            config=default_config,
            loop=loop,
            correlation_id=uuid4(),
        )

        class FakeSwapEvent:
            src_path = str(tmp_path / ".CLAUDE.md.swp")
            is_directory = False

        handler.dispatch(FakeSwapEvent())
        await asyncio.sleep(0)

        assert len(mock_kafka_publisher.published_messages) == 0

    @pytest.mark.asyncio
    async def test_dispatch_empty_src_path_is_skipped(
        self,
        default_config: ModelWatchdogConfig,
        mock_kafka_publisher: MockKafkaPublisher,
    ) -> None:
        """Events with empty src_path must be silently skipped."""
        loop = asyncio.get_running_loop()
        handler = _AsyncKafkaEventHandler(
            kafka_publisher=mock_kafka_publisher,
            config=default_config,
            loop=loop,
            correlation_id=uuid4(),
        )

        class FakeEmptyEvent:
            src_path = ""
            is_directory = False

        handler.dispatch(FakeEmptyEvent())
        await asyncio.sleep(0)

        assert len(mock_kafka_publisher.published_messages) == 0


# =============================================================================
# ModelWatchdogConfig — validation
# =============================================================================


@pytest.mark.unit
class TestModelWatchdogConfig:
    """ModelWatchdogConfig must validate paths and filter ignored files."""

    def test_empty_watched_paths_raises_value_error(self) -> None:
        """Empty watched_paths must raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            ModelWatchdogConfig(watched_paths=())

    def test_relative_path_raises_value_error(self) -> None:
        """Relative paths in watched_paths must raise ValueError."""
        with pytest.raises(ValueError, match="absolute"):
            ModelWatchdogConfig(watched_paths=("relative/path",))

    def test_tilde_path_is_expanded(self) -> None:
        """Paths starting with ~ must be expanded to absolute paths."""
        config = ModelWatchdogConfig(watched_paths=("~/.claude",))
        assert all(p.startswith("/") for p in config.watched_paths)

    def test_is_ignored_swp_suffix(self, tmp_path: Any) -> None:
        """is_ignored() must return True for .swp files."""
        config = ModelWatchdogConfig(watched_paths=(str(tmp_path),))
        assert config.is_ignored(str(tmp_path / ".file.swp")) is True

    def test_is_ignored_tmp_suffix(self, tmp_path: Any) -> None:
        """is_ignored() must return True for .tmp files."""
        config = ModelWatchdogConfig(watched_paths=(str(tmp_path),))
        assert config.is_ignored(str(tmp_path / "work.tmp")) is True

    def test_is_ignored_tilde_suffix(self, tmp_path: Any) -> None:
        """is_ignored() must return True for files ending in ~."""
        config = ModelWatchdogConfig(watched_paths=(str(tmp_path),))
        assert config.is_ignored(str(tmp_path / "CLAUDE.md~")) is True

    def test_is_ignored_normal_file(self, tmp_path: Any) -> None:
        """is_ignored() must return False for normal .md files."""
        config = ModelWatchdogConfig(watched_paths=(str(tmp_path),))
        assert config.is_ignored(str(tmp_path / "CLAUDE.md")) is False

    def test_polling_interval_must_be_positive(self, tmp_path: Any) -> None:
        """polling_interval_seconds must be >= 1."""
        with pytest.raises(ValueError):
            ModelWatchdogConfig(
                watched_paths=(str(tmp_path),),
                polling_interval_seconds=0,
            )

    def test_default_crawl_scope(self, tmp_path: Any) -> None:
        """Default crawl_scope must match the design doc value."""
        config = ModelWatchdogConfig(watched_paths=(str(tmp_path),))
        assert config.crawl_scope == "omninode/shared/global-standards"
