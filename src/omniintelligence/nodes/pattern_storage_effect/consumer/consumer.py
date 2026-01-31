# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Kafka consumer for pattern storage events.

Consumes pattern-learned events with idempotency handling.
Transaction boundary spans both dedupe insert and pattern storage.

The consumer follows this invariant for exactly-once semantics:
    1. Poll Kafka message
    2. Validate event envelope
    3. Begin DB transaction
    4. Dedupe check (INSERT ON CONFLICT DO NOTHING RETURNING)
    5. If duplicate: skip, commit offset
    6. If new: call handle_store_pattern with conn
    7. Commit DB transaction
    8. Commit Kafka offset

Reference: OMN-1669 (STORE-004)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any

from omniintelligence.nodes.pattern_storage_effect.consumer.envelope import (
    ModelEventEnvelope,
)
from omniintelligence.nodes.pattern_storage_effect.consumer.idempotency import (
    IdempotencyGate,
    cleanup_processed_events,
)
from omniintelligence.nodes.pattern_storage_effect.handlers.handler_store_pattern import (
    ProtocolPatternStore,
    handle_store_pattern,
)
from omniintelligence.nodes.pattern_storage_effect.models import (
    ModelPatternStorageInput,
)

if TYPE_CHECKING:
    from asyncpg import Pool as AsyncPool
    from confluent_kafka import Consumer as KafkaConsumer
    from confluent_kafka import Message

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

DEFAULT_CONSUMER_GROUP = "omniintelligence.pattern_storage_effect.v1"
DEFAULT_SUBSCRIBE_TOPIC = "onex.evt.omniintelligence.pattern-learned.v1"
CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes
RETENTION_DAYS = 7
POLL_TIMEOUT_SECONDS = 1.0


# =============================================================================
# Consumer Implementation
# =============================================================================


class PatternStorageConsumer:
    """Kafka consumer for pattern storage with idempotency.

    Handles pattern-learned events with transactional idempotency:
    - Dedupe check and pattern storage in same DB transaction
    - Kafka offset committed only after DB commit succeeds
    - Background cleanup of processed_events table

    Invariant Flow:
        1. Poll Kafka message
        2. Validate event envelope (extracts event_id for idempotency)
        3. Begin DB transaction
        4. Dedupe check via INSERT ON CONFLICT DO NOTHING RETURNING
        5. If duplicate: skip processing, still commit Kafka offset
        6. If new: call handle_store_pattern within same transaction
        7. Commit DB transaction
        8. Commit Kafka offset (only after DB commit succeeds)

    This ensures exactly-once semantics: if DB commit fails, Kafka offset
    is not committed, and the message will be redelivered.

    Usage:
        consumer = PatternStorageConsumer(
            db_pool=db_pool,
            kafka_consumer=kafka_consumer,
            pattern_store=pattern_store,
        )
        await consumer.start()

        # ... later ...

        await consumer.stop()
    """

    def __init__(
        self,
        *,
        db_pool: AsyncPool,
        kafka_consumer: KafkaConsumer,
        pattern_store: ProtocolPatternStore,
        consumer_group: str = DEFAULT_CONSUMER_GROUP,
        subscribe_topic: str = DEFAULT_SUBSCRIBE_TOPIC,
    ) -> None:
        """Initialize the pattern storage consumer.

        Args:
            db_pool: asyncpg connection pool (caller-provided, consumer owns tx)
            kafka_consumer: Confluent Kafka consumer (configured but not subscribed)
            pattern_store: Implementation of ProtocolPatternStore for persistence
            consumer_group: Kafka consumer group ID
            subscribe_topic: Topic to subscribe to
        """
        self._db_pool = db_pool
        self._kafka_consumer = kafka_consumer
        self._pattern_store = pattern_store
        self._consumer_group = consumer_group
        self._subscribe_topic = subscribe_topic
        self._gate = IdempotencyGate()
        self._running = False
        self._cleanup_task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        """Check if the consumer is currently running."""
        return self._running

    async def start(self) -> None:
        """Start the consumer loop and cleanup task.

        Subscribes to the configured topic, starts the background cleanup
        task, and enters the main consume loop. This method blocks until
        stop() is called.
        """
        self._running = True
        self._kafka_consumer.subscribe([self._subscribe_topic])

        # Start background cleanup
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(),
            name="pattern_storage_consumer_cleanup",
        )

        logger.info(
            "consumer.started",
            extra={
                "consumer_group": self._consumer_group,
                "subscribe_topic": self._subscribe_topic,
            },
        )

        try:
            await self._consume_loop()
        finally:
            # Ensure cleanup on unexpected exit
            if self._running:
                await self.stop()

    async def stop(self) -> None:
        """Stop the consumer gracefully.

        Cancels the cleanup task, closes the Kafka consumer, and logs
        the shutdown. Safe to call multiple times.
        """
        if not self._running:
            return

        self._running = False

        # Cancel background cleanup task
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None

        # Close Kafka consumer
        self._kafka_consumer.close()

        logger.info(
            "consumer.stopped",
            extra={
                "consumer_group": self._consumer_group,
                "subscribe_topic": self._subscribe_topic,
            },
        )

    async def _consume_loop(self) -> None:
        """Main consume loop.

        Polls for messages and processes them with idempotency guarantees.
        Continues until stop() is called (sets _running to False).
        """
        while self._running:
            try:
                # Poll with timeout (non-blocking allows graceful shutdown)
                msg = self._kafka_consumer.poll(timeout=POLL_TIMEOUT_SECONDS)

                if msg is None:
                    # No message available, continue polling
                    await asyncio.sleep(0)  # Yield to event loop
                    continue

                if msg.error():
                    logger.error(
                        "kafka.error",
                        extra={
                            "error": str(msg.error()),
                            "consumer_group": self._consumer_group,
                        },
                    )
                    continue

                await self._process_message(msg)

            except asyncio.CancelledError:
                # Graceful shutdown
                logger.info("consume_loop.cancelled")
                raise
            except Exception:
                logger.exception(
                    "consume_loop.error",
                    extra={"consumer_group": self._consumer_group},
                )
                # Continue processing other messages
                # (individual message failures should not stop the consumer)

    async def _process_message(self, msg: Message) -> None:
        """Process a single Kafka message with idempotency.

        Implements the exactly-once invariant:
            1. Parse and validate envelope
            2. Begin transaction
            3. Dedupe check (atomic INSERT ON CONFLICT)
            4. If new: call handler within same transaction
            5. Commit transaction
            6. Commit Kafka offset

        Args:
            msg: Kafka message to process

        Note:
            If any step fails before Kafka commit, the message will be
            redelivered. The idempotency gate ensures duplicate processing
            is skipped on retry.
        """
        # Track whether this was a duplicate for logging
        is_new = False

        try:
            # Step 1: Parse JSON payload
            raw_value = msg.value()
            if raw_value is None:
                logger.warning(
                    "message.empty",
                    extra={"offset": msg.offset(), "partition": msg.partition()},
                )
                return

            payload: dict[str, Any] = json.loads(raw_value.decode("utf-8"))

            # Step 2: Validate event envelope (extracts event_id for idempotency)
            envelope = ModelEventEnvelope.model_validate(payload)

            # Steps 3-6: Transaction-scoped dedupe and storage
            async with self._db_pool.acquire() as conn:
                async with conn.transaction():
                    # Step 4: Idempotency check (atomic INSERT ON CONFLICT)
                    is_new = await self._gate.check_and_mark(conn, envelope.event_id)

                    if is_new:
                        # Step 5: New event - process within same transaction
                        input_data = ModelPatternStorageInput.model_validate(payload)
                        await handle_store_pattern(
                            input_data,
                            pattern_store=self._pattern_store,
                            conn=conn,
                        )
                    # If duplicate: skip processing, transaction commits empty changes

            # Step 7: Commit Kafka offset (only after DB transaction succeeds)
            self._kafka_consumer.commit(message=msg)

            logger.debug(
                "message.processed",
                extra={
                    "event_id": str(envelope.event_id),
                    "was_duplicate": not is_new,
                    "offset": msg.offset(),
                    "partition": msg.partition(),
                    "correlation_id": (
                        str(envelope.correlation_id)
                        if envelope.correlation_id
                        else None
                    ),
                },
            )

        except json.JSONDecodeError as e:
            # Invalid JSON - log and skip (don't retry, will always fail)
            logger.error(
                "message.invalid_json",
                extra={
                    "offset": msg.offset(),
                    "partition": msg.partition(),
                    "error": str(e),
                },
            )
            # Commit offset to avoid infinite retry loop on invalid messages
            self._kafka_consumer.commit(message=msg)

        except Exception:
            # Processing failed - don't commit offset, message will be redelivered
            logger.exception(
                "message.failed",
                extra={
                    "offset": msg.offset(),
                    "partition": msg.partition(),
                    "topic": msg.topic(),
                },
            )
            # Do NOT commit offset - message will be reprocessed on restart

    async def _cleanup_loop(self) -> None:
        """Background task to clean up old processed events.

        Runs every CLEANUP_INTERVAL_SECONDS (5 minutes) and deletes
        processed events older than RETENTION_DAYS (7 days).

        This prevents the processed_events table from growing unbounded
        while maintaining idempotency protection for recent events.
        """
        while self._running:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

                if not self._running:
                    break

                async with self._db_pool.acquire() as conn:
                    deleted_count = await cleanup_processed_events(
                        conn, RETENTION_DAYS
                    )
                    if deleted_count > 0:
                        logger.info(
                            "cleanup.completed",
                            extra={
                                "deleted_count": deleted_count,
                                "retention_days": RETENTION_DAYS,
                            },
                        )

            except asyncio.CancelledError:
                logger.debug("cleanup_loop.cancelled")
                raise
            except Exception:
                logger.exception(
                    "cleanup.failed",
                    extra={"retention_days": RETENTION_DAYS},
                )
                # Continue cleanup loop despite errors


__all__ = [
    "DEFAULT_CONSUMER_GROUP",
    "DEFAULT_SUBSCRIBE_TOPIC",
    "PatternStorageConsumer",
]
