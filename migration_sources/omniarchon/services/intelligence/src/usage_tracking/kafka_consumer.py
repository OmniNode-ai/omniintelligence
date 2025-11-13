"""
Kafka Consumer for Pattern Usage Tracking

Subscribes to Kafka topics and routes events to UsageTracker:
- agent-manifest-injections: Track patterns in manifests
- agent-actions: Track patterns used in actions
- agent-routing-decisions: Track patterns influencing routing

Created: 2025-10-28
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional
from uuid import UUID

import asyncpg
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError
from prometheus_client import Counter, Gauge

from .usage_tracker import UsageTracker


# Add project root to path for config imports
def _find_project_root() -> Path:
    """
    Find project root by searching for .git directory (repository root).

    Walks up the directory tree from this file's location until .git is found.
    This ensures we find the repository root, not just a service-level pyproject.toml.
    Falls back to pyproject.toml if .git is not found.
    """
    current = Path(__file__).resolve().parent
    # First pass: look for .git (repository root)
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    # Second pass: fall back to pyproject.toml
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    # Final fallback to current directory if no marker found
    return current


project_root = _find_project_root()
sys.path.insert(0, str(project_root))
from config.kafka_helper import KAFKA_DOCKER_SERVERS  # Docker services use internal DNS

logger = logging.getLogger(__name__)

# Prometheus metrics
events_consumed = Counter(
    "usage_tracking_events_consumed_total",
    "Total events consumed for usage tracking",
    ["topic", "status"],
)

events_processing_errors = Counter(
    "usage_tracking_processing_errors_total",
    "Total event processing errors",
    ["topic", "error_type"],
)

consumer_lag = Gauge(
    "usage_tracking_consumer_lag",
    "Consumer lag for usage tracking topics",
    ["topic", "partition"],
)


class UsageTrackingConsumer:
    """
    Kafka consumer for pattern usage tracking.

    Subscribes to multiple topics and routes events to UsageTracker.
    Implements graceful shutdown and error handling.
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        bootstrap_servers: Optional[str] = None,
        group_id: str = "pattern-usage-tracking",
    ):
        """
        Initialize usage tracking consumer.

        Args:
            db_pool: Database connection pool
            bootstrap_servers: Kafka bootstrap servers (defaults to env var)
            group_id: Consumer group ID
        """
        self.db_pool = db_pool
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            KAFKA_DOCKER_SERVERS,  # Use centralized config for Docker context
        )
        self.group_id = group_id

        # Topics to subscribe to
        self.topics = [
            "agent-manifest-injections",
            "agent-actions",
            "agent-routing-decisions",
        ]

        self.consumer: Optional[AIOKafkaConsumer] = None
        self.usage_tracker = UsageTracker(db_pool)
        self._running = False
        self._consume_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start Kafka consumer and usage tracker."""
        if self._running:
            logger.warning("Usage tracking consumer already running")
            return

        logger.info(
            f"Starting usage tracking consumer: "
            f"bootstrap_servers={self.bootstrap_servers}, "
            f"group_id={self.group_id}, "
            f"topics={self.topics}"
        )

        try:
            # Create consumer
            self.consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="latest",  # Start from latest for new consumer
                enable_auto_commit=True,
                auto_commit_interval_ms=5000,
            )

            # Start consumer
            await self.consumer.start()
            logger.info(f"Connected to Kafka: topics={self.topics}")

            # Start usage tracker
            await self.usage_tracker.start()

            # Start consuming
            self._running = True
            self._consume_task = asyncio.create_task(self._consume_loop())

            logger.info("Usage tracking consumer started successfully")

        except KafkaConnectionError as e:
            logger.error(f"Failed to connect to Kafka: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to start usage tracking consumer: {e}", exc_info=True)
            raise

    async def stop(self):
        """Stop Kafka consumer gracefully."""
        if not self._running:
            return

        logger.info("Stopping usage tracking consumer...")
        self._running = False

        # Cancel consume task
        if self._consume_task and not self._consume_task.done():
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass

        # Stop usage tracker (flush pending updates)
        await self.usage_tracker.stop()

        # Stop consumer
        if self.consumer:
            await self.consumer.stop()

        logger.info("Usage tracking consumer stopped")

    async def _consume_loop(self):
        """Main consume loop."""
        logger.info("Starting consume loop")

        try:
            async for msg in self.consumer:
                try:
                    await self._process_message(msg)
                    events_consumed.labels(topic=msg.topic, status="success").inc()

                except Exception as e:
                    logger.error(
                        f"Error processing message from {msg.topic}: {e}",
                        exc_info=True,
                    )
                    events_consumed.labels(topic=msg.topic, status="error").inc()
                    events_processing_errors.labels(
                        topic=msg.topic, error_type=type(e).__name__
                    ).inc()

        except asyncio.CancelledError:
            logger.info("Consume loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in consume loop: {e}", exc_info=True)
            raise

    async def _process_message(self, msg):
        """
        Process single Kafka message.

        Routes message to appropriate handler based on topic.

        Args:
            msg: Kafka message
        """
        topic = msg.topic
        data = msg.value

        # Extract common fields
        agent_name = data.get("agent_name", "unknown")
        correlation_id_str = data.get("correlation_id")

        # Convert correlation_id to UUID
        try:
            correlation_id = (
                UUID(correlation_id_str) if correlation_id_str else UUID(int=0)
            )
        except (ValueError, TypeError):
            correlation_id = UUID(int=0)

        # Route to appropriate handler
        if topic == "agent-manifest-injections":
            await self._handle_manifest_injection(data, agent_name, correlation_id)

        elif topic == "agent-actions":
            await self._handle_agent_action(data, agent_name, correlation_id)

        elif topic == "agent-routing-decisions":
            await self._handle_routing_decision(data, agent_name, correlation_id)

        else:
            logger.warning(f"Unknown topic: {topic}")

    async def _handle_manifest_injection(
        self, data: dict, agent_name: str, correlation_id: UUID
    ):
        """
        Handle agent-manifest-injections event.

        Extracts patterns from manifest and tracks usage.

        Args:
            data: Event data
            agent_name: Agent name
            correlation_id: Correlation ID
        """
        # Extract patterns from manifest data
        patterns = []

        # Check different possible locations for patterns
        if "patterns" in data:
            patterns = data["patterns"]
        elif "manifest" in data and isinstance(data["manifest"], dict):
            manifest = data["manifest"]
            if "patterns" in manifest:
                patterns = manifest["patterns"]

        # Also check pattern_count to validate
        pattern_count = data.get("patterns_count", 0)
        if pattern_count > 0 and not patterns:
            logger.warning(
                f"Manifest injection has pattern_count={pattern_count} "
                f"but no patterns found in data. agent={agent_name}, "
                f"correlation_id={correlation_id}"
            )

        if patterns:
            await self.usage_tracker.track_manifest_usage(
                patterns=patterns,
                agent_name=agent_name,
                correlation_id=correlation_id,
            )

    async def _handle_agent_action(
        self, data: dict, agent_name: str, correlation_id: UUID
    ):
        """
        Handle agent-actions event.

        Tracks patterns referenced in agent tool calls.

        Args:
            data: Event data
            agent_name: Agent name
            correlation_id: Correlation ID
        """
        await self.usage_tracker.track_action_usage(
            action_data=data,
            agent_name=agent_name,
            correlation_id=correlation_id,
        )

    async def _handle_routing_decision(
        self, data: dict, agent_name: str, correlation_id: UUID
    ):
        """
        Handle agent-routing-decisions event.

        Tracks patterns that influenced routing decision.

        Args:
            data: Event data
            agent_name: Agent name (selected agent)
            correlation_id: Correlation ID
        """
        # Use selected_agent if available (more accurate)
        if "selected_agent" in data:
            agent_name = data["selected_agent"]

        await self.usage_tracker.track_routing_usage(
            routing_data=data,
            agent_name=agent_name,
            correlation_id=correlation_id,
        )


# Standalone runner for testing
async def main():
    """Run usage tracking consumer standalone."""
    import os

    # Database connection
    db_dsn = (
        f"postgresql://{os.getenv('DB_USER', 'postgres')}:"
        f"{os.getenv('DB_PASSWORD', 'omninode_remote_2024_secure')}@"
        f"{os.getenv('DB_HOST', '192.168.86.200')}:"
        f"{os.getenv('DB_PORT', '5436')}/"
        f"{os.getenv('DB_NAME', 'omninode_bridge')}"
    )

    # Create database pool
    db_pool = await asyncpg.create_pool(db_dsn, min_size=2, max_size=10)

    # Create and start consumer
    consumer = UsageTrackingConsumer(db_pool)

    try:
        await consumer.start()

        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await consumer.stop()
        await db_pool.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
