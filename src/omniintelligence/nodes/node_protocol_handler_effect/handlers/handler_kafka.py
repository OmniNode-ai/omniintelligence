# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Kafka protocol handler.

Implements the ProtocolHandler interface for Apache Kafka produce/consume
operations using confluent-kafka.

Supported Operations:
    - produce: Produce a message to a topic
    - consume: Consume messages from subscribed topics

Config Keys:
    - bootstrap_servers (str, required): Kafka broker addresses
    - client_id (str, optional): Client identifier (default: "onex-protocol-handler")
    - producer_config (dict, optional): Additional producer configuration
    - consumer_config (dict, optional): Additional consumer configuration
    - group_id (str, optional): Consumer group ID (required for consume)

Params Keys:
    For produce:
        - topic (str, required): Target topic
        - key (str, optional): Message key
        - value (dict, required): Message value (JSON-serialized)
        - headers (dict, optional): Message headers

    For consume:
        - topics (list[str], required): Topics to subscribe to
        - timeout (float, optional): Poll timeout in seconds (default: 1.0)
        - max_messages (int, optional): Maximum messages to consume (default: 1)

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from __future__ import annotations

import json
import logging
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer

# =============================================================================
# Logging
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

VALID_OPERATIONS = frozenset({"produce", "consume"})
DEFAULT_CLIENT_ID = "onex-protocol-handler"
DEFAULT_POLL_TIMEOUT = 1.0
DEFAULT_MAX_MESSAGES = 1


# =============================================================================
# Handler Implementation
# =============================================================================


class KafkaHandler:
    """Kafka protocol handler using confluent-kafka.

    Manages both a producer and consumer instance. The producer is always
    created; the consumer is only created when a group_id is provided.

    Thread Safety:
        confluent-kafka Producer and Consumer are NOT thread-safe but
        are safe for sequential use from a single coroutine. Operations
        run synchronously in the event loop (confluent-kafka does not
        provide native async). For production use, consider wrapping
        in run_in_executor.

    Note:
        This handler uses synchronous confluent-kafka calls. For high-throughput
        scenarios, the caller should run operations via asyncio.to_thread()
        or use the ONEX event bus abstraction instead.
    """

    def __init__(self) -> None:
        self._producer: Producer | None = None
        self._consumer: Consumer | None = None
        self._bootstrap_servers: str = ""
        self._connected: bool = False

    async def connect(self, config: dict[str, Any]) -> None:
        """Create Kafka producer and optionally consumer.

        Args:
            config: Connection configuration.
                - bootstrap_servers (str, required): Broker addresses.
                - client_id (str, optional): Client identifier.
                - producer_config (dict, optional): Additional producer config.
                - consumer_config (dict, optional): Additional consumer config.
                - group_id (str, optional): Consumer group (enables consumer).

        Raises:
            ConnectionError: If bootstrap_servers is missing.
        """
        bootstrap_servers = config.get("bootstrap_servers")
        if not bootstrap_servers:
            raise ConnectionError("KafkaHandler requires 'bootstrap_servers' in config")

        client_id = config.get("client_id", DEFAULT_CLIENT_ID)
        self._bootstrap_servers = str(bootstrap_servers)

        # Build producer config
        producer_conf: dict[str, Any] = {
            "bootstrap.servers": self._bootstrap_servers,
            "client.id": f"{client_id}-producer",
            **(config.get("producer_config", {})),
        }

        try:
            self._producer = Producer(producer_conf)
        except KafkaException as exc:
            raise ConnectionError(f"Kafka producer creation failed: {exc}") from exc

        # Build consumer config (only if group_id provided)
        group_id = config.get("group_id")
        if group_id:
            consumer_conf: dict[str, Any] = {
                "bootstrap.servers": self._bootstrap_servers,
                "client.id": f"{client_id}-consumer",
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                **(config.get("consumer_config", {})),
            }
            try:
                self._consumer = Consumer(consumer_conf)
            except KafkaException as exc:
                raise ConnectionError(f"Kafka consumer creation failed: {exc}") from exc

        self._connected = True
        logger.info(
            "Kafka handler connected",
            extra={
                "bootstrap_servers": self._bootstrap_servers,
                "has_consumer": self._consumer is not None,
            },
        )

    async def execute(
        self,
        operation: str,
        params: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a Kafka operation.

        Args:
            operation: "produce" or "consume".
            params: Operation parameters (see module docstring).
            correlation_id: Optional correlation ID added to message headers.

        Returns:
            For produce: dict with "topic", "partition", "offset".
            For consume: dict with "messages" (list of message dicts).

        Raises:
            RuntimeError: If handler is not connected.
            ConnectionError: If Kafka is unreachable.
        """
        if not self._connected:
            raise RuntimeError("KafkaHandler is not connected. Call connect() first.")

        if operation not in VALID_OPERATIONS:
            raise ValueError(
                f"Unsupported Kafka operation: {operation}. Must be one of {VALID_OPERATIONS}"
            )

        if operation == "produce":
            return self._produce(params, correlation_id=correlation_id)
        else:
            return self._consume(params, correlation_id=correlation_id)

    def _produce(
        self,
        params: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Produce a message to a Kafka topic.

        Args:
            params: Must contain "topic" and "value".
            correlation_id: Added to headers if provided.

        Returns:
            dict with "topic", "delivered" status.
        """
        if self._producer is None:
            raise RuntimeError("Kafka producer is not initialized")

        topic = params.get("topic")
        if not topic:
            raise ValueError("KafkaHandler produce requires 'topic' in params")

        value = params.get("value")
        if value is None:
            raise ValueError("KafkaHandler produce requires 'value' in params")

        key = params.get("key")
        headers = dict(params.get("headers", {}))

        if correlation_id:
            headers["correlation-id"] = correlation_id

        # Serialize
        value_bytes = (
            json.dumps(value).encode("utf-8")
            if isinstance(value, dict)
            else str(value).encode("utf-8")
        )
        key_bytes = key.encode("utf-8") if key else None

        # Convert headers to list of tuples (confluent-kafka format)
        header_list = [
            (k, v.encode("utf-8") if isinstance(v, str) else v)
            for k, v in headers.items()
        ]

        delivery_result: dict[str, Any] = {"topic": topic, "delivered": False}

        def on_delivery(err: Any, msg: Any) -> None:
            if err is not None:
                delivery_result["error"] = str(err)
            else:
                delivery_result["delivered"] = True
                delivery_result["partition"] = msg.partition()
                delivery_result["offset"] = msg.offset()

        self._producer.produce(
            topic=topic,
            key=key_bytes,
            value=value_bytes,
            headers=header_list if header_list else None,
            on_delivery=on_delivery,
        )

        # Flush to ensure delivery callback fires
        self._producer.flush(timeout=10.0)

        logger.debug(
            "Kafka produce completed",
            extra={
                "topic": topic,
                "delivered": delivery_result.get("delivered", False),
                "correlation_id": correlation_id,
            },
        )

        return delivery_result

    def _consume(
        self,
        params: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Consume messages from Kafka topics.

        Args:
            params: Must contain "topics".
            correlation_id: For logging only.

        Returns:
            dict with "messages" list.
        """
        if self._consumer is None:
            raise RuntimeError(
                "Kafka consumer is not initialized. Provide 'group_id' in connect config."
            )

        topics = params.get("topics")
        if not topics:
            raise ValueError("KafkaHandler consume requires 'topics' in params")

        timeout = params.get("timeout", DEFAULT_POLL_TIMEOUT)
        max_messages = params.get("max_messages", DEFAULT_MAX_MESSAGES)

        self._consumer.subscribe(topics)

        messages: list[dict[str, Any]] = []
        for _ in range(max_messages):
            msg = self._consumer.poll(timeout=timeout)
            if msg is None:
                break
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    break
                raise ConnectionError(f"Kafka consumer error: {msg.error()}")

            msg_dict: dict[str, Any] = {
                "topic": msg.topic(),
                "partition": msg.partition(),
                "offset": msg.offset(),
                "key": msg.key().decode("utf-8") if msg.key() else None,
                "value": json.loads(msg.value().decode("utf-8"))
                if msg.value()
                else None,
            }

            # Parse headers
            if msg.headers():
                msg_dict["headers"] = {
                    k: v.decode("utf-8") if isinstance(v, bytes) else v
                    for k, v in msg.headers()
                }

            messages.append(msg_dict)

        logger.debug(
            "Kafka consume completed",
            extra={
                "message_count": len(messages),
                "correlation_id": correlation_id,
            },
        )

        return {"messages": messages}

    async def disconnect(self) -> None:
        """Close Kafka producer and consumer."""
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None

        if self._producer is not None:
            self._producer.flush(timeout=5.0)
            self._producer = None

        self._connected = False
        logger.info("Kafka handler disconnected")

    async def health_check(self) -> bool:
        """Check if the Kafka handler is connected.

        Returns:
            True if the handler is connected and the producer exists.
        """
        return self._connected and self._producer is not None


__all__ = [
    "KafkaHandler",
]
