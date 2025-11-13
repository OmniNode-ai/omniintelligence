"""
Dead Letter Queue (DLQ) Handler - Phase 1

Handles monitoring and reprocessing of failed events in DLQ.

Features:
- DLQ message consumption and parsing
- Reprocessing with backoff strategy
- Metrics tracking (DLQ size, reprocessing success/failure)
- Alert integration (future: Slack, PagerDuty)

Created: 2025-10-18
Reference: EVENT_BUS_ARCHITECTURE.md Phase 1
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from confluent_kafka import Consumer, KafkaError, Message, Producer

logger = logging.getLogger(__name__)


@dataclass
class DLQMessage:
    """
    Dead Letter Queue message structure.

    Contains original event envelope plus error metadata.
    """

    original_topic: str
    original_envelope: dict[str, Any]
    error_message: str
    error_timestamp: float
    service: str
    instance_id: str
    retry_count: int
    dlq_topic: str
    partition: int
    offset: int


class DLQHandler:
    """
    Dead Letter Queue handler for monitoring and reprocessing.

    Monitors DLQ topics for failed events, tracks metrics, and provides
    reprocessing capabilities with configurable retry strategies.

    Features:
    - Automatic DLQ topic subscription (*.dlq pattern)
    - Metrics tracking (message count, error patterns, age)
    - Reprocessing with exponential backoff
    - Alert thresholds for DLQ overflow

    Usage:
        from config import settings
        handler = DLQHandler(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            consumer_group="dlq-handler"
        )

        await handler.start()

        # Get DLQ metrics
        metrics = handler.get_metrics()

        # Reprocess messages from specific DLQ
        await handler.reprocess_dlq(
            dlq_topic="omninode.codegen.request.validate.v1.dlq",
            limit=100
        )

        await handler.stop()
    """

    def __init__(
        self,
        bootstrap_servers: str,
        consumer_group: str = "dlq-handler",
        dlq_topic_pattern: str = r".*\.dlq",
        alert_threshold: int = 100,
        max_dlq_message_age_hours: int = 24,
        reprocess_producer_servers: Optional[str] = None,
    ):
        """
        Initialize DLQ handler.

        Args:
            bootstrap_servers: Kafka bootstrap servers
            consumer_group: Consumer group for DLQ monitoring
            dlq_topic_pattern: Regex pattern for DLQ topics (default: "*.dlq")
            alert_threshold: Alert if DLQ message count exceeds this (default: 100)
            max_dlq_message_age_hours: Alert if messages older than this (default: 24h)
            reprocess_producer_servers: Kafka servers for reprocessing (defaults to bootstrap_servers)
        """
        self.bootstrap_servers = bootstrap_servers
        self.consumer_group = consumer_group
        self.dlq_topic_pattern = dlq_topic_pattern
        self.alert_threshold = alert_threshold
        self.max_dlq_message_age_hours = max_dlq_message_age_hours
        self.reprocess_producer_servers = (
            reprocess_producer_servers or bootstrap_servers
        )

        # Kafka consumer and producer
        self.consumer: Optional[Consumer] = None
        self.producer: Optional[Producer] = None

        # State
        self.running = False
        self._consumer_task: Optional[asyncio.Task] = None

        # DLQ message storage (in-memory for monitoring)
        self.dlq_messages: list[DLQMessage] = []

        # Metrics
        self.metrics = {
            "total_dlq_messages": 0,
            "messages_by_topic": {},
            "messages_by_error_type": {},
            "oldest_message_age_hours": 0.0,
            "reprocessing_success": 0,
            "reprocessing_failed": 0,
            "alerts_triggered": 0,
        }

    async def start(self) -> None:
        """
        Start DLQ handler.

        Initializes consumer and begins monitoring DLQ topics.
        """
        if self.running:
            logger.warning("DLQ handler already running")
            return

        logger.info(f"Starting DLQ handler | consumer_group={self.consumer_group}")

        # Initialize consumer
        self._initialize_consumer()

        # Initialize producer (for reprocessing)
        self._initialize_producer()

        # Subscribe to DLQ topics
        await self._subscribe_to_dlq_topics()

        self.running = True

        # Start background consumer loop
        self._consumer_task = asyncio.create_task(self._consumer_loop())

        logger.info("DLQ handler started successfully")

    async def stop(self) -> None:
        """
        Stop DLQ handler gracefully.

        Stops consumer loop and closes connections.
        """
        if not self.running:
            logger.info("DLQ handler not running")
            return

        logger.info("Stopping DLQ handler")
        self.running = False

        # Wait for consumer task
        if self._consumer_task and not self._consumer_task.done():
            try:
                await asyncio.wait_for(self._consumer_task, timeout=10.0)
            except TimeoutError:
                logger.warning("Consumer task did not finish, cancelling")
                self._consumer_task.cancel()
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass

        # Close consumer
        if self.consumer:
            try:
                self.consumer.close()
                logger.info("DLQ consumer closed")
            except Exception as e:
                logger.error(f"Error closing DLQ consumer: {e}")

        # Close producer
        if self.producer:
            try:
                self.producer.flush(timeout=5.0)
                logger.info("DLQ producer flushed and closed")
            except Exception as e:
                logger.error(f"Error closing DLQ producer: {e}")

        logger.info("DLQ handler stopped")

    def _initialize_consumer(self) -> None:
        """Initialize Kafka consumer for DLQ monitoring."""
        consumer_config = {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.consumer_group,
            "auto.offset.reset": "earliest",  # Read from beginning
            "enable.auto.commit": True,
            "session.timeout.ms": 30000,
            "client.id": f"dlq-handler-{self.consumer_group}",
        }

        self.consumer = Consumer(consumer_config)
        logger.debug("DLQ consumer initialized")

    def _initialize_producer(self) -> None:
        """Initialize Kafka producer for reprocessing."""
        producer_config = {
            "bootstrap.servers": self.reprocess_producer_servers,
            "client.id": f"dlq-reprocessor-{self.consumer_group}",
            "acks": "all",
            "retries": 3,
        }

        self.producer = Producer(producer_config)
        logger.debug("DLQ producer initialized")

    async def _subscribe_to_dlq_topics(self) -> None:
        """Subscribe to all DLQ topics matching pattern."""
        if not self.consumer:
            raise RuntimeError("Consumer not initialized")

        # Get list of topics
        metadata = self.consumer.list_topics(timeout=10)

        # Filter DLQ topics
        dlq_topics = [topic for topic in metadata.topics if topic.endswith(".dlq")]

        if dlq_topics:
            self.consumer.subscribe(dlq_topics)
            logger.info(f"Subscribed to {len(dlq_topics)} DLQ topics: {dlq_topics}")
        else:
            logger.warning("No DLQ topics found")

    async def _consumer_loop(self) -> None:
        """
        Main consumer loop for DLQ monitoring.

        Polls DLQ topics and tracks metrics.
        """
        logger.info("DLQ consumer loop started")

        try:
            while self.running:
                # Poll for messages
                msg: Optional[Message] = await asyncio.to_thread(
                    self.consumer.poll, 1.0
                )

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"DLQ consumer error: {msg.error()}")
                        continue

                # Process DLQ message
                try:
                    await self._process_dlq_message(msg)
                except Exception as e:
                    logger.error(f"Error processing DLQ message: {e}", exc_info=True)

                await asyncio.sleep(0)

        except asyncio.CancelledError:
            logger.info("DLQ consumer loop cancelled")
            raise
        except Exception as e:
            logger.error(f"DLQ consumer loop error: {e}", exc_info=True)
        finally:
            logger.info("DLQ consumer loop stopped")

    async def _process_dlq_message(self, msg: Message) -> None:
        """
        Process a DLQ message.

        Parses message, updates metrics, and triggers alerts if needed.

        Args:
            msg: Kafka message from DLQ topic
        """
        try:
            # Deserialize message
            message_value = msg.value()
            if not message_value:
                return

            dlq_data = json.loads(message_value.decode("utf-8"))

            # Create DLQMessage
            dlq_message = DLQMessage(
                original_topic=dlq_data.get("original_topic", "unknown"),
                original_envelope=dlq_data.get("original_envelope", {}),
                error_message=dlq_data.get("error_message", "unknown"),
                error_timestamp=dlq_data.get("error_timestamp", 0.0),
                service=dlq_data.get("service", "unknown"),
                instance_id=dlq_data.get("instance_id", "unknown"),
                retry_count=dlq_data.get("retry_count", 0),
                dlq_topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
            )

            # Store message (limit to 1000 most recent)
            self.dlq_messages.append(dlq_message)
            if len(self.dlq_messages) > 1000:
                self.dlq_messages.pop(0)

            # Update metrics
            self._update_metrics(dlq_message)

            # Check alert thresholds
            await self._check_alert_thresholds()

            logger.debug(
                f"DLQ message processed | topic={dlq_message.dlq_topic} | "
                f"original_topic={dlq_message.original_topic} | "
                f"error={dlq_message.error_message}"
            )

        except Exception as e:
            logger.error(f"Error processing DLQ message: {e}", exc_info=True)

    def _update_metrics(self, dlq_message: DLQMessage) -> None:
        """
        Update DLQ metrics based on message.

        Args:
            dlq_message: DLQ message to process
        """
        self.metrics["total_dlq_messages"] += 1

        # Track by topic
        topic = dlq_message.original_topic
        self.metrics["messages_by_topic"][topic] = (
            self.metrics["messages_by_topic"].get(topic, 0) + 1
        )

        # Track by error type
        error_type = dlq_message.error_message.split(":")[0]
        self.metrics["messages_by_error_type"][error_type] = (
            self.metrics["messages_by_error_type"].get(error_type, 0) + 1
        )

        # Calculate message age
        message_age_hours = (time.time() - dlq_message.error_timestamp) / 3600
        if message_age_hours > self.metrics["oldest_message_age_hours"]:
            self.metrics["oldest_message_age_hours"] = message_age_hours

    async def _check_alert_thresholds(self) -> None:
        """
        Check if alert thresholds are exceeded.

        Triggers alerts if:
        - Total DLQ messages > alert_threshold
        - Oldest message > max_dlq_message_age_hours
        """
        total_messages = self.metrics["total_dlq_messages"]
        oldest_age = self.metrics["oldest_message_age_hours"]

        should_alert = False
        alert_reasons = []

        if total_messages > self.alert_threshold:
            should_alert = True
            alert_reasons.append(
                f"DLQ message count ({total_messages}) exceeds threshold ({self.alert_threshold})"
            )

        if oldest_age > self.max_dlq_message_age_hours:
            should_alert = True
            alert_reasons.append(
                f"Oldest DLQ message age ({oldest_age:.1f}h) exceeds threshold ({self.max_dlq_message_age_hours}h)"
            )

        if should_alert:
            self.metrics["alerts_triggered"] += 1
            logger.warning(f"DLQ ALERT | reasons={alert_reasons}")
            # TODO: Send to alerting system (Slack, PagerDuty, etc.)

    async def reprocess_dlq(
        self, dlq_topic: str, limit: Optional[int] = None
    ) -> dict[str, Any]:
        """
        Reprocess messages from specific DLQ topic.

        Republishes failed events to their original topics.

        Args:
            dlq_topic: DLQ topic to reprocess
            limit: Maximum messages to reprocess (None = all)

        Returns:
            Dict with reprocessing results:
            - messages_reprocessed: Count of messages successfully reprocessed
            - messages_failed: Count of messages that failed reprocessing
            - errors: List of errors encountered
        """
        if not self.producer:
            raise RuntimeError("Producer not initialized")

        logger.info(
            f"Starting DLQ reprocessing | dlq_topic={dlq_topic} | limit={limit}"
        )

        # Filter messages from specific DLQ topic
        messages_to_reprocess = [
            msg for msg in self.dlq_messages if msg.dlq_topic == dlq_topic
        ]

        if limit:
            messages_to_reprocess = messages_to_reprocess[:limit]

        success_count = 0
        failed_count = 0
        errors = []

        for dlq_message in messages_to_reprocess:
            try:
                # Reconstruct original event
                original_topic = dlq_message.original_topic
                original_envelope_json = json.dumps(
                    dlq_message.original_envelope
                ).encode("utf-8")

                # Republish to original topic
                self.producer.produce(
                    topic=original_topic, value=original_envelope_json
                )

                success_count += 1
                self.metrics["reprocessing_success"] += 1

                logger.debug(
                    f"Reprocessed DLQ message | original_topic={original_topic}"
                )

            except Exception as e:
                failed_count += 1
                self.metrics["reprocessing_failed"] += 1
                errors.append(str(e))

                logger.error(
                    f"Failed to reprocess DLQ message | error={e}", exc_info=True
                )

        # Flush producer
        self.producer.flush(timeout=10.0)

        logger.info(
            f"DLQ reprocessing completed | success={success_count} | failed={failed_count}"
        )

        return {
            "messages_reprocessed": success_count,
            "messages_failed": failed_count,
            "errors": errors,
        }

    def get_metrics(self) -> dict[str, Any]:
        """
        Get DLQ metrics.

        Returns:
            Dict with DLQ metrics:
            - total_dlq_messages: Total messages in DLQ
            - messages_by_topic: Breakdown by original topic
            - messages_by_error_type: Breakdown by error type
            - oldest_message_age_hours: Age of oldest message
            - reprocessing_success: Successful reprocessing count
            - reprocessing_failed: Failed reprocessing count
            - alerts_triggered: Number of alerts triggered
        """
        return self.metrics.copy()

    def get_dlq_summary(self) -> dict[str, Any]:
        """
        Get summary of DLQ status.

        Returns:
            Dict with summary:
            - total_messages: Total DLQ messages
            - oldest_message_age_hours: Age of oldest message
            - top_failing_topics: Topics with most failures
            - top_error_types: Most common error types
            - alert_status: Whether alerting thresholds are exceeded
        """
        top_failing_topics = sorted(
            self.metrics["messages_by_topic"].items(), key=lambda x: x[1], reverse=True
        )[:5]

        top_error_types = sorted(
            self.metrics["messages_by_error_type"].items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        alert_status = (
            "ALERT"
            if (
                self.metrics["total_dlq_messages"] > self.alert_threshold
                or self.metrics["oldest_message_age_hours"]
                > self.max_dlq_message_age_hours
            )
            else "OK"
        )

        return {
            "total_messages": self.metrics["total_dlq_messages"],
            "oldest_message_age_hours": self.metrics["oldest_message_age_hours"],
            "top_failing_topics": dict(top_failing_topics),
            "top_error_types": dict(top_error_types),
            "alert_status": alert_status,
            "alerts_triggered": self.metrics["alerts_triggered"],
        }


# ============================================================================
# Factory Functions
# ============================================================================


def create_dlq_handler(
    bootstrap_servers: str,
    consumer_group: str = "dlq-handler",
    **kwargs,
) -> DLQHandler:
    """
    Create DLQ handler instance.

    Args:
        bootstrap_servers: Kafka bootstrap servers
        consumer_group: Consumer group for DLQ monitoring
        **kwargs: Additional DLQHandler arguments

    Returns:
        Configured DLQHandler instance
    """
    return DLQHandler(
        bootstrap_servers=bootstrap_servers,
        consumer_group=consumer_group,
        **kwargs,
    )
