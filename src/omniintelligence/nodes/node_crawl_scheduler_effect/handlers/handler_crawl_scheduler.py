# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handler classes for CrawlSchedulerEffect.

Three handler classes for the crawl scheduler, one per operation:

1. ``HandlerCrawlTick``
   Called by RuntimeScheduler on a periodic tick.  Iterates over configured
   crawl sources and emits crawl-tick.v1 commands for any source whose
   debounce window has expired.

2. ``HandlerCrawlRequested``
   Called when a manual/external trigger arrives via crawl-requested.v1.
   Applies the same per-source debounce guard before emitting.

3. ``HandlerDocumentIndexed``
   Called when a document-indexed.v1 event is received.  Resets the debounce
   window for the crawled (source_ref, crawler_type) so the next trigger is
   not throttled.

Debounce Guard:
---------------
Both trigger handlers use the same ``DebounceStateManager`` singleton.
The guard prevents phantom duplication that occurs when git hook + watchdog +
scheduled tick all fire for the same source within seconds.

Design: See omni_save/design/DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §4

Handler Contract:
-----------------
ALL exceptions are caught and returned as structured ERROR results.
These handlers never raise — unexpected errors produce a result with
status=EnumCrawlSchedulerStatus.ERROR.

Kafka Graceful Degradation:
---------------------------
If kafka_publisher is None, the handler logs a warning but still records the
debounce entry.  This ensures that when Kafka is temporarily unavailable,
subsequent triggers within the window are still dropped, preventing a burst
when Kafka recovers.  The result status is ERROR (not EMITTED) when the
publisher is absent.

Reference: OMN-2384
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from omniintelligence.constants import TOPIC_CRAWL_TICK_V1
from omniintelligence.nodes.node_crawl_scheduler_effect.handlers.debounce_state import (
    DebounceStateManager,
)
from omniintelligence.nodes.node_crawl_scheduler_effect.models import (
    CrawlerType,
    EnumCrawlSchedulerStatus,
    EnumTriggerSource,
    ModelCrawlRequestedEvent,
    ModelCrawlSchedulerConfig,
    ModelCrawlSchedulerResult,
    ModelCrawlTickCommand,
    ModelCrawlTickRequest,
    ModelDocumentIndexedRequest,
)
from omniintelligence.protocols import ProtocolKafkaPublisher
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Default clock for the crawl handlers."""
    return datetime.now(UTC)


class HandlerCrawlTick:
    """Emit a crawl-tick.v1 command for a scheduled trigger.

    Called by the RuntimeScheduler tick for each configured crawl source.
    Applies the per-source debounce guard before emitting.

    Args:
        debounce_state: Active debounce state manager (injected).
        config: Scheduler configuration with debounce windows.
        kafka_publisher: Optional Kafka publisher.  When None, the trigger
            is recorded in debounce state but no event is published.
    """

    def __init__(
        self,
        *,
        debounce_state: DebounceStateManager,
        config: ModelCrawlSchedulerConfig,
        kafka_publisher: ProtocolKafkaPublisher | None = None,
    ) -> None:
        self._debounce_state = debounce_state
        self._config = config
        self._kafka_publisher = kafka_publisher

    async def handle(self, request: ModelCrawlTickRequest) -> ModelCrawlSchedulerResult:
        """Process one scheduled tick.

        Args:
            request: Crawl type, scope, source reference and optional
                injected ``now`` (defaults to ``datetime.now(UTC)``).

        Returns:
            ModelCrawlSchedulerResult with status EMITTED, DEBOUNCED, or ERROR.
        """
        current_time = request.now or datetime.now(UTC)

        try:
            return await _process_trigger(
                crawl_type=request.crawl_type,
                crawl_scope=request.crawl_scope,
                source_ref=request.source_ref,
                trigger_source=EnumTriggerSource.SCHEDULED,
                debounce_state=self._debounce_state,
                config=self._config,
                kafka_publisher=self._kafka_publisher,
                now=current_time,
            )
        except Exception as exc:
            sanitized = get_log_sanitizer().sanitize(str(exc))
            logger.exception(
                "Unhandled exception in schedule_crawl_tick",
                extra={
                    "source_ref": request.source_ref,
                    "crawl_type": request.crawl_type.value,
                    "error": sanitized,
                },
            )
            return ModelCrawlSchedulerResult(
                status=EnumCrawlSchedulerStatus.ERROR,
                crawl_type=request.crawl_type,
                source_ref=request.source_ref,
                crawl_scope=request.crawl_scope,
                trigger_source=EnumTriggerSource.SCHEDULED,
                correlation_id=uuid4(),
                processed_at=current_time,
                error_message=sanitized,
            )


class HandlerCrawlRequested:
    """Process a manual/external crawl trigger from crawl-requested.v1.

    Applies the same per-source debounce guard as the scheduled tick handler.
    This ensures that git hook + watchdog + manual triggers for the same source
    do not produce duplicate crawl-tick events.

    Args:
        debounce_state: Active debounce state manager (injected).
        config: Scheduler configuration with debounce windows.
        kafka_publisher: Optional Kafka publisher.
        clock: Returns the current UTC datetime.  Defaults to
            ``datetime.now(UTC)``.  Injected for testability.
    """

    def __init__(
        self,
        debounce_state: DebounceStateManager,
        config: ModelCrawlSchedulerConfig,
        kafka_publisher: ProtocolKafkaPublisher | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._debounce_state = debounce_state
        self._config = config
        self._kafka_publisher = kafka_publisher
        self._clock = clock

    async def handle(
        self, request: ModelCrawlRequestedEvent
    ) -> ModelCrawlSchedulerResult:
        """Process one crawl-requested event.

        Args:
            request: The crawl-requested event received from Kafka.

        Returns:
            ModelCrawlSchedulerResult with status EMITTED, DEBOUNCED, or ERROR.
        """
        current_time = self._clock()

        try:
            return await _process_trigger(
                crawl_type=request.crawl_type,
                crawl_scope=request.crawl_scope,
                source_ref=request.source_ref,
                trigger_source=request.trigger_source,
                debounce_state=self._debounce_state,
                config=self._config,
                kafka_publisher=self._kafka_publisher,
                now=current_time,
                correlation_id_hint=request.correlation_id,
            )
        except Exception as exc:
            sanitized = get_log_sanitizer().sanitize(str(exc))
            logger.exception(
                "Unhandled exception in handle_crawl_requested",
                extra={
                    "source_ref": request.source_ref,
                    "crawl_type": request.crawl_type.value,
                    "correlation_id": str(request.correlation_id),
                    "error": sanitized,
                },
            )
            return ModelCrawlSchedulerResult(
                status=EnumCrawlSchedulerStatus.ERROR,
                crawl_type=request.crawl_type,
                source_ref=request.source_ref,
                crawl_scope=request.crawl_scope,
                trigger_source=request.trigger_source,
                correlation_id=request.correlation_id,
                processed_at=current_time,
                error_message=sanitized,
            )


class HandlerDocumentIndexed:
    """Reset the debounce window after a successful crawl completion.

    Called when a ``document-indexed.v1`` event is received.  Clears the
    debounce entry for the ``(source_ref, crawler_type)`` key so the next
    trigger is not throttled.

    Args:
        debounce_state: Active debounce state manager (injected).
    """

    def __init__(self, *, debounce_state: DebounceStateManager) -> None:
        self._debounce_state = debounce_state

    def handle(self, request: ModelDocumentIndexedRequest) -> bool:
        """Clear the debounce entry for the indexed source.

        Args:
            request: Source reference and crawler type from the indexed event.

        Returns:
            True if a debounce entry was cleared; False if no entry existed
            (e.g., process restarted since the crawl was triggered).
        """
        cleared = self._debounce_state.clear_debounce(
            source_ref=request.source_ref,
            crawler_type=request.crawler_type,
        )

        if cleared:
            logger.debug(
                "Debounce window cleared after successful crawl",
                extra={
                    "source_ref": request.source_ref,
                    "crawler_type": request.crawler_type.value,
                },
            )
        else:
            logger.debug(
                "No debounce entry to clear (already cleared or process restarted)",
                extra={
                    "source_ref": request.source_ref,
                    "crawler_type": request.crawler_type.value,
                },
            )

        return cleared


# =============================================================================
# Internal helpers
# =============================================================================


# =============================================================================
# Internal helpers
# =============================================================================


async def _process_trigger(
    *,
    crawl_type: CrawlerType,
    crawl_scope: str,
    source_ref: str,
    trigger_source: EnumTriggerSource,
    debounce_state: DebounceStateManager,
    config: ModelCrawlSchedulerConfig,
    kafka_publisher: ProtocolKafkaPublisher | None,
    now: datetime,
    correlation_id_hint: UUID | None = None,
) -> ModelCrawlSchedulerResult:
    """Core trigger processing logic shared by both handler entry points.

    Steps:
    1. Check debounce guard.  Drop silently if within window.
    2. Record debounce entry (before Kafka publish to prevent race).
    3. Guard: return ERROR if kafka_publisher is None.
    4. Build ModelCrawlTickCommand.
    5. Publish to crawl-tick.v1.
    6. Return structured result.

    Args:
        correlation_id_hint: Optional UUID to use as correlation_id.
            When None, a new UUID is generated.
    """
    # Resolve correlation_id
    correlation_id: UUID = (
        correlation_id_hint if correlation_id_hint is not None else uuid4()
    )

    # Step 1: Check debounce guard
    window_seconds = config.get_window_seconds(crawl_type)

    if not debounce_state.is_allowed(
        source_ref=source_ref,
        crawler_type=crawl_type,
        window_seconds=window_seconds,
        now=now,
    ):
        logger.debug(
            "Crawl trigger debounced — dropping silently",
            extra={
                "source_ref": source_ref,
                "crawl_type": crawl_type.value,
                "trigger_source": trigger_source.value,
                "window_seconds": window_seconds,
                "correlation_id": str(correlation_id),
            },
        )
        return ModelCrawlSchedulerResult(
            status=EnumCrawlSchedulerStatus.DEBOUNCED,
            crawl_type=crawl_type,
            source_ref=source_ref,
            crawl_scope=crawl_scope,
            trigger_source=trigger_source,
            correlation_id=correlation_id,
            processed_at=now,
            debounce_window_seconds=window_seconds,
        )

    # Step 2: Record debounce entry BEFORE Kafka publish.
    # If publish fails, the debounce entry is still set.  This is intentional:
    # it prevents a burst of retries from all passing the guard simultaneously.
    debounce_state.record_trigger(
        source_ref=source_ref,
        crawler_type=crawl_type,
        now=now,
    )

    # Step 3: Guard — publisher must be available before building the command
    if kafka_publisher is None:
        logger.warning(
            "Kafka publisher not available — crawl-tick emitted to debounce state only",
            extra={
                "source_ref": source_ref,
                "crawl_type": crawl_type.value,
                "correlation_id": str(correlation_id),
            },
        )
        return ModelCrawlSchedulerResult(
            status=EnumCrawlSchedulerStatus.ERROR,
            crawl_type=crawl_type,
            source_ref=source_ref,
            crawl_scope=crawl_scope,
            trigger_source=trigger_source,
            correlation_id=correlation_id,
            processed_at=now,
            error_message="kafka_publisher not configured",
        )

    # Step 4: Build crawl-tick command
    command = ModelCrawlTickCommand(
        crawl_type=crawl_type,
        crawl_scope=crawl_scope,
        source_ref=source_ref,
        correlation_id=correlation_id,
        triggered_at_utc=now.isoformat(),
        trigger_source=trigger_source,
    )

    # Step 5: Publish to Kafka
    await kafka_publisher.publish(
        topic=TOPIC_CRAWL_TICK_V1,
        key=source_ref,
        value=command.model_dump(mode="json"),
    )

    logger.info(
        "Crawl tick emitted",
        extra={
            "source_ref": source_ref,
            "crawl_type": crawl_type.value,
            "crawl_scope": crawl_scope,
            "trigger_source": trigger_source.value,
            "correlation_id": str(correlation_id),
            "topic": TOPIC_CRAWL_TICK_V1,
        },
    )

    return ModelCrawlSchedulerResult(
        status=EnumCrawlSchedulerStatus.EMITTED,
        crawl_type=crawl_type,
        source_ref=source_ref,
        crawl_scope=crawl_scope,
        trigger_source=trigger_source,
        correlation_id=correlation_id,
        processed_at=now,
    )


__all__ = [
    "TOPIC_CRAWL_TICK_V1",
    "HandlerCrawlRequested",
    "HandlerCrawlTick",
    "HandlerDocumentIndexed",
]
