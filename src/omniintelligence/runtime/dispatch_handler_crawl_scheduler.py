# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Dispatch bridge handlers for the CrawlSchedulerEffect node.

This module provides bridge handlers that adapt between the MessageDispatchEngine
handler signature and the CrawlSchedulerEffect domain handlers.  It wires
two subscribed topics to their respective handler functions:

    1. ``onex.cmd.omnimemory.crawl-requested.v1``
       → ``handle_crawl_requested()`` — manual/external crawl trigger
    2. ``onex.evt.omnimemory.document-indexed.v1``
       → ``handle_document_indexed()`` — debounce reset on crawl completion

Design Decisions:
    - Both handlers read from ``RegistryCrawlSchedulerEffect`` for their
      Kafka publisher, config, and debounce state dependencies.
    - ``handle_document_indexed`` is synchronous at the domain level; the
      dispatch bridge wraps it in an async closure for engine compatibility.
    - Payload parsing follows the same defensive pattern as other dispatch
      bridge handlers: missing/malformed payloads raise ValueError so the
      dispatch engine can route to DLQ without infinite NACK loops.
    - The crawl-tick publish topic is determined by
      ``TOPIC_CRAWL_TICK_V1`` in ``handler_crawl_scheduler.py``.  The
      dispatch bridge does not need to pass a publish_topic explicitly
      because the handler itself writes to that constant topic.

Related:
    - OMN-2384: CrawlSchedulerEffect implementation
    - dispatch_handlers.py: pattern established for other effect nodes
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)

# =============================================================================
# Dispatch alias constants for CrawlScheduler topics
# =============================================================================

DISPATCH_ALIAS_CRAWL_REQUESTED = "onex.commands.omnimemory.crawl-requested.v1"
"""Dispatch-compatible alias for crawl-requested canonical topic."""

DISPATCH_ALIAS_DOCUMENT_INDEXED = "onex.events.omnimemory.document-indexed.v1"
"""Dispatch-compatible alias for document-indexed canonical topic."""


# =============================================================================
# Bridge Handler: crawl-requested.v1
# =============================================================================


def create_crawl_requested_dispatch_handler(
    *,
    correlation_id: UUID | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch engine handler for crawl-requested commands.

    Reads the Kafka publisher, debounce state, and config from
    ``RegistryCrawlSchedulerEffect`` at call time (not at factory creation
    time) so that tests can inject mocks via the registry before dispatching.

    Args:
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> handle_crawl_requested()."""
        from omniintelligence.nodes.node_crawl_scheduler_effect.handlers.handler_crawl_scheduler import (
            handle_crawl_requested,
        )
        from omniintelligence.nodes.node_crawl_scheduler_effect.models import (
            ModelCrawlRequestedEvent,
        )
        from omniintelligence.nodes.node_crawl_scheduler_effect.registry.registry_crawl_scheduler_effect import (
            RegistryCrawlSchedulerEffect,
        )

        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        if not isinstance(payload, dict):
            msg = (
                f"Unexpected payload type {type(payload).__name__} "
                f"for crawl-requested (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        try:
            event = ModelCrawlRequestedEvent(**payload)
        except Exception as e:
            sanitized = get_log_sanitizer().sanitize(str(e))
            msg = (
                f"Failed to parse payload as ModelCrawlRequestedEvent: "
                f"{sanitized} (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg) from e

        kafka_publisher = RegistryCrawlSchedulerEffect.get_publisher()
        debounce_state = RegistryCrawlSchedulerEffect.get_debounce_state()
        config = RegistryCrawlSchedulerEffect.get_config()

        logger.info(
            "Dispatching crawl-requested via MessageDispatchEngine "
            "(source_ref=%s, crawl_type=%s, trigger_source=%s, "
            "correlation_id=%s)",
            get_log_sanitizer().sanitize(event.source_ref),
            event.crawl_type.value,
            event.trigger_source.value,
            ctx_correlation_id,
        )

        result = await handle_crawl_requested(
            event=event,
            debounce_state=debounce_state,
            config=config,
            kafka_publisher=kafka_publisher,
        )

        logger.info(
            "Crawl-requested processed via dispatch engine "
            "(status=%s, source_ref=%s, correlation_id=%s)",
            result.status.value,
            get_log_sanitizer().sanitize(result.source_ref),
            ctx_correlation_id,
        )

        return "ok"

    return _handle


# =============================================================================
# Bridge Handler: document-indexed.v1
# =============================================================================


def create_document_indexed_dispatch_handler(
    *,
    correlation_id: UUID | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch engine handler for document-indexed events.

    Resets the per-source debounce window after a successful crawl
    completion.  Reads the debounce state from
    ``RegistryCrawlSchedulerEffect`` at call time.

    Args:
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> handle_document_indexed()."""
        from omniintelligence.nodes.node_crawl_scheduler_effect.handlers.handler_crawl_scheduler import (
            handle_document_indexed,
        )
        from omniintelligence.nodes.node_crawl_scheduler_effect.models import (
            CrawlerType,
        )
        from omniintelligence.nodes.node_crawl_scheduler_effect.registry.registry_crawl_scheduler_effect import (
            RegistryCrawlSchedulerEffect,
        )

        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        if not isinstance(payload, dict):
            msg = (
                f"Unexpected payload type {type(payload).__name__} "
                f"for document-indexed (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        # Extract required fields
        raw_source_ref = payload.get("source_ref")
        if raw_source_ref is None:
            msg = (
                f"document-indexed payload missing required field 'source_ref' "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)
        source_ref = str(raw_source_ref)

        raw_crawler_type = payload.get("crawler_type")
        if raw_crawler_type is None:
            msg = (
                f"document-indexed payload missing required field 'crawler_type' "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        try:
            crawler_type = CrawlerType(raw_crawler_type)
        except ValueError as e:
            msg = (
                f"Invalid crawler_type value {raw_crawler_type!r} "
                f"for document-indexed (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg) from e

        debounce_state = RegistryCrawlSchedulerEffect.get_debounce_state()

        logger.info(
            "Dispatching document-indexed via MessageDispatchEngine "
            "(source_ref=%s, crawler_type=%s, correlation_id=%s)",
            get_log_sanitizer().sanitize(source_ref),
            crawler_type.value,
            ctx_correlation_id,
        )

        cleared = handle_document_indexed(
            source_ref=source_ref,
            crawler_type=crawler_type,
            debounce_state=debounce_state,
        )

        logger.info(
            "Document-indexed processed via dispatch engine "
            "(cleared=%s, source_ref=%s, correlation_id=%s)",
            cleared,
            get_log_sanitizer().sanitize(source_ref),
            ctx_correlation_id,
        )

        return "ok"

    return _handle


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "DISPATCH_ALIAS_CRAWL_REQUESTED",
    "DISPATCH_ALIAS_DOCUMENT_INDEXED",
    "create_crawl_requested_dispatch_handler",
    "create_document_indexed_dispatch_handler",
]
