"""
Real Kafka Event Publisher for Intelligence Service

Uses confluent_kafka to publish events to actual Kafka topics.
Replaces stub publisher in HybridEventRouter.

Created: 2025-10-21
Purpose: Enable real event publishing to Kafka
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from confluent_kafka import Producer

# Centralized configuration
from config import settings

logger = logging.getLogger(__name__)


# NOTE: correlation_id support enabled for tracing
class KafkaEventPublisher:
    """
    Real Kafka publisher using confluent_kafka.

    Publishes events to actual Kafka topics with delivery guarantees.
    """

    def __init__(self, config: Optional[Any] = None):
        """
        Initialize Kafka publisher.

        Args:
            config: Optional configuration (not used, kept for compatibility)
        """
        self.config = config
        self.is_connected = False

        # Get Kafka bootstrap servers from centralized config
        bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", settings.kafka_bootstrap_servers
        )

        # Initialize confluent_kafka Producer
        self._producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "client.id": "archon-intelligence-publisher",
                "acks": "all",  # Wait for all replicas to acknowledge
                "retries": 3,
                "retry.backoff.ms": 100,
                # Note: Compression disabled for test compatibility
                # "compression.type": "snappy",
            }
        )

        self.is_connected = True
        logger.info(
            f"Kafka publisher initialized successfully | bootstrap_servers={bootstrap_servers}"
        )

    async def initialize(self) -> None:
        """Initialize publisher (already done in __init__)."""
        pass

    def _delivery_callback(self, err, msg):
        """
        Kafka delivery callback.

        Args:
            err: Error if delivery failed
            msg: Message metadata if delivery succeeded
        """
        if err:
            logger.error(f"Kafka delivery failed: {err} | topic={msg.topic()}")
        else:
            logger.debug(
                f"Kafka delivery succeeded | topic={msg.topic()} | "
                f"partition={msg.partition()} | offset={msg.offset()}"
            )

    async def publish(
        self,
        topic: str,
        event: Any,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        partition: Optional[int] = None,
    ) -> None:
        """
        Publish event to Kafka topic.

        Args:
            topic: Kafka topic name
            event: Event object (ModelEvent or dict)
            key: Optional message key
            headers: Optional message headers
            partition: Optional partition (None = automatic)
        """
        try:
            logger.info(f"🚀 publish() called | topic={topic} | key={key}")

            # Convert event to dict if it's an object
            if hasattr(event, "model_dump"):
                event_dict = event.model_dump()
            elif hasattr(event, "dict"):
                event_dict = event.dict()
            else:
                event_dict = event if isinstance(event, dict) else {}

            logger.info(
                f"✅ Event converted to dict | keys={list(event_dict.keys())[:5]}"
            )

            # Convert UUIDs to strings for JSON serialization
            def convert_uuids(obj):
                if isinstance(obj, dict):
                    return {k: convert_uuids(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_uuids(item) for item in obj]
                elif isinstance(obj, UUID):
                    return str(obj)
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                else:
                    return obj

            event_dict = convert_uuids(event_dict)

            # Serialize to JSON
            value = json.dumps(event_dict).encode("utf-8")
            logger.info(f"✅ Event serialized | size={len(value)} bytes")

            # Convert key to bytes if provided
            key_bytes = key.encode("utf-8") if key else None

            # Convert headers to list of tuples if provided
            headers_list = None
            if headers:
                headers_list = [(k, v.encode("utf-8")) for k, v in headers.items()]

            # Build produce kwargs (only include partition if not None)
            produce_kwargs = {
                "topic": topic,
                "value": value,
                "key": key_bytes,
                "headers": headers_list,
                "callback": self._delivery_callback,
            }
            if partition is not None:
                produce_kwargs["partition"] = partition

            # Publish to Kafka
            logger.info(
                f"📤 Calling producer.produce() | topic={topic} | partition={partition}"
            )
            self._producer.produce(**produce_kwargs)
            logger.info(f"✅ producer.produce() succeeded")

            # Flush to ensure immediate delivery
            # flush() blocks until message is sent or timeout
            logger.info(f"🔄 Calling producer.flush(timeout=5.0)")
            remaining = self._producer.flush(timeout=5.0)
            logger.info(
                f"✅ producer.flush() completed | remaining_messages={remaining}"
            )

            logger.info(f"✅ Published event to Kafka | topic={topic} | key={key}")

        except Exception as e:
            logger.error(
                f"❌ Failed to publish to Kafka | topic={topic} | error={e}",
                exc_info=True,
            )
            raise

    async def publish_batch(
        self,
        topic: str,
        events: list,
        keys: Optional[list] = None,
        headers: Optional[list] = None,
    ) -> None:
        """
        Publish batch of events to Kafka.

        Args:
            topic: Kafka topic name
            events: List of events
            keys: Optional list of keys
            headers: Optional list of headers
        """
        keys = keys or [None] * len(events)
        headers = headers or [None] * len(events)

        for event, key, header in zip(events, keys, headers):
            await self.publish(topic, event, key, header)

        # Flush all messages
        self._producer.flush(timeout=10.0)

    async def shutdown(self) -> None:
        """Shutdown publisher and flush pending messages."""
        if self._producer:
            logger.info("Flushing pending Kafka messages...")
            self._producer.flush(timeout=10.0)
            logger.info("Kafka publisher shutdown complete")
            self.is_connected = False
