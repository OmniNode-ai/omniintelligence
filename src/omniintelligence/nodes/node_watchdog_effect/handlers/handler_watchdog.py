# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler functions for WatchdogEffect.

This module implements the two handler entry points for the filesystem watcher:

1. ``start_watching()``
   Starts the OS-level filesystem observer (FSEvents/inotify/polling) for
   all configured watched paths.  Registers an event handler that publishes
   ``{env}.onex.cmd.omnimemory.crawl-requested.v1`` on file change.

2. ``stop_watching()``
   Gracefully stops the active observer and clears module-level state.

Design: omni_save/design/DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §4

Handler Contract:
-----------------
ALL exceptions are caught and returned as structured ERROR results.
These functions never raise — unexpected errors produce a result with
status=EnumWatchdogStatus.ERROR.

Kafka Non-Blocking Pattern:
---------------------------
The watchdog event handler runs in a background thread (OS observer thread).
It schedules a coroutine on the asyncio event loop via
``loop.call_soon_threadsafe(loop.create_task, coro)``.  This ensures:
  - The observer thread is never blocked by Kafka I/O.
  - The Kafka publish is fully async on the main event loop.
  - No synchronous/blocking awaits in the observer thread.

Deduplication:
--------------
WatchdogEffect does NOT implement its own debounce.  It emits
``crawl-requested.v1`` with ``trigger_source=FILESYSTEM_WATCH`` and relies
on the per-source debounce guard in ``CrawlSchedulerEffect`` (30-second
window) to prevent phantom duplication from rapid saves.

Reference: OMN-2386
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from omniintelligence.nodes.node_watchdog_effect.models.enum_watchdog_status import (
    EnumWatchdogStatus,
)
from omniintelligence.nodes.node_watchdog_effect.models.model_watchdog_config import (
    ModelWatchdogConfig,
)
from omniintelligence.nodes.node_watchdog_effect.models.model_watchdog_result import (
    ModelWatchdogResult,
)
from omniintelligence.protocols import ProtocolKafkaPublisher
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)

# Topic published by this handler (bare, without {env} prefix).
# RuntimeHostProcess injects the environment prefix at runtime.
TOPIC_CRAWL_REQUESTED_V1: str = "onex.cmd.omnimemory.crawl-requested.v1"

# CrawlerType value used in the emitted event payload.
# WatchdogEffect triggers are routed as WATCHDOG-type crawl requests.
CRAWLER_TYPE_WATCHDOG: str = "watchdog"

# TriggerSource value used in the emitted event payload.
TRIGGER_SOURCE_FILESYSTEM_WATCH: str = "filesystem_watch"


class _AsyncKafkaEventHandler:
    """Watchdog event handler that bridges OS events to async Kafka publishes.

    This handler is registered with the watchdog observer and runs in the
    OS observer thread (not the asyncio event loop thread).  All Kafka
    publishes are scheduled on the event loop via
    ``loop.call_soon_threadsafe(loop.create_task, coro)`` so the observer
    thread is never blocked.

    Args:
        kafka_publisher: Kafka publisher for crawl-requested.v1.
        config: Watchdog configuration (watched paths, ignored suffixes, scope).
        loop: The asyncio event loop on which to schedule publishes.
    """

    def __init__(
        self,
        kafka_publisher: ProtocolKafkaPublisher,
        config: ModelWatchdogConfig,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._kafka_publisher = kafka_publisher
        self._config = config
        self._loop = loop

    def dispatch(self, event: Any) -> None:
        """Dispatch a watchdog filesystem event.

        Called by the watchdog observer thread on every filesystem event.
        Filters ignored files and schedules async Kafka publish.

        Args:
            event: A watchdog FileSystemEvent (FileCreatedEvent,
                FileModifiedEvent, FileDeletedEvent, etc.).
        """
        # Directory events are not interesting — only file events
        if getattr(event, "is_directory", False):
            return

        src_path: str = getattr(event, "src_path", "")
        if not src_path:
            return

        # Filter editor swap files and other ignored patterns
        if self._config.is_ignored(src_path):
            logger.debug(
                "Watchdog event skipped (ignored suffix)",
                extra={"file_path": src_path},
            )
            return

        # Schedule async publish on the event loop (non-blocking).
        # Guard against RuntimeError("Event loop is closed") — the OS observer
        # thread may fire one final event after loop shutdown begins.  This is
        # expected at teardown and safe to discard.
        # coro.close() is required to avoid RuntimeWarning about unawaited coroutine.
        coro = self._publish_crawl_requested(src_path)
        try:
            self._loop.call_soon_threadsafe(self._loop.create_task, coro)
        except RuntimeError as exc:
            if "event loop is closed" not in str(exc).lower():
                # Re-raise unexpected RuntimeErrors (not the known shutdown race).
                raise
            coro.close()
            logger.debug(
                "Watchdog event dropped: event loop closed during shutdown",
                extra={"file_path": src_path},
            )

    async def _publish_crawl_requested(self, file_path: str) -> None:
        """Publish crawl-requested.v1 for a changed file path.

        Builds the payload and calls the async Kafka publisher.
        All exceptions are caught and logged to prevent crashing the task.

        Args:
            file_path: Absolute path of the changed file.
        """
        correlation_id = uuid4()

        try:
            now_utc = datetime.now(UTC)

            payload: dict[str, object] = {
                "crawl_type": CRAWLER_TYPE_WATCHDOG,
                "crawl_scope": self._config.crawl_scope,
                "source_ref": file_path,
                "correlation_id": str(correlation_id),
                "requested_at_utc": now_utc.isoformat(),
                "trigger_source": TRIGGER_SOURCE_FILESYSTEM_WATCH,
            }

            await self._kafka_publisher.publish(
                topic=TOPIC_CRAWL_REQUESTED_V1,
                key=file_path,
                value=payload,
            )

            logger.info(
                "Watchdog: crawl-requested.v1 emitted",
                extra={
                    "file_path": file_path,
                    "correlation_id": str(correlation_id),
                    "topic": TOPIC_CRAWL_REQUESTED_V1,
                    "trigger_source": TRIGGER_SOURCE_FILESYSTEM_WATCH,
                },
            )
        except Exception as exc:
            sanitized = get_log_sanitizer().sanitize(str(exc))
            logger.exception(
                "Watchdog: failed to publish crawl-requested.v1",
                extra={
                    "file_path": file_path,
                    "correlation_id": str(correlation_id),
                    "error": sanitized,
                },
            )


async def start_watching(
    *,
    config: ModelWatchdogConfig,
    kafka_publisher: ProtocolKafkaPublisher | None = None,
    observer_factory: Any = None,
) -> ModelWatchdogResult:
    """Start the OS-level filesystem observer for configured watched paths.

    Selects the best available observer (FSEvents → inotify → polling)
    and schedules recursive watches for all paths in ``config.watched_paths``.
    The event handler publishes ``crawl-requested.v1`` on file change.

    Args:
        config: Watchdog configuration (paths, polling interval, scope).
        kafka_publisher: Kafka publisher for crawl-requested.v1.  When None,
            the observer is started but no Kafka events are published.
        observer_factory: Optional callable that returns
            ``(observer, EnumWatchdogObserverType)``.  Defaults to
            ``create_observer()`` from observer_factory module.  Injected for
            testing to avoid real OS watchers.

    Returns:
        ModelWatchdogResult with status STARTED or ERROR.
    """
    from omniintelligence.nodes.node_watchdog_effect.handlers.observer_factory import (
        create_observer,
    )
    from omniintelligence.nodes.node_watchdog_effect.registry.registry_watchdog_effect import (
        RegistryWatchdogEffect,
    )

    try:
        # Guard: prevent double-start.
        # If an observer is already registered the previous call to
        # start_watching() already owns it.  Overwriting the registry entry
        # would make the first observer untrackable — it keeps running forever,
        # leaking OS file-descriptor handles.  Return early with STARTED so
        # callers get a well-defined result without silently corrupting state.
        existing_observer = RegistryWatchdogEffect.get_observer()
        if existing_observer is not None:
            logger.warning(
                "WatchdogEffect: start_watching() called but an observer is already "
                "running — ignoring duplicate start request",
                extra={"watched_paths": config.watched_paths},
            )
            return ModelWatchdogResult(
                status=EnumWatchdogStatus.STARTED,
                observer_type=RegistryWatchdogEffect.get_observer_type(),
                watched_paths=tuple(config.watched_paths),
            )

        # Resolve observer factory
        factory = observer_factory if observer_factory is not None else create_observer

        # Create observer (platform-appropriate).
        # Pass config to the default factory so polling_interval_seconds is
        # honoured; injected test factories take no arguments.
        # Caller contract: injected observer_factory must be a zero-argument
        # callable — factory() — returning (observer, EnumWatchdogObserverType).
        if observer_factory is not None:
            observer, observer_type = factory()
        else:
            observer, observer_type = factory(config=config)

        # kafka_publisher is None — event delivery is permanently disabled.
        #
        # When kafka_publisher is None the observer starts with no event
        # handlers attached and runs idle.  crawl-requested.v1 events will
        # NEVER be emitted.  Runtime re-wiring is NOT supported: watchdog
        # handler lists are fixed at observer.schedule() time and cannot be
        # updated while the observer thread is alive.  To enable event
        # delivery, call stop_watching() then start_watching() again with a
        # valid kafka_publisher.
        if kafka_publisher is None:
            logger.warning(
                "WatchdogEffect: kafka_publisher is None — observer will run "
                "idle with no event handlers; crawl-requested.v1 events will "
                "never be emitted (runtime re-wiring not supported; restart "
                "observer with a valid kafka_publisher to enable delivery)",
                extra={"watched_paths": config.watched_paths},
            )

        # Get current event loop for thread-safe scheduling
        loop = asyncio.get_running_loop()

        if kafka_publisher is not None:
            # Build async event handler that bridges OS events to Kafka
            event_handler = _AsyncKafkaEventHandler(
                kafka_publisher=kafka_publisher,
                config=config,
                loop=loop,
            )

            # Schedule recursive watches for all configured paths.
            # WHY this import-guard pattern: we import BaseObserver solely to
            # detect whether the real watchdog package is installed at runtime.
            # When watchdog IS installed the observer is a real BaseObserver
            # subclass and _schedule_watches() wraps the handler in the
            # FileSystemEventHandler subclass that watchdog's schedule() API
            # requires.  When watchdog is NOT installed (unit tests inject a
            # MockObserver) the ImportError branch falls through to
            # _schedule_watches_compat(), which calls observer.schedule()
            # directly without the FileSystemEventHandler wrapper — the mock
            # accepts any handler object.  This lets us distinguish injected
            # mock observers from real watchdog observers at scheduling time
            # without adding an isinstance() check on the observer itself.
            try:
                from watchdog.observers.api import (
                    BaseObserver as _BaseObserver,  # noqa: F401
                )

                _schedule_watches(observer, event_handler, config)
            except ImportError:
                # watchdog not installed — schedule_watches won't work
                # This branch is only hit when a mock observer is injected
                _schedule_watches_compat(observer, event_handler, config)

        # Start the observer thread (non-blocking — runs in background)
        observer.start()

        # Register in module-level registry for stop_watching()
        RegistryWatchdogEffect.register_observer(observer, observer_type)

        logger.info(
            "WatchdogEffect: observer started",
            extra={
                "observer_type": observer_type.value,
                "watched_paths": config.watched_paths,
            },
        )

        return ModelWatchdogResult(
            status=EnumWatchdogStatus.STARTED,
            observer_type=observer_type,
            watched_paths=tuple(config.watched_paths),
        )

    except Exception as exc:
        sanitized = get_log_sanitizer().sanitize(str(exc))
        logger.exception(
            "WatchdogEffect: failed to start observer",
            extra={"error": sanitized, "watched_paths": config.watched_paths},
        )
        return ModelWatchdogResult(
            status=EnumWatchdogStatus.ERROR,
            error_message=sanitized,
        )


async def stop_watching() -> ModelWatchdogResult:
    """Gracefully stop the active filesystem observer.

    Retrieves the running observer from the module-level registry,
    calls ``observer.stop()`` and then ``observer.join(timeout=5.0)``
    offloaded to a thread via ``asyncio.to_thread`` so the event loop
    is not blocked if the OS observer thread takes time to exit cleanly.

    Returns:
        ModelWatchdogResult with status STOPPED or ERROR.
    """
    from omniintelligence.nodes.node_watchdog_effect.registry.registry_watchdog_effect import (
        RegistryWatchdogEffect,
    )

    try:
        observer = RegistryWatchdogEffect.get_observer()
        observer_type = RegistryWatchdogEffect.get_observer_type()

        if observer is None:
            logger.warning(
                "WatchdogEffect: stop_watching() called but no observer is registered"
            )
            return ModelWatchdogResult(
                status=EnumWatchdogStatus.STOPPED,
                observer_type=None,
            )

        observer.stop()
        try:
            await asyncio.to_thread(observer.join, 5.0)
        finally:
            # Always clear the registry so the double-start guard doesn't
            # permanently block re-starts if join() raises or times out.
            RegistryWatchdogEffect.clear()

        logger.info(
            "WatchdogEffect: observer stopped",
            extra={
                "observer_type": observer_type.value if observer_type else "unknown"
            },
        )

        return ModelWatchdogResult(
            status=EnumWatchdogStatus.STOPPED,
            observer_type=observer_type,
        )

    except Exception as exc:
        sanitized = get_log_sanitizer().sanitize(str(exc))
        logger.exception(
            "WatchdogEffect: failed to stop observer",
            extra={"error": sanitized},
        )
        return ModelWatchdogResult(
            status=EnumWatchdogStatus.ERROR,
            error_message=sanitized,
        )


# =============================================================================
# Internal helpers
# =============================================================================


def _schedule_watches(
    observer: Any, event_handler: Any, config: ModelWatchdogConfig
) -> None:
    """Schedule recursive watches via watchdog's native schedule() API.

    Args:
        observer: The watchdog BaseObserver instance.
        event_handler: The event handler to attach to each path.
        config: Configuration containing watched paths.
    """
    try:
        from watchdog.events import FileSystemEventHandler

        # Wrap _AsyncKafkaEventHandler in a FileSystemEventHandler subclass
        # so watchdog's observer accepts it
        class _WatchdogCompatHandler(FileSystemEventHandler):
            def __init__(self, inner: _AsyncKafkaEventHandler) -> None:
                super().__init__()
                self._inner = inner

            def dispatch(self, event: Any) -> None:
                self._inner.dispatch(event)

        compat_handler = _WatchdogCompatHandler(event_handler)

        for path in config.watched_paths:
            observer.schedule(compat_handler, path=path, recursive=True)

    except ImportError:
        # watchdog not available — only reachable with mocked observer in tests
        _schedule_watches_compat(observer, event_handler, config)


def _schedule_watches_compat(
    observer: Any, event_handler: Any, config: ModelWatchdogConfig
) -> None:
    """Compatibility schedule helper for mocked observers.

    Calls ``observer.schedule(handler, path, recursive=True)`` for each
    watched path.  This signature matches both real watchdog observers and
    the mock observer used in unit tests.

    Args:
        observer: Observer instance (real or mock).
        event_handler: Event handler instance.
        config: Configuration containing watched paths.
    """
    for path in config.watched_paths:
        observer.schedule(event_handler, path=path, recursive=True)


__all__ = [
    "TOPIC_CRAWL_REQUESTED_V1",
    "start_watching",
    "stop_watching",
]
