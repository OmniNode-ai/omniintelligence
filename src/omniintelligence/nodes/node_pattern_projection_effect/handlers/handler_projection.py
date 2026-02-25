# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handler functions for pattern projection snapshot publishing.

This module implements the projection publish logic: querying all
validated/provisional patterns and publishing a full materialized snapshot
to the pattern-projection Kafka topic.

Design Principles:
    - Fire-and-forget Kafka emission: failures are logged but never propagated.
      The handler always returns a result; the snapshot is best-effort.
    - correlation_id threaded from the triggering lifecycle event through to
      the snapshot payload for end-to-end tracing.
    - snapshot_at is injected by the caller (no datetime.now() in model).
    - No blocking on Kafka — await producer.publish() with non-blocking
      protocol semantics; exceptions caught and logged.
    - Protocol-based dependency injection for testability.

Reference:
    - OMN-2424: Pattern projection snapshot publisher
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from omniintelligence.models.events.model_pattern_projection_event import (
    ModelPatternProjectionEvent,
)
from omniintelligence.models.repository.model_pattern_summary import ModelPatternSummary
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternQueryStore
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

_QUERY_LIMIT: int = 500
"""Maximum patterns fetched per page when building a projection snapshot.

A full snapshot queries all validated/provisional patterns. We paginate
in chunks of 500 to avoid loading unbounded rows into memory in one call.
Increase if the pattern store grows beyond this threshold.
"""

_MIN_CONFIDENCE: float = 0.0
"""Minimum confidence for projection queries.

Projection snapshots include all validated/provisional patterns regardless
of confidence score — filtering is deferred to the consumer.
"""

_PROJECTION_VERSION: int = 1
"""Current schema version for ModelPatternProjectionEvent.

Increment when the snapshot schema changes incompatibly.
"""


# =============================================================================
# Handler
# =============================================================================


async def publish_projection(
    pattern_query_store: ProtocolPatternQueryStore,
    producer: ProtocolKafkaPublisher | None,
    *,
    correlation_id: UUID | None,
    publish_topic: str | None,
    trigger_event_type: str = "unknown",
    triggering_pattern_id: UUID | None = None,
) -> ModelPatternProjectionEvent:
    """Query all validated patterns and publish a full materialized snapshot.

    On each trigger (pattern promoted, deprecated, or lifecycle-transitioned):
    1. Query all validated/provisional patterns via pattern_query_store
    2. Build a ModelPatternProjectionEvent snapshot with explicit snapshot_at
    3. Publish the snapshot to the projection topic (fire-and-forget)
    4. Return the snapshot model regardless of Kafka publish outcome

    Fire-and-Forget Emission:
        If the Kafka producer is None or raises, the exception is caught and
        logged. The handler always returns the built snapshot. Callers receive
        the snapshot model even if Kafka publication failed.

    Args:
        pattern_query_store: REQUIRED store for querying validated patterns.
        producer: Optional Kafka publisher. When None, the snapshot is built
            but not published to Kafka (graceful degradation).
        correlation_id: Correlation ID from the triggering lifecycle event.
            Threaded into the snapshot payload for distributed tracing.
        publish_topic: Full Kafka topic string for the projection event.
            Required when producer is not None; ignored when producer is None.
        trigger_event_type: Event type string of the triggering event
            (e.g. "PatternPromoted"). Used for logging only.
        triggering_pattern_id: Pattern ID from the triggering event.
            Used for logging only.

    Returns:
        ModelPatternProjectionEvent containing the full pattern snapshot.
        Always returned — Kafka failures do not prevent snapshot construction.
    """
    snapshot_id = uuid4()
    snapshot_at = datetime.now(UTC)

    logger.info(
        "Building pattern projection snapshot (trigger=%s, pattern_id=%s, "
        "correlation_id=%s, snapshot_id=%s)",
        trigger_event_type,
        triggering_pattern_id,
        correlation_id,
        snapshot_id,
        extra={"correlation_id": str(correlation_id) if correlation_id else None},
    )

    # Step 1: Query all validated/provisional patterns (paginated)
    all_patterns: list[ModelPatternSummary] = []
    offset = 0

    while True:
        try:
            raw_rows = await pattern_query_store.query_patterns(
                domain=None,
                language=None,
                min_confidence=_MIN_CONFIDENCE,
                limit=_QUERY_LIMIT,
                offset=offset,
            )
        except Exception as query_exc:
            sanitized = get_log_sanitizer().sanitize(str(query_exc))
            logger.error(
                "Failed to query patterns for projection snapshot "
                "(snapshot_id=%s, offset=%d, correlation_id=%s, error=%s)",
                snapshot_id,
                offset,
                correlation_id,
                sanitized,
                extra={
                    "correlation_id": str(correlation_id) if correlation_id else None
                },
            )
            # Return an empty snapshot rather than propagating the error.
            # The snapshot_at must still be set to maintain model validity.
            return ModelPatternProjectionEvent(
                snapshot_id=snapshot_id,
                snapshot_at=snapshot_at,
                patterns=[],
                total_count=0,
                version=_PROJECTION_VERSION,
                correlation_id=correlation_id,
            )

        if not raw_rows:
            break

        for row in raw_rows:
            try:
                pattern = ModelPatternSummary.model_validate(row)
                all_patterns.append(pattern)
            except Exception as parse_exc:
                sanitized_parse = get_log_sanitizer().sanitize(str(parse_exc))
                logger.warning(
                    "Failed to parse pattern row for projection snapshot "
                    "(snapshot_id=%s, row_keys=%s, correlation_id=%s, error=%s)",
                    snapshot_id,
                    sorted(row.keys()) if isinstance(row, dict) else type(row).__name__,
                    correlation_id,
                    sanitized_parse,
                    extra={
                        "correlation_id": str(correlation_id)
                        if correlation_id
                        else None
                    },
                )
                # Skip malformed rows — partial snapshot is better than no snapshot

        if len(raw_rows) < _QUERY_LIMIT:
            # Last page reached
            break

        offset += _QUERY_LIMIT

    # Step 2: Build the projection snapshot
    snapshot = ModelPatternProjectionEvent(
        snapshot_id=snapshot_id,
        snapshot_at=snapshot_at,
        patterns=all_patterns,
        total_count=len(all_patterns),
        version=_PROJECTION_VERSION,
        correlation_id=correlation_id,
    )

    logger.info(
        "Pattern projection snapshot built "
        "(snapshot_id=%s, total_count=%d, correlation_id=%s)",
        snapshot_id,
        snapshot.total_count,
        correlation_id,
        extra={"correlation_id": str(correlation_id) if correlation_id else None},
    )

    # Step 3: Publish snapshot to Kafka (fire-and-forget)
    if producer is not None:
        if publish_topic is None:
            logger.warning(
                "publish_topic is None but producer is available — skipping Kafka publish "
                "(snapshot_id=%s, correlation_id=%s)",
                snapshot_id,
                correlation_id,
                extra={
                    "correlation_id": str(correlation_id) if correlation_id else None
                },
            )
        else:
            try:
                await producer.publish(
                    topic=publish_topic,
                    key=str(snapshot_id),
                    value=snapshot.model_dump(mode="json"),
                )
                logger.debug(
                    "Pattern projection snapshot published to Kafka "
                    "(snapshot_id=%s, topic=%s, total_count=%d, correlation_id=%s)",
                    snapshot_id,
                    publish_topic,
                    snapshot.total_count,
                    correlation_id,
                    extra={
                        "correlation_id": str(correlation_id)
                        if correlation_id
                        else None
                    },
                )
            except Exception as kafka_exc:
                # Fire-and-forget: Kafka failures do not propagate
                sanitized_kafka = get_log_sanitizer().sanitize(str(kafka_exc))
                logger.error(
                    "Kafka publish failed for pattern projection snapshot — fire-and-forget, "
                    "not propagating (snapshot_id=%s, topic=%s, correlation_id=%s, error=%s)",
                    snapshot_id,
                    publish_topic,
                    correlation_id,
                    sanitized_kafka,
                    extra={
                        "correlation_id": str(correlation_id)
                        if correlation_id
                        else None
                    },
                )

    return snapshot


__all__ = [
    "publish_projection",
]
