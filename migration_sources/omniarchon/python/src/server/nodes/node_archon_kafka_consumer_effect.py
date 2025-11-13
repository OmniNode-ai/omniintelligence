"""
Node Archon Kafka Consumer Effect - Stub Implementation
"""

import os
from typing import Optional

from pydantic import BaseModel, ConfigDict

# Centralized configuration
try:
    from config import settings

    _DEFAULT_KAFKA_SERVERS = settings.kafka_bootstrap_servers
except ImportError:
    _DEFAULT_KAFKA_SERVERS = "omninode-bridge-redpanda:9092"


class ModelConsumerConfig(BaseModel):
    """Stub implementation for consumer configuration."""

    model_config = ConfigDict(extra="allow")

    bootstrap_servers: str = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", _DEFAULT_KAFKA_SERVERS
    )
    group_id: str = "archon-consumer"
    consumer_group: str = "archon-consumer-group"
    topic_patterns: list[str] = ["dev.omninode_bridge.onex.evt.*.v1"]
    auto_offset_reset: str = "latest"


class NodeArchonKafkaConsumerEffect:
    """Stub implementation for Kafka consumer effect node."""

    def __init__(self, config: Optional[ModelConsumerConfig] = None):
        self.config = config or ModelConsumerConfig()
        self.is_running = False

    def start(self):
        """Start the consumer."""
        self.is_running = True

    def stop(self):
        """Stop the consumer."""
        self.is_running = False

    def is_healthy(self) -> bool:
        """Check if consumer is healthy."""
        return self.is_running
