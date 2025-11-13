"""
Configuration management for intelligence consumer service.

Uses Pydantic settings for environment variable management with
validation and type safety.
"""

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Import parent configuration for defaults
try:
    from config import settings as parent_settings

    _DEFAULT_KAFKA_SERVERS = parent_settings.kafka_bootstrap_servers
except ImportError:
    # Fallback if parent config not available
    _DEFAULT_KAFKA_SERVERS = "omninode-bridge-redpanda:9092"


class ConsumerConfig(BaseSettings):
    """Configuration for intelligence consumer service."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Kafka Configuration
    kafka_bootstrap_servers: str = Field(
        default=_DEFAULT_KAFKA_SERVERS,
        description="Kafka bootstrap servers from centralized config",
    )
    kafka_topic_prefix: str = Field(
        default="dev.archon-intelligence", description="Kafka topic prefix"
    )
    kafka_consumer_group: str = Field(
        default="archon-intelligence-consumer-group",
        description="Kafka consumer group ID",
    )
    kafka_auto_offset_reset: str = Field(
        default="earliest", description="Auto offset reset strategy"
    )
    kafka_max_poll_records: int = Field(
        default=10, description="Maximum records to poll per batch"
    )
    kafka_enable_auto_commit: bool = Field(
        default=False, description="Enable auto commit (disabled for manual control)"
    )
    kafka_session_timeout_ms: int = Field(
        default=45000,
        description="Kafka session timeout in milliseconds (increased from default 10s to prevent rebalancing during slow processing)",
    )
    kafka_heartbeat_interval_ms: int = Field(
        default=10000,
        description="Kafka heartbeat interval in milliseconds (increased from default 3s)",
    )
    kafka_max_poll_interval_ms: int = Field(
        default=600000,
        description="Maximum time between poll() calls before rebalance (10min to allow 180s intelligence processing + queue delays)",
    )

    # Intelligence Service Configuration
    intelligence_service_url: str = Field(
        default="http://archon-intelligence:8053",
        description="Intelligence service base URL",
    )
    intelligence_timeout: int = Field(
        default=900,
        description="Intelligence service timeout in seconds (900s to match intelligence service parallelization capacity for complex documents with quality assessment against 25K+ patterns)",
    )

    # Memgraph Configuration
    memgraph_uri: str = Field(
        default="bolt://memgraph:7687", description="Memgraph connection URI"
    )
    memgraph_username: str = Field(
        default="", description="Memgraph username (optional)"
    )
    memgraph_password: str = Field(
        default="", description="Memgraph password (optional)"
    )

    # Retry Configuration
    max_retry_attempts: int = Field(
        default=3, description="Maximum retry attempts before DLQ"
    )
    retry_backoff_base: int = Field(
        default=2, description="Base delay for exponential backoff (seconds)"
    )
    retry_backoff_max: int = Field(
        default=60, description="Maximum backoff delay (seconds)"
    )

    # Circuit Breaker Configuration
    circuit_breaker_enabled: bool = Field(
        default=True, description="Enable/disable circuit breaker protection"
    )
    circuit_breaker_threshold: int = Field(
        default=10,
        description="Consecutive failures to open circuit (increased tolerance for large file batch processing)",
    )
    circuit_breaker_timeout: int = Field(
        default=30, description="Seconds before attempting half-open"
    )
    circuit_breaker_success_threshold: int = Field(
        default=3, description="Consecutive successes to close circuit"
    )

    # Health Check Configuration
    health_check_port: int = Field(
        default=8080, description="Health check HTTP server port"
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    log_format: str = Field(default="json", description="Log format (json or console)")

    # Performance Configuration
    processing_concurrency: int = Field(
        default=5, description="Number of concurrent message processors"
    )
    shutdown_timeout: int = Field(
        default=30, description="Graceful shutdown timeout (seconds)"
    )

    # Instance Configuration (for horizontal scaling)
    instance_id: str = Field(
        default="default",
        description="Instance identifier for multi-instance deployments",
    )
    worker_count: int = Field(
        default=8, description="Number of worker threads per instance"
    )
    queue_size: int = Field(
        default=100, description="Internal queue size for message buffering"
    )

    @property
    def enrichment_topic(self) -> str:
        """Get the enrichment topic name."""
        return f"{self.kafka_topic_prefix}.enrich-document.v1"

    @property
    def code_analysis_topic(self) -> str:
        """Get the code-analysis request topic name."""
        return f"{self.kafka_topic_prefix}.intelligence.code-analysis-requested.v1"

    @property
    def code_analysis_completed_topic(self) -> str:
        """Get the code-analysis completion topic name."""
        return f"{self.kafka_topic_prefix}.intelligence.code-analysis-completed.v1"

    @property
    def code_analysis_failed_topic(self) -> str:
        """Get the code-analysis failed topic name."""
        return f"{self.kafka_topic_prefix}.intelligence.code-analysis-failed.v1"

    @property
    def manifest_requested_topic(self) -> str:
        """Get the manifest intelligence request topic name."""
        return f"{self.kafka_topic_prefix}.intelligence.manifest.requested.v1"

    @property
    def manifest_completed_topic(self) -> str:
        """Get the manifest intelligence completion topic name."""
        return f"{self.kafka_topic_prefix}.intelligence.manifest.completed.v1"

    @property
    def manifest_failed_topic(self) -> str:
        """Get the manifest intelligence failed topic name."""
        return f"{self.kafka_topic_prefix}.intelligence.manifest.failed.v1"

    @property
    def completion_topic(self) -> str:
        """Get the completion topic name."""
        return f"{self.kafka_topic_prefix}.enrich-document-completed.v1"

    @property
    def dlq_topic(self) -> str:
        """Get the DLQ topic name."""
        return f"{self.kafka_topic_prefix}.enrich-document-dlq.v1"

    def get_subscribed_topics(self) -> list[str]:
        """Get list of topics to subscribe to."""
        return [
            self.enrichment_topic,
            self.code_analysis_topic,
            self.manifest_requested_topic,
        ]

    def get_kafka_config(self) -> dict:
        """Get Kafka consumer configuration as dict."""
        return {
            "bootstrap_servers": self.kafka_bootstrap_servers,
            "group_id": self.kafka_consumer_group,
            "auto_offset_reset": self.kafka_auto_offset_reset,
            "enable_auto_commit": self.kafka_enable_auto_commit,
            "max_poll_records": self.kafka_max_poll_records,
            "session_timeout_ms": self.kafka_session_timeout_ms,
            "heartbeat_interval_ms": self.kafka_heartbeat_interval_ms,
            "max_poll_interval_ms": self.kafka_max_poll_interval_ms,
        }


# Singleton instance
_config: Optional[ConsumerConfig] = None


def get_config() -> ConsumerConfig:
    """Get or create configuration singleton."""
    global _config
    if _config is None:
        _config = ConsumerConfig()
    return _config
