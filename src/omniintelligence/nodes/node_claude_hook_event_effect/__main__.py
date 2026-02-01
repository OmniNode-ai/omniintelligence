# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Claude Hook Event Effect Entry Point.

This module wires EventBusKafka for real Kafka event consumption:
    python -m omniintelligence.nodes.node_claude_hook_event_effect

Environment Variables:
    KAFKA_BOOTSTRAP_SERVERS: Kafka bootstrap servers (required)
        - Docker: omninode-bridge-redpanda:9092
        - Host scripts: 192.168.86.200:29092
    KAFKA_ENVIRONMENT: Environment prefix for topics (default: dev)
    LOG_LEVEL: Logging level (default: INFO)

This node subscribes to:
    {env}.onex.cmd.omniintelligence.claude-hook-event.v1

And publishes to:
    {env}.onex.evt.omniintelligence.intent-classified.v1

Reference:
    - OMN-1829: Wire RuntimeHostProcess for real Kafka event consumption
    - OMN-1456: Unified Claude Code hook endpoint
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from omnibase_infra.models import ModelEventMessage


def _get_log_level() -> int:
    """Get log level from environment with safe fallback."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        return logging.INFO
    return level


# Configure logging
logging.basicConfig(
    level=_get_log_level(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Kafka Publisher Adapter
# =============================================================================


class KafkaPublisherAdapter:
    """Adapter to use EventBusKafka as a ProtocolKafkaPublisher.

    Bridges the EventBusKafka.publish(topic, key: bytes, value: bytes) interface
    to the ProtocolKafkaPublisher.publish(topic, key: str, value: dict) interface.
    """

    def __init__(self, event_bus: Any) -> None:
        """Initialize adapter with EventBusKafka instance."""
        self._event_bus = event_bus

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Publish event to Kafka via EventBusKafka."""
        value_bytes = json.dumps(
            value, separators=(",", ":"), ensure_ascii=False, default=str
        ).encode("utf-8")
        key_bytes = key.encode("utf-8") if key else None
        await self._event_bus.publish(topic=topic, key=key_bytes, value=value_bytes)


# =============================================================================
# Event Processing
# =============================================================================


async def create_message_handler(
    kafka_publisher: KafkaPublisherAdapter,
    topic_env_prefix: str,
    publish_topic_suffix: str,
) -> Any:
    """Create a message handler closure for event processing.

    Returns an async callback that can be passed to event_bus.subscribe().
    """
    from omnibase_core.enums.hooks.claude_code import EnumClaudeCodeHookEventType
    from omnibase_core.models.hooks.claude_code import (
        ModelClaudeCodeHookEvent,
        ModelClaudeCodeHookEventPayload,
    )

    from omniintelligence.nodes.node_claude_hook_event_effect.handlers import (
        route_hook_event,
    )

    async def on_message(msg: ModelEventMessage) -> None:
        """Process incoming Kafka message."""
        try:
            # Deserialize message value
            if msg.value is None:
                logger.warning("Received message with null value, skipping")
                return

            payload_dict = json.loads(msg.value.decode("utf-8"))
            logger.debug(f"Received event: {payload_dict.get('event_type', 'unknown')}")

            # Convert to ModelClaudeCodeHookEvent
            # Handle event_type enum conversion
            event_type_str = payload_dict.get("event_type", "")
            try:
                event_type = EnumClaudeCodeHookEventType(event_type_str)
            except ValueError:
                # Try uppercase version
                try:
                    event_type = EnumClaudeCodeHookEventType[
                        event_type_str.upper().replace(" ", "_")
                    ]
                except KeyError:
                    logger.warning(f"Unknown event type: {event_type_str}, skipping")
                    return

            # Build payload model
            payload_data = payload_dict.get("payload", {})
            if isinstance(payload_data, dict):
                hook_payload = ModelClaudeCodeHookEventPayload(**payload_data)
            else:
                hook_payload = ModelClaudeCodeHookEventPayload()

            # Parse correlation_id
            correlation_id_str = payload_dict.get("correlation_id")
            if correlation_id_str:
                correlation_id = UUID(correlation_id_str)
            else:
                from uuid import uuid4

                correlation_id = uuid4()

            # Parse timestamp
            timestamp_str = payload_dict.get("timestamp_utc")
            if timestamp_str:
                timestamp_utc = datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                )
            else:
                timestamp_utc = datetime.now(UTC)

            # Create event model
            event = ModelClaudeCodeHookEvent(
                event_type=event_type,
                session_id=payload_dict.get("session_id", "unknown"),
                correlation_id=correlation_id,
                timestamp_utc=timestamp_utc,
                payload=hook_payload,
            )

            # Process event via handler
            result = await route_hook_event(
                event=event,
                intent_classifier=None,  # TODO: Wire intent classifier when available
                kafka_producer=kafka_publisher,
                topic_env_prefix=topic_env_prefix,
                publish_topic_suffix=publish_topic_suffix,
            )

            logger.info(
                f"Processed {event_type.value} event: status={result.status.value}, "
                f"session={event.session_id}, correlation={correlation_id}"
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message JSON: {e}")
        except Exception as e:
            logger.exception(f"Error processing message: {e}")

    return on_message


# =============================================================================
# Main Entry Point
# =============================================================================


async def main() -> None:
    """Run the Claude Hook Event Effect node with real Kafka consumption."""
    logger.info("=" * 60)
    logger.info("Starting Claude Hook Event Effect Node")
    logger.info("=" * 60)

    # Load configuration from environment
    kafka_env = os.getenv("KAFKA_ENVIRONMENT", "dev")

    # Topic configuration from contract.yaml
    subscribe_topic_suffix = "onex.cmd.omniintelligence.claude-hook-event.v1"
    publish_topic_suffix = "onex.evt.omniintelligence.intent-classified.v1"
    subscribe_topic = f"{kafka_env}.{subscribe_topic_suffix}"

    logger.info(f"Kafka environment: {kafka_env}")
    logger.info(f"Subscribe topic: {subscribe_topic}")
    logger.info(f"Publish topic suffix: {publish_topic_suffix}")

    # Import infrastructure components
    from omnibase_infra.event_bus.event_bus_kafka import EventBusKafka
    from omnibase_infra.models import ModelNodeIdentity

    # Create event bus from environment
    logger.info("Creating EventBusKafka from environment...")
    event_bus = EventBusKafka.default()
    await event_bus.start()
    logger.info("EventBusKafka started successfully")

    # Create Kafka publisher adapter
    kafka_publisher = KafkaPublisherAdapter(event_bus)

    # Create node identity for subscription
    node_identity = ModelNodeIdentity(
        env=kafka_env,
        service="omniintelligence",
        node_name="claude_hook_event_effect",
        version="1.0.0",
    )

    # Create message handler
    on_message = await create_message_handler(
        kafka_publisher=kafka_publisher,
        topic_env_prefix=kafka_env,
        publish_topic_suffix=publish_topic_suffix,
    )

    # Subscribe to input topic
    logger.info(f"Subscribing to topic: {subscribe_topic}")
    unsubscribe = await event_bus.subscribe(
        topic=subscribe_topic,
        node_identity=node_identity,
        on_message=on_message,
    )
    logger.info("Subscribed successfully")

    # Start consuming messages
    await event_bus.start_consuming()
    logger.info("Started consuming messages from Kafka")

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def handle_signal(sig_name: str) -> None:
        logger.info(f"Received {sig_name}, initiating shutdown")
        shutdown_event.set()

    try:
        loop.add_signal_handler(signal.SIGTERM, handle_signal, "SIGTERM")
        loop.add_signal_handler(signal.SIGINT, handle_signal, "SIGINT")
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        def signal_handler(sig: int, _frame: object) -> None:
            logger.info(f"Received signal {sig}, initiating shutdown")
            shutdown_event.set()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    try:
        logger.info("Claude Hook Event Effect Node ready")
        logger.info("Waiting for events on Kafka topic...")
        await shutdown_event.wait()

    except asyncio.CancelledError:
        logger.info("Event loop cancelled, shutting down")
        raise

    except Exception as e:
        logger.error(f"Node error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Cleanup
        logger.info("Shutting down...")

        try:
            loop.remove_signal_handler(signal.SIGTERM)
            loop.remove_signal_handler(signal.SIGINT)
        except (NotImplementedError, ValueError):
            pass

        # Unsubscribe from topic
        logger.info("Unsubscribing from Kafka topic...")
        await unsubscribe()

        # Close event bus
        logger.info("Closing event bus...")
        await event_bus.close()

        logger.info("Claude Hook Event Effect Node shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
