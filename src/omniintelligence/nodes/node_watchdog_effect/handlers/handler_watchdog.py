# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
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
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

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

# Topic published by this handler.
#
# This is the BARE canonical topic string without the ``{env}.`` prefix.
# RuntimeHostProcess injects the environment prefix (e.g. ``dev.``, ``prod.``)
# at runtime for subscriptions declared in contract.yaml.  Direct publishes in
# handler code use this bare constant; the Kafka publisher wrapper resolves the
# full topic name (including env prefix) from its own configuration, consistent
# with the pattern used by TOPIC_ROUTING_FEEDBACK_PROCESSED in constants.py.
#
# Full runtime topic: ``{env}.onex.cmd.omnimemory.crawl-requested.v1``
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
        correlation_id: UUID,
    ) -> None:
        self._kafka_publisher = kafka_publisher
        self._config = config
        self._loop = loop
        self._correlation_id = correlation_id

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
                extra={
                    "file_path": src_path,
                    "correlation_id": str(self._correlation_id),
                },
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
                # Do NOT re-raise — the observer thread has no recovery path for
                # unexpected RuntimeErrors and re-raising would silently terminate
                # the observer thread without any structured error result or alerting.
                # Log at error level so the failure is visible.
                logger.error(
                    "Observer thread error (non-shutdown): %s",
                    exc,
                    exc_info=True,
                    extra={"correlation_id": str(self._correlation_id)},
                )
                coro.close()
                return
            coro.close()
            logger.debug(
                "Watchdog event dropped: event loop closed during shutdown",
                extra={
                    "file_path": src_path,
                    "correlation_id": str(self._correlation_id),
                },
            )

    async def _publish_crawl_requested(self, file_path: str) -> None:
        """Publish crawl-requested.v1 for a changed file path.

        Builds the payload and calls the async Kafka publisher.
        All exceptions are caught and logged to prevent crashing the task.

        Each emitted event carries a fresh correlation_id so that downstream
        consumers can trace individual ingestion flows independently.  The
        construction-time ``self._correlation_id`` is used only for
        handler-level logging (e.g., in ``dispatch()``), not for events.

        Args:
            file_path: Absolute path of the changed file.
        """
        # Fresh UUID per event — each file change starts its own trace span.
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
    correlation_id: UUID,
    kafka_publisher: ProtocolKafkaPublisher | None = None,
    observer_factory: Any = None,
) -> ModelWatchdogResult:
    """Start the OS-level filesystem observer for configured watched paths.

    Selects the best available observer (FSEvents → inotify → polling)
    and schedules recursive watches for all paths in ``config.watched_paths``.
    The event handler publishes ``crawl-requested.v1`` on file change.

    Args:
        config: Watchdog configuration (paths, polling interval, scope).
        correlation_id: Correlation ID threaded through all operations and
            emitted events for end-to-end distributed tracing.
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
        # Guard: prevent double-start — atomic check-then-act.
        #
        # claim_start_slot() atomically checks for a running observer *and* a
        # concurrent start-in-progress sentinel, then sets the sentinel under
        # a single lock acquisition.  This closes the race window that existed
        # when get_observer() and register_observer() were two separate lock
        # acquisitions: two concurrent asyncio tasks could both observe None
        # from get_observer() and then both proceed through factory() and
        # _schedule_watches() before either called register_observer().
        #
        # If claim_start_slot() returns False, either an observer is already
        # running or another concurrent start_watching() call holds the slot.
        # Return STARTED with the active observer's state so callers get a
        # well-defined result without silently corrupting state.
        if not RegistryWatchdogEffect.claim_start_slot():
            active_config = RegistryWatchdogEffect.get_config()
            active_watched_paths = (
                tuple(active_config.watched_paths)
                if active_config is not None
                else tuple(config.watched_paths)
            )
            logger.warning(
                "WatchdogEffect: start_watching() called but an observer is already "
                "running or starting — ignoring duplicate start request",
                extra={
                    "watched_paths": active_watched_paths,
                    "correlation_id": str(correlation_id),
                },
            )
            return ModelWatchdogResult(
                status=EnumWatchdogStatus.STARTED,
                observer_type=RegistryWatchdogEffect.get_observer_type(),
                watched_paths=active_watched_paths,
                correlation_id=correlation_id,
            )

        # Validate that all watched paths exist on disk before starting the observer.
        # watchdog raises OSError at observer.schedule() time for missing paths, which
        # is caught by the outer except and returned as ERROR.  An earlier explicit check
        # gives operators a clearer error message pointing to the specific missing path.
        #
        # Release the start slot before returning ERROR so subsequent calls are
        # not permanently blocked by the sentinel set in claim_start_slot().
        for watched_path in config.watched_paths:
            if not Path(watched_path).exists():
                missing_msg = f"watched path does not exist: {watched_path}"
                logger.error(
                    "WatchdogEffect: cannot start observer — %s",
                    missing_msg,
                    extra={
                        "watched_path": watched_path,
                        "correlation_id": str(correlation_id),
                    },
                )
                RegistryWatchdogEffect.release_start_slot()
                return ModelWatchdogResult(
                    status=EnumWatchdogStatus.ERROR,
                    error_message=missing_msg,
                    correlation_id=correlation_id,
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
                extra={
                    "watched_paths": config.watched_paths,
                    "correlation_id": str(correlation_id),
                },
            )

        if kafka_publisher is not None:
            # Get current event loop for thread-safe scheduling.
            # Only needed when kafka_publisher is present — _AsyncKafkaEventHandler
            # uses the loop to schedule coroutines from the observer thread.
            loop = asyncio.get_running_loop()

            # Build async event handler that bridges OS events to Kafka
            event_handler = _AsyncKafkaEventHandler(
                kafka_publisher=kafka_publisher,
                config=config,
                loop=loop,
                correlation_id=correlation_id,
            )

            # Schedule recursive watches for all configured paths.
            # _schedule_watches() wraps the handler in a FileSystemEventHandler
            # subclass as required by watchdog's schedule() API.  Mock observers
            # injected in tests accept any handler type, so this works for both
            # real and test contexts.
            _schedule_watches(observer, event_handler, config)

        # Register BEFORE starting the observer thread.
        # If observer.start() raises after the OS thread has begun, the observer
        # could be alive with no registry entry, making it untrackable (leaked
        # OS file-descriptor handles with no way to call stop/join).  By
        # registering first we ensure the observer is always reachable via
        # stop_watching() regardless of start() outcome.  If start() fails,
        # clean up the registry entry so the double-start guard is not
        # permanently tripped and callers can retry.
        RegistryWatchdogEffect.register_observer(observer, observer_type, config)

        try:
            # Start the observer thread (non-blocking — runs in background)
            observer.start()
        except Exception:
            # start() failed — undo the registry entry so the double-start
            # guard is not permanently tripped.  The observer thread did not
            # start successfully so there is nothing to stop/join.
            RegistryWatchdogEffect.clear()
            raise

        logger.info(
            "WatchdogEffect: observer started",
            extra={
                "observer_type": observer_type.value,
                "watched_paths": config.watched_paths,
                "correlation_id": str(correlation_id),
            },
        )

        return ModelWatchdogResult(
            status=EnumWatchdogStatus.STARTED,
            observer_type=observer_type,
            watched_paths=tuple(config.watched_paths),
            correlation_id=correlation_id,
        )

    except Exception as exc:
        # Release the start sentinel so subsequent start_watching() calls are
        # not permanently blocked.  If register_observer() already replaced the
        # sentinel with the real observer entry (i.e. observer.start() raised),
        # release_start_slot() is a no-op because the sentinel key is gone;
        # RegistryWatchdogEffect.clear() was already called by the inner
        # observer.start() failure handler in that case.
        RegistryWatchdogEffect.release_start_slot()
        sanitized = get_log_sanitizer().sanitize(str(exc))
        logger.exception(
            "WatchdogEffect: failed to start observer",
            extra={
                "error": sanitized,
                "watched_paths": config.watched_paths,
                "correlation_id": str(correlation_id),
            },
        )
        return ModelWatchdogResult(
            status=EnumWatchdogStatus.ERROR,
            error_message=sanitized,
            correlation_id=correlation_id,
        )


async def stop_watching(*, correlation_id: UUID) -> ModelWatchdogResult:
    """Gracefully stop the active filesystem observer.

    Retrieves the running observer from the module-level registry,
    calls ``observer.stop()`` and then ``observer.join(timeout=5.0)``
    offloaded to a thread via ``asyncio.to_thread`` so the event loop
    is not blocked if the OS observer thread takes time to exit cleanly.

    Args:
        correlation_id: Correlation ID threaded through all operations for
            end-to-end distributed tracing.

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
                "WatchdogEffect: stop_watching() called but no observer is registered",
                extra={"correlation_id": str(correlation_id)},
            )
            return ModelWatchdogResult(
                status=EnumWatchdogStatus.STOPPED,
                observer_type=None,
                correlation_id=correlation_id,
            )

        # Ensure the registry is always cleared even if observer.stop() raises.
        # Without this, a dead observer reference remains in the registry and
        # every subsequent start_watching() call is permanently blocked by the
        # double-start guard.
        try:
            observer.stop()
        finally:
            RegistryWatchdogEffect.clear()

        # Join with timeout offloaded to a thread so the event loop is not blocked.
        # Failures here are non-fatal — the registry has already been cleared above.
        # Log a warning if join times out or raises so operators are aware that
        # the OS observer thread may still be alive (resource leak risk).
        #
        # NOTE: threading.Thread.join(timeout) returns normally even when the
        # timeout expires with the thread still alive — it does NOT raise.
        # We must explicitly check observer.is_alive() after the join to detect
        # a timeout expiry and log the appropriate warning.
        try:
            await asyncio.to_thread(observer.join, 5.0)
        except Exception as join_exc:
            logger.warning(
                "WatchdogEffect: observer.join() did not complete cleanly — "
                "OS observer thread may still be alive",
                extra={
                    "error": get_log_sanitizer().sanitize(str(join_exc)),
                    "correlation_id": str(correlation_id),
                },
            )
        else:
            if observer.is_alive():
                logger.warning(
                    "WatchdogEffect: observer thread is still alive after join "
                    "timeout — OS file-descriptor handles may be leaked",
                    extra={"correlation_id": str(correlation_id)},
                )

        logger.info(
            "WatchdogEffect: observer stopped",
            extra={
                "observer_type": observer_type.value if observer_type else "unknown",
                "correlation_id": str(correlation_id),
            },
        )

        return ModelWatchdogResult(
            status=EnumWatchdogStatus.STOPPED,
            observer_type=observer_type,
            correlation_id=correlation_id,
        )

    except Exception as exc:
        sanitized = get_log_sanitizer().sanitize(str(exc))
        logger.exception(
            "WatchdogEffect: failed to stop observer",
            extra={"error": sanitized, "correlation_id": str(correlation_id)},
        )
        return ModelWatchdogResult(
            status=EnumWatchdogStatus.ERROR,
            error_message=sanitized,
            correlation_id=correlation_id,
        )


# =============================================================================
# Internal helpers
# =============================================================================


def _schedule_watches(
    observer: Any, event_handler: Any, config: ModelWatchdogConfig
) -> None:
    """Schedule recursive watches via watchdog's native schedule() API.

    Wraps the event handler in a ``FileSystemEventHandler`` subclass so
    watchdog's ``observer.schedule()`` API accepts it.  Mock observers
    injected in tests accept ``Any`` handler, so the wrapped handler
    passes through without issue.

    Args:
        observer: The watchdog BaseObserver instance (real or mock).
        event_handler: The event handler to attach to each path.
        config: Configuration containing watched paths.
    """
    from watchdog.events import FileSystemEventHandler

    # Wrap _AsyncKafkaEventHandler in a FileSystemEventHandler subclass
    # so watchdog's observer accepts it
    class _WatchdogCompatHandler(FileSystemEventHandler):
        def __init__(self, inner: _AsyncKafkaEventHandler) -> None:
            super().__init__()
            self._inner = inner

        def dispatch(self, event: Any) -> None:
            self._inner.dispatch(event)

    # One shared compat_handler wraps the single _AsyncKafkaEventHandler instance
    # and is reused for all watched paths. This is intentional: all paths share
    # the same async dispatch logic and Kafka publisher, so a single handler
    # instance is correct and avoids redundant object creation per path.
    compat_handler = _WatchdogCompatHandler(event_handler)

    for path in config.watched_paths:
        observer.schedule(compat_handler, path=path, recursive=True)


__all__ = [
    "TOPIC_CRAWL_REQUESTED_V1",
    "start_watching",
    "stop_watching",
]
