"""
Kafka Configuration for Intelligence Service

Manages Kafka connection and topic configuration from environment variables
with validated configuration models following ONEX patterns.
"""

import os
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Centralized configuration
try:
    from config import settings as parent_settings

    _DEFAULT_KAFKA_SERVERS = parent_settings.kafka_bootstrap_servers
except ImportError:
    _DEFAULT_KAFKA_SERVERS = "omninode-bridge-redpanda:9092"


class KafkaTopicConfig(BaseModel):
    """Configuration for Kafka codegen and intelligence topics."""

    # Codegen Request topics
    validate_request: str = Field(
        default="omninode.codegen.request.validate.v1",
        description="Topic for code validation requests",
    )
    analyze_request: str = Field(
        default="omninode.codegen.request.analyze.v1",
        description="Topic for code analysis requests",
    )
    pattern_request: str = Field(
        default="omninode.codegen.request.pattern.v1",
        description="Topic for pattern matching requests",
    )
    mixin_request: str = Field(
        default="omninode.codegen.request.mixin.v1",
        description="Topic for mixin application requests",
    )

    # Codegen Response topics
    validate_response: str = Field(
        default="omninode.codegen.response.validate.v1",
        description="Topic for code validation responses",
    )
    analyze_response: str = Field(
        default="omninode.codegen.response.analyze.v1",
        description="Topic for code analysis responses",
    )
    pattern_response: str = Field(
        default="omninode.codegen.response.pattern.v1",
        description="Topic for pattern matching responses",
    )
    mixin_response: str = Field(
        default="omninode.codegen.response.mixin.v1",
        description="Topic for mixin application responses",
    )

    # Intelligence Adapter topics
    intelligence_analysis_request: str = Field(
        default="dev.archon-intelligence.intelligence.code-analysis-requested.v1",
        description="Topic for intelligence code analysis requests",
    )
    intelligence_analysis_completed: str = Field(
        default="dev.archon-intelligence.intelligence.code-analysis-completed.v1",
        description="Topic for intelligence code analysis completed responses",
    )
    intelligence_analysis_failed: str = Field(
        default="dev.archon-intelligence.intelligence.code-analysis-failed.v1",
        description="Topic for intelligence code analysis failed responses",
    )

    # Tree + Stamping Integration topics (2025-10-24)
    tree_index_project_request: str = Field(
        default="dev.archon-intelligence.tree.index-project-requested.v1",
        description="Topic for tree index project requests",
    )
    tree_index_project_completed: str = Field(
        default="dev.archon-intelligence.tree.index-project-completed.v1",
        description="Topic for tree index project completed responses",
    )
    tree_index_project_failed: str = Field(
        default="dev.archon-intelligence.tree.index-project-failed.v1",
        description="Topic for tree index project failed responses",
    )
    tree_search_files_request: str = Field(
        default="dev.archon-intelligence.tree.search-files-requested.v1",
        description="Topic for tree search files requests",
    )
    tree_search_files_completed: str = Field(
        default="dev.archon-intelligence.tree.search-files-completed.v1",
        description="Topic for tree search files completed responses",
    )
    tree_search_files_failed: str = Field(
        default="dev.archon-intelligence.tree.search-files-failed.v1",
        description="Topic for tree search files failed responses",
    )
    tree_get_status_request: str = Field(
        default="dev.archon-intelligence.tree.get-status-requested.v1",
        description="Topic for tree get status requests",
    )
    tree_get_status_completed: str = Field(
        default="dev.archon-intelligence.tree.get-status-completed.v1",
        description="Topic for tree get status completed responses",
    )
    tree_get_status_failed: str = Field(
        default="dev.archon-intelligence.tree.get-status-failed.v1",
        description="Topic for tree get status failed responses",
    )
    tree_incremental_stamp_request: str = Field(
        default="dev.archon-intelligence.tree.incremental-stamp-requested.v1",
        description="Topic for tree incremental stamp requests",
    )
    tree_incremental_stamp_completed: str = Field(
        default="dev.archon-intelligence.tree.incremental-stamp-completed.v1",
        description="Topic for tree incremental stamp completed responses",
    )
    tree_incremental_stamp_failed: str = Field(
        default="dev.archon-intelligence.tree.incremental-stamp-failed.v1",
        description="Topic for tree incremental stamp failed responses",
    )


class KafkaConsumerConfig(BaseModel):
    """Configuration for Kafka consumer behavior."""

    group_id: str = Field(
        default="archon-intelligence", description="Consumer group ID"
    )
    auto_offset_reset: str = Field(
        default="earliest",
        description="Where to start consuming messages (earliest/latest)",
    )
    enable_auto_commit: bool = Field(
        default=True, description="Enable automatic offset commits"
    )
    max_poll_records: int = Field(
        default=500, ge=1, le=10000, description="Maximum records to fetch per poll"
    )
    session_timeout_ms: int = Field(
        default=30000,
        ge=1000,
        le=300000,
        description="Consumer session timeout in milliseconds",
    )

    @field_validator("auto_offset_reset")
    @classmethod
    def validate_auto_offset_reset(cls, v: str) -> str:
        """Validate auto_offset_reset value."""
        if v not in ("earliest", "latest"):
            raise ValueError("auto_offset_reset must be 'earliest' or 'latest'")
        return v


class KafkaConfig(BaseModel):
    """Complete Kafka configuration for Intelligence Service."""

    bootstrap_servers: str = Field(
        default=_DEFAULT_KAFKA_SERVERS,
        description="Kafka bootstrap servers from centralized config",
    )
    topics: KafkaTopicConfig = Field(
        default_factory=KafkaTopicConfig, description="Topic configuration"
    )
    consumer: KafkaConsumerConfig = Field(
        default_factory=KafkaConsumerConfig, description="Consumer configuration"
    )

    @field_validator("bootstrap_servers")
    @classmethod
    def validate_bootstrap_servers(cls, v: str) -> str:
        """Validate bootstrap servers format."""
        if not v or not v.strip():
            raise ValueError("bootstrap_servers cannot be empty")
        return v.strip()

    @classmethod
    def from_env(cls) -> "KafkaConfig":
        """
        Load Kafka configuration from environment variables.

        Environment Variables:
            # Connection
            KAFKA_BOOTSTRAP_SERVERS: Kafka bootstrap servers (default: omninode-bridge-redpanda:9092)
            KAFKA_CONSUMER_GROUP: Consumer group ID (default: archon-intelligence)

            # Consumer Behavior
            KAFKA_AUTO_OFFSET_RESET: Start position (earliest/latest, default: earliest)
            KAFKA_ENABLE_AUTO_COMMIT: Enable auto-commit (default: true)
            KAFKA_MAX_POLL_RECORDS: Max records per poll (default: 500)
            KAFKA_SESSION_TIMEOUT_MS: Session timeout (default: 30000)

            # Request Topics
            KAFKA_CODEGEN_VALIDATE_REQUEST: Validation request topic
            KAFKA_CODEGEN_ANALYZE_REQUEST: Analysis request topic
            KAFKA_CODEGEN_PATTERN_REQUEST: Pattern request topic
            KAFKA_CODEGEN_MIXIN_REQUEST: Mixin request topic

            # Response Topics
            KAFKA_CODEGEN_VALIDATE_RESPONSE: Validation response topic
            KAFKA_CODEGEN_ANALYZE_RESPONSE: Analysis response topic
            KAFKA_CODEGEN_PATTERN_RESPONSE: Pattern response topic
            KAFKA_CODEGEN_MIXIN_RESPONSE: Mixin response topic

            # Intelligence Adapter Topics
            KAFKA_INTELLIGENCE_ANALYSIS_REQUEST: Intelligence analysis request topic
            KAFKA_INTELLIGENCE_ANALYSIS_COMPLETED: Intelligence analysis completed topic
            KAFKA_INTELLIGENCE_ANALYSIS_FAILED: Intelligence analysis failed topic

            # Tree + Stamping Integration Topics (2025-10-24)
            KAFKA_TREE_INDEX_PROJECT_REQUEST: Tree index project request topic
            KAFKA_TREE_INDEX_PROJECT_COMPLETED: Tree index project completed topic
            KAFKA_TREE_INDEX_PROJECT_FAILED: Tree index project failed topic
            KAFKA_TREE_SEARCH_FILES_REQUEST: Tree search files request topic
            KAFKA_TREE_SEARCH_FILES_COMPLETED: Tree search files completed topic
            KAFKA_TREE_SEARCH_FILES_FAILED: Tree search files failed topic
            KAFKA_TREE_GET_STATUS_REQUEST: Tree get status request topic
            KAFKA_TREE_GET_STATUS_COMPLETED: Tree get status completed topic
            KAFKA_TREE_GET_STATUS_FAILED: Tree get status failed topic
            KAFKA_TREE_INCREMENTAL_STAMP_REQUEST: Tree incremental stamp request topic
            KAFKA_TREE_INCREMENTAL_STAMP_COMPLETED: Tree incremental stamp completed topic
            KAFKA_TREE_INCREMENTAL_STAMP_FAILED: Tree incremental stamp failed topic

        Returns:
            Complete Kafka configuration

        Raises:
            ValueError: If required environment variables are invalid
        """
        return cls(
            bootstrap_servers=os.getenv(
                "KAFKA_BOOTSTRAP_SERVERS", _DEFAULT_KAFKA_SERVERS
            ),
            topics=KafkaTopicConfig(
                validate_request=os.getenv(
                    "KAFKA_CODEGEN_VALIDATE_REQUEST",
                    "omninode.codegen.request.validate.v1",
                ),
                analyze_request=os.getenv(
                    "KAFKA_CODEGEN_ANALYZE_REQUEST",
                    "omninode.codegen.request.analyze.v1",
                ),
                pattern_request=os.getenv(
                    "KAFKA_CODEGEN_PATTERN_REQUEST",
                    "omninode.codegen.request.pattern.v1",
                ),
                mixin_request=os.getenv(
                    "KAFKA_CODEGEN_MIXIN_REQUEST", "omninode.codegen.request.mixin.v1"
                ),
                validate_response=os.getenv(
                    "KAFKA_CODEGEN_VALIDATE_RESPONSE",
                    "omninode.codegen.response.validate.v1",
                ),
                analyze_response=os.getenv(
                    "KAFKA_CODEGEN_ANALYZE_RESPONSE",
                    "omninode.codegen.response.analyze.v1",
                ),
                pattern_response=os.getenv(
                    "KAFKA_CODEGEN_PATTERN_RESPONSE",
                    "omninode.codegen.response.pattern.v1",
                ),
                mixin_response=os.getenv(
                    "KAFKA_CODEGEN_MIXIN_RESPONSE", "omninode.codegen.response.mixin.v1"
                ),
                # Intelligence Adapter Topics
                intelligence_analysis_request=os.getenv(
                    "KAFKA_INTELLIGENCE_ANALYSIS_REQUEST",
                    "dev.archon-intelligence.intelligence.code-analysis-requested.v1",
                ),
                intelligence_analysis_completed=os.getenv(
                    "KAFKA_INTELLIGENCE_ANALYSIS_COMPLETED",
                    "dev.archon-intelligence.intelligence.code-analysis-completed.v1",
                ),
                intelligence_analysis_failed=os.getenv(
                    "KAFKA_INTELLIGENCE_ANALYSIS_FAILED",
                    "dev.archon-intelligence.intelligence.code-analysis-failed.v1",
                ),
                # Tree + Stamping Integration Topics (2025-10-24)
                tree_index_project_request=os.getenv(
                    "KAFKA_TREE_INDEX_PROJECT_REQUEST",
                    "dev.archon-intelligence.tree.index-project-requested.v1",
                ),
                tree_index_project_completed=os.getenv(
                    "KAFKA_TREE_INDEX_PROJECT_COMPLETED",
                    "dev.archon-intelligence.tree.index-project-completed.v1",
                ),
                tree_index_project_failed=os.getenv(
                    "KAFKA_TREE_INDEX_PROJECT_FAILED",
                    "dev.archon-intelligence.tree.index-project-failed.v1",
                ),
                tree_search_files_request=os.getenv(
                    "KAFKA_TREE_SEARCH_FILES_REQUEST",
                    "dev.archon-intelligence.tree.search-files-requested.v1",
                ),
                tree_search_files_completed=os.getenv(
                    "KAFKA_TREE_SEARCH_FILES_COMPLETED",
                    "dev.archon-intelligence.tree.search-files-completed.v1",
                ),
                tree_search_files_failed=os.getenv(
                    "KAFKA_TREE_SEARCH_FILES_FAILED",
                    "dev.archon-intelligence.tree.search-files-failed.v1",
                ),
                tree_get_status_request=os.getenv(
                    "KAFKA_TREE_GET_STATUS_REQUEST",
                    "dev.archon-intelligence.tree.get-status-requested.v1",
                ),
                tree_get_status_completed=os.getenv(
                    "KAFKA_TREE_GET_STATUS_COMPLETED",
                    "dev.archon-intelligence.tree.get-status-completed.v1",
                ),
                tree_get_status_failed=os.getenv(
                    "KAFKA_TREE_GET_STATUS_FAILED",
                    "dev.archon-intelligence.tree.get-status-failed.v1",
                ),
                tree_incremental_stamp_request=os.getenv(
                    "KAFKA_TREE_INCREMENTAL_STAMP_REQUEST",
                    "dev.archon-intelligence.tree.incremental-stamp-requested.v1",
                ),
                tree_incremental_stamp_completed=os.getenv(
                    "KAFKA_TREE_INCREMENTAL_STAMP_COMPLETED",
                    "dev.archon-intelligence.tree.incremental-stamp-completed.v1",
                ),
                tree_incremental_stamp_failed=os.getenv(
                    "KAFKA_TREE_INCREMENTAL_STAMP_FAILED",
                    "dev.archon-intelligence.tree.incremental-stamp-failed.v1",
                ),
            ),
            consumer=KafkaConsumerConfig(
                group_id=os.getenv("KAFKA_CONSUMER_GROUP", "archon-intelligence"),
                auto_offset_reset=os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest"),
                enable_auto_commit=os.getenv("KAFKA_ENABLE_AUTO_COMMIT", "true").lower()
                in ("true", "1", "yes"),
                max_poll_records=int(os.getenv("KAFKA_MAX_POLL_RECORDS", "500")),
                session_timeout_ms=int(os.getenv("KAFKA_SESSION_TIMEOUT_MS", "30000")),
            ),
        )

    def to_consumer_config(self) -> dict:
        """
        Convert to aiokafka consumer configuration dictionary.

        Returns:
            Dict suitable for AIOKafkaConsumer initialization
        """
        return {
            "bootstrap_servers": self.bootstrap_servers,
            "group_id": self.consumer.group_id,
            "auto_offset_reset": self.consumer.auto_offset_reset,
            "enable_auto_commit": self.consumer.enable_auto_commit,
            "max_poll_records": self.consumer.max_poll_records,
            "session_timeout_ms": self.consumer.session_timeout_ms,
        }


# Global config instance (lazy loaded)
_kafka_config: Optional[KafkaConfig] = None


def get_kafka_config() -> KafkaConfig:
    """
    Get the global Kafka configuration instance.

    Returns:
        Global Kafka configuration instance

    Raises:
        ValueError: If configuration cannot be loaded
    """
    global _kafka_config
    if _kafka_config is None:
        _kafka_config = KafkaConfig.from_env()
    return _kafka_config


def reset_kafka_config() -> None:
    """Reset the global Kafka configuration instance (primarily for testing)."""
    global _kafka_config
    _kafka_config = None
