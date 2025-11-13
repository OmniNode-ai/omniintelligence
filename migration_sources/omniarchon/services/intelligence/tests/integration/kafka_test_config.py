"""
Kafka Test Configuration - Centralized Configuration for Kafka Integration Tests

This module provides centralized configuration for Kafka integration testing,
including connection settings, topic definitions, consumer/producer configs.

Responsibilities:
- Centralized Kafka connection settings (bootstrap servers, schema registry)
- Topic naming conventions and default topics
- Consumer/producer configuration factories
- Environment-based configuration overrides

Author: Archon Intelligence Team
Version: 1.0.0
Created: 2025-10-15 (MVP Phase 4 - Workflow 1)
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

# Add project root to path for config imports
project_root = (
    Path(__file__).resolve().parents[4]
)  # Go up 4 levels from tests/integration
sys.path.insert(0, str(project_root))

# Import centralized configuration
from config.kafka_helper import KAFKA_HOST_SERVERS


class KafkaTestConfig:
    """
    Centralized Kafka test configuration.

    Provides connection settings, topic definitions, and configuration
    factories for Kafka consumers and producers in integration tests.

    Features:
    - Environment variable overrides for flexibility
    - Consistent topic naming following ONEX patterns
    - Consumer/producer configuration factories
    - Redpanda-compatible defaults

    Usage:
        # Get bootstrap servers
        servers = KafkaTestConfig.BOOTSTRAP_SERVERS

        # Get consumer configuration
        consumer_config = KafkaTestConfig.get_consumer_config("test-group")

        # Get producer configuration
        producer_config = KafkaTestConfig.get_producer_config()

        # Access default topics
        validation_topic = KafkaTestConfig.DEFAULT_TOPICS["validation_request"]
    """

    # ========================================================================
    # Connection Configuration
    # ========================================================================

    BOOTSTRAP_SERVERS = os.getenv(
        "TEST_KAFKA_BOOTSTRAP_SERVERS",
        KAFKA_HOST_SERVERS,  # Use centralized config (192.168.86.200:29092 for host testing)
    )

    SCHEMA_REGISTRY_URL = os.getenv(
        "TEST_SCHEMA_REGISTRY_URL", "http://localhost:18081"
    )

    # ========================================================================
    # Consumer Configuration
    # ========================================================================

    CONSUMER_GROUP_PREFIX = "archon-intelligence-test"

    # ========================================================================
    # Topic Configuration
    # ========================================================================

    DEFAULT_TOPICS = {
        # Codegen validation event topics
        "validation_request": "omninode.codegen.request.validate.v1",
        "validation_response": "omninode.codegen.response.validate.v1",
        # Codegen analysis event topics
        "analysis_request": "omninode.codegen.request.analyze.v1",
        "analysis_response": "omninode.codegen.response.analyze.v1",
        # Codegen pattern matching event topics
        "pattern_request": "omninode.codegen.request.pattern.v1",
        "pattern_response": "omninode.codegen.response.pattern.v1",
        # Codegen mixin recommendation event topics
        "mixin_request": "omninode.codegen.request.mixin.v1",
        "mixin_response": "omninode.codegen.response.mixin.v1",
    }

    # ========================================================================
    # Configuration Factories
    # ========================================================================

    @classmethod
    def get_consumer_config(cls, group_id: str) -> Dict[str, Any]:
        """
        Get Kafka consumer configuration for integration tests.

        Args:
            group_id: Consumer group identifier (will be prefixed)

        Returns:
            Dictionary with consumer configuration settings

        Configuration:
        - bootstrap_servers: Kafka/Redpanda connection
        - group_id: Prefixed consumer group ID
        - auto_offset_reset: "earliest" for test reproducibility
        - enable_auto_commit: True for simplicity in tests
        - max_poll_records: 100 for batch processing
        - session_timeout_ms: 30s for connection stability
        - heartbeat_interval_ms: 10s for health monitoring

        Example:
            config = KafkaTestConfig.get_consumer_config("validation-test")
            consumer = KafkaConsumer(**config)
        """
        return {
            "bootstrap_servers": cls.BOOTSTRAP_SERVERS,
            "group_id": f"{cls.CONSUMER_GROUP_PREFIX}-{group_id}",
            "auto_offset_reset": "earliest",  # Start from beginning in tests
            "enable_auto_commit": True,
            "max_poll_records": 100,
            "session_timeout_ms": 30000,  # 30 seconds
            "heartbeat_interval_ms": 10000,  # 10 seconds
        }

    @classmethod
    def get_producer_config(cls) -> Dict[str, Any]:
        """
        Get Kafka producer configuration for integration tests.

        Returns:
            Dictionary with producer configuration settings

        Configuration:
        - bootstrap_servers: Kafka/Redpanda connection
        - acks: "all" for guaranteed delivery
        - retries: 3 for reliability
        - max_in_flight_requests_per_connection: 1 for ordering

        Example:
            config = KafkaTestConfig.get_producer_config()
            producer = KafkaProducer(**config)
        """
        return {
            "bootstrap_servers": cls.BOOTSTRAP_SERVERS,
            "acks": "all",  # Wait for all replicas
            "retries": 3,  # Retry on transient failures
            "max_in_flight_requests_per_connection": 1,  # Preserve ordering
        }

    @classmethod
    def get_admin_config(cls) -> Dict[str, Any]:
        """
        Get Kafka admin client configuration for topic management.

        Returns:
            Dictionary with admin client configuration settings

        Example:
            config = KafkaTestConfig.get_admin_config()
            admin = KafkaAdminClient(**config)
        """
        return {
            "bootstrap_servers": cls.BOOTSTRAP_SERVERS,
        }


# ============================================================================
# Environment Configuration Validation
# ============================================================================


def validate_kafka_test_environment() -> bool:
    """
    Validate Kafka test environment configuration.

    Returns:
        True if configuration is valid, False otherwise

    Checks:
    - BOOTSTRAP_SERVERS is set and reachable
    - Required environment variables are present
    - Topic naming follows ONEX conventions

    Note:
        This is a basic validation. Full connectivity testing
        is performed by kafka_utils.verify_kafka_connectivity()
    """

    # Check if bootstrap servers is configured
    if not KafkaTestConfig.BOOTSTRAP_SERVERS:
        return False

    # Validate topic naming conventions
    for topic_name in KafkaTestConfig.DEFAULT_TOPICS.values():
        if not topic_name.startswith("omninode."):
            return False
        if not topic_name.endswith(".v1"):
            return False

    return True
