# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Feedback Effect Entry Point.

This module wires EventBusKafka for real Kafka event consumption:
    python -m omniintelligence.nodes.node_pattern_feedback_effect

Environment Variables:
    KAFKA_BOOTSTRAP_SERVERS: Kafka bootstrap servers (required)
        - Docker: omninode-bridge-redpanda:9092
        - Host scripts: 192.168.86.200:29092
    KAFKA_ENVIRONMENT: Environment prefix for topics (default: dev)
    LOG_LEVEL: Logging level (default: INFO)

    PostgreSQL (required):
    POSTGRES_HOST: PostgreSQL host (default: 192.168.86.200)
    POSTGRES_PORT: PostgreSQL port (default: 5436)
    POSTGRES_DATABASE: Database name (default: omninode_bridge)
    POSTGRES_USER: Database user (default: postgres)
    POSTGRES_PASSWORD: Database password (required)

This node subscribes to:
    {env}.onex.cmd.omniintelligence.session-outcome.v1

Reference:
    - OMN-1829: Wire RuntimeHostProcess for real Kafka event consumption
    - OMN-1678: Rolling window metric updates for session outcomes
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
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
# Database Connection
# =============================================================================


async def create_db_connection() -> Any:
    """Create asyncpg database connection from environment variables.

    Returns:
        asyncpg.Connection instance.

    Raises:
        RuntimeError: If POSTGRES_PASSWORD is not set.
        asyncpg.PostgresError: If connection fails.
    """
    import asyncpg

    host = os.getenv("POSTGRES_HOST", "192.168.86.200")
    port = int(os.getenv("POSTGRES_PORT", "5436"))
    database = os.getenv("POSTGRES_DATABASE", "omninode_bridge")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD")

    if not password:
        raise RuntimeError(
            "POSTGRES_PASSWORD environment variable is required. "
            "Set it before running the node."
        )

    logger.info(f"Connecting to PostgreSQL at {host}:{port}/{database}")

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    logger.info("PostgreSQL connection established")
    return conn


# =============================================================================
# Event Processing
# =============================================================================


async def create_message_handler(
    db_connection: Any,
) -> Any:
    """Create a message handler closure for event processing.

    Returns an async callback that can be passed to event_bus.subscribe().
    """
    from omnibase_core.integrations.claude_code import (
        ClaudeCodeSessionOutcome,
        ClaudeSessionOutcome,
    )

    from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
        event_to_handler_args,
        record_session_outcome,
    )
    from omniintelligence.nodes.node_pattern_feedback_effect.registry import (
        RegistryPatternFeedbackEffect,
    )

    # Register the database connection as the repository
    RegistryPatternFeedbackEffect.register_repository(db_connection)

    async def on_message(msg: ModelEventMessage) -> None:
        """Process incoming Kafka message."""
        try:
            # Deserialize message value
            if msg.value is None:
                logger.warning("Received message with null value, skipping")
                return

            payload_dict = json.loads(msg.value.decode("utf-8"))
            logger.debug(f"Received session outcome event: {payload_dict}")

            # Convert to ClaudeSessionOutcome
            # Parse session_id
            session_id_str = payload_dict.get("session_id")
            if not session_id_str:
                logger.warning("No session_id in event, skipping")
                return

            try:
                session_id = UUID(session_id_str)
            except ValueError:
                logger.warning(f"Invalid session_id: {session_id_str}, skipping")
                return

            # Parse outcome enum
            outcome_str = payload_dict.get("outcome", "unknown")
            try:
                outcome = ClaudeCodeSessionOutcome(outcome_str)
            except ValueError:
                # Try uppercase
                try:
                    outcome = ClaudeCodeSessionOutcome[outcome_str.upper()]
                except KeyError:
                    logger.warning(f"Unknown outcome: {outcome_str}, using UNKNOWN")
                    outcome = ClaudeCodeSessionOutcome.UNKNOWN

            # Parse correlation_id
            correlation_id_str = payload_dict.get("correlation_id")
            correlation_id = UUID(correlation_id_str) if correlation_id_str else None

            # Parse error if present
            from omnibase_core.models.services import ModelErrorDetails

            error_data = payload_dict.get("error")
            error: ModelErrorDetails[Any] | None = None
            if error_data and isinstance(error_data, dict):
                error = ModelErrorDetails(
                    error_code=error_data.get("code", "UNKNOWN_ERROR"),
                    error_type=error_data.get("type", "runtime"),
                    error_message=error_data.get("message", "Unknown error"),
                    component=error_data.get("component"),
                )

            # Create event model
            event = ClaudeSessionOutcome(
                session_id=session_id,
                outcome=outcome,
                correlation_id=correlation_id,
                error=error,
            )

            # Convert to handler args
            handler_args = event_to_handler_args(event)

            # Process event via handler
            result = await record_session_outcome(
                session_id=handler_args["session_id"],
                success=handler_args["success"],
                failure_reason=handler_args["failure_reason"],
                repository=db_connection,
                correlation_id=handler_args["correlation_id"],
            )

            logger.info(
                f"Processed session outcome: status={result.status.value}, "
                f"session={session_id}, injections_updated={result.injections_updated}, "
                f"patterns_updated={result.patterns_updated}"
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
    """Run the Pattern Feedback Effect node with real Kafka consumption."""
    logger.info("=" * 60)
    logger.info("Starting Pattern Feedback Effect Node")
    logger.info("=" * 60)

    # Load configuration from environment
    kafka_env = os.getenv("KAFKA_ENVIRONMENT", "dev")

    # Topic configuration from contract.yaml
    subscribe_topic_suffix = "onex.cmd.omniintelligence.session-outcome.v1"
    subscribe_topic = f"{kafka_env}.{subscribe_topic_suffix}"

    logger.info(f"Kafka environment: {kafka_env}")
    logger.info(f"Subscribe topic: {subscribe_topic}")

    # Import infrastructure components
    from omnibase_infra.event_bus.event_bus_kafka import EventBusKafka
    from omnibase_infra.models import ModelNodeIdentity

    # Create database connection first
    logger.info("Creating PostgreSQL connection...")
    db_connection = await create_db_connection()

    # Create event bus from environment
    logger.info("Creating EventBusKafka from environment...")
    event_bus = EventBusKafka.default()
    await event_bus.start()
    logger.info("EventBusKafka started successfully")

    # Create node identity for subscription
    node_identity = ModelNodeIdentity(
        env=kafka_env,
        service="omniintelligence",
        node_name="pattern_feedback_effect",
        version="1.0.0",
    )

    # Create message handler
    on_message = await create_message_handler(
        db_connection=db_connection,
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
        logger.info("Pattern Feedback Effect Node ready")
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

        # Close database connection
        logger.info("Closing PostgreSQL connection...")
        await db_connection.close()

        # Clear registry
        from omniintelligence.nodes.node_pattern_feedback_effect.registry import (
            RegistryPatternFeedbackEffect,
        )

        RegistryPatternFeedbackEffect.clear()

        logger.info("Pattern Feedback Effect Node shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
