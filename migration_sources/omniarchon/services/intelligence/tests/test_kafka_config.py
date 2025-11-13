"""
Tests for Kafka Configuration Module

Validates that configuration loads correctly from environment variables
and provides proper defaults.
"""

import os

import pytest
from src.config.kafka_config import (
    KafkaConfig,
    KafkaConsumerConfig,
    KafkaTopicConfig,
    get_kafka_config,
    reset_kafka_config,
)


class TestKafkaTopicConfig:
    """Tests for KafkaTopicConfig."""

    def test_default_values(self):
        """Test default topic names."""
        config = KafkaTopicConfig()

        # Request topics
        assert config.validate_request == "omninode.codegen.request.validate.v1"
        assert config.analyze_request == "omninode.codegen.request.analyze.v1"
        assert config.pattern_request == "omninode.codegen.request.pattern.v1"
        assert config.mixin_request == "omninode.codegen.request.mixin.v1"

        # Response topics
        assert config.validate_response == "omninode.codegen.response.validate.v1"
        assert config.analyze_response == "omninode.codegen.response.analyze.v1"
        assert config.pattern_response == "omninode.codegen.response.pattern.v1"
        assert config.mixin_response == "omninode.codegen.response.mixin.v1"


class TestKafkaConsumerConfig:
    """Tests for KafkaConsumerConfig."""

    def test_default_values(self):
        """Test default consumer configuration."""
        config = KafkaConsumerConfig()

        assert config.group_id == "archon-intelligence"
        assert config.auto_offset_reset == "earliest"
        assert config.enable_auto_commit is True
        assert config.max_poll_records == 500
        assert config.session_timeout_ms == 30000

    def test_auto_offset_reset_validation(self):
        """Test validation of auto_offset_reset."""
        # Valid values
        config = KafkaConsumerConfig(auto_offset_reset="earliest")
        assert config.auto_offset_reset == "earliest"

        config = KafkaConsumerConfig(auto_offset_reset="latest")
        assert config.auto_offset_reset == "latest"

        # Invalid value
        with pytest.raises(ValueError, match="must be 'earliest' or 'latest'"):
            KafkaConsumerConfig(auto_offset_reset="invalid")

    def test_max_poll_records_validation(self):
        """Test validation of max_poll_records bounds."""
        # Valid values
        config = KafkaConsumerConfig(max_poll_records=1)
        assert config.max_poll_records == 1

        config = KafkaConsumerConfig(max_poll_records=10000)
        assert config.max_poll_records == 10000

        # Invalid values
        with pytest.raises(ValueError):
            KafkaConsumerConfig(max_poll_records=0)

        with pytest.raises(ValueError):
            KafkaConsumerConfig(max_poll_records=10001)

    def test_session_timeout_validation(self):
        """Test validation of session_timeout_ms bounds."""
        # Valid values
        config = KafkaConsumerConfig(session_timeout_ms=1000)
        assert config.session_timeout_ms == 1000

        config = KafkaConsumerConfig(session_timeout_ms=300000)
        assert config.session_timeout_ms == 300000

        # Invalid values
        with pytest.raises(ValueError):
            KafkaConsumerConfig(session_timeout_ms=999)

        with pytest.raises(ValueError):
            KafkaConsumerConfig(session_timeout_ms=300001)


class TestKafkaConfig:
    """Tests for KafkaConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = KafkaConfig()

        assert config.bootstrap_servers == "omninode-bridge-redpanda:9092"
        assert isinstance(config.topics, KafkaTopicConfig)
        assert isinstance(config.consumer, KafkaConsumerConfig)

    def test_bootstrap_servers_validation(self):
        """Test validation of bootstrap_servers."""
        # Valid value
        config = KafkaConfig(bootstrap_servers="localhost:9092")
        assert config.bootstrap_servers == "localhost:9092"

        # Empty value
        with pytest.raises(ValueError, match="cannot be empty"):
            KafkaConfig(bootstrap_servers="")

        with pytest.raises(ValueError, match="cannot be empty"):
            KafkaConfig(bootstrap_servers="   ")

    def test_from_env_defaults(self, monkeypatch):
        """Test loading configuration from environment with defaults."""
        # Clear any existing environment variables
        for key in os.environ.keys():
            if key.startswith("KAFKA_"):
                monkeypatch.delenv(key, raising=False)

        reset_kafka_config()
        config = KafkaConfig.from_env()

        assert config.bootstrap_servers == "omninode-bridge-redpanda:9092"
        assert config.consumer.group_id == "archon-intelligence"
        assert config.topics.validate_request == "omninode.codegen.request.validate.v1"

    def test_from_env_custom_values(self, monkeypatch):
        """Test loading custom configuration from environment."""
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "custom-broker:9093")
        monkeypatch.setenv("KAFKA_CONSUMER_GROUP", "test-group")
        monkeypatch.setenv("KAFKA_AUTO_OFFSET_RESET", "latest")
        monkeypatch.setenv("KAFKA_ENABLE_AUTO_COMMIT", "false")
        monkeypatch.setenv("KAFKA_MAX_POLL_RECORDS", "1000")
        monkeypatch.setenv("KAFKA_SESSION_TIMEOUT_MS", "45000")

        # Custom topics
        monkeypatch.setenv("KAFKA_CODEGEN_VALIDATE_REQUEST", "custom.validate.request")
        monkeypatch.setenv(
            "KAFKA_CODEGEN_VALIDATE_RESPONSE", "custom.validate.response"
        )

        reset_kafka_config()
        config = KafkaConfig.from_env()

        # Connection
        assert config.bootstrap_servers == "custom-broker:9093"

        # Consumer
        assert config.consumer.group_id == "test-group"
        assert config.consumer.auto_offset_reset == "latest"
        assert config.consumer.enable_auto_commit is False
        assert config.consumer.max_poll_records == 1000
        assert config.consumer.session_timeout_ms == 45000

        # Topics
        assert config.topics.validate_request == "custom.validate.request"
        assert config.topics.validate_response == "custom.validate.response"

    def test_to_consumer_config(self):
        """Test conversion to AIOKafkaConsumer config."""
        config = KafkaConfig(
            bootstrap_servers="localhost:9092",
            consumer=KafkaConsumerConfig(
                group_id="test-consumer",
                auto_offset_reset="latest",
                enable_auto_commit=False,
                max_poll_records=100,
                session_timeout_ms=60000,
            ),
        )

        consumer_config = config.to_consumer_config()

        assert consumer_config == {
            "bootstrap_servers": "localhost:9092",
            "group_id": "test-consumer",
            "auto_offset_reset": "latest",
            "enable_auto_commit": False,
            "max_poll_records": 100,
            "session_timeout_ms": 60000,
        }


class TestGlobalConfig:
    """Tests for global configuration management."""

    def test_get_kafka_config_singleton(self, monkeypatch):
        """Test that get_kafka_config returns singleton instance."""
        reset_kafka_config()

        config1 = get_kafka_config()
        config2 = get_kafka_config()

        assert config1 is config2

    def test_reset_kafka_config(self, monkeypatch):
        """Test that reset_kafka_config clears singleton."""
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker1:9092")
        reset_kafka_config()

        config1 = get_kafka_config()
        assert config1.bootstrap_servers == "broker1:9092"

        # Change environment and reset
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker2:9092")
        reset_kafka_config()

        config2 = get_kafka_config()
        assert config2.bootstrap_servers == "broker2:9092"
        assert config1 is not config2


class TestDockerEnvironmentConfiguration:
    """Tests for Docker environment configuration."""

    def test_docker_defaults(self, monkeypatch):
        """Test default configuration for Docker environment."""
        # Simulate Docker environment
        for key in os.environ.keys():
            if key.startswith("KAFKA_"):
                monkeypatch.delenv(key, raising=False)

        reset_kafka_config()
        config = KafkaConfig.from_env()

        # Verify Docker-specific defaults
        assert config.bootstrap_servers == "omninode-bridge-redpanda:9092"
        assert config.consumer.group_id == "archon-intelligence"
        assert config.consumer.auto_offset_reset == "earliest"

    def test_local_development_configuration(self, monkeypatch):
        """Test configuration for local development."""
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
        monkeypatch.setenv("KAFKA_CONSUMER_GROUP", "archon-intelligence-dev")

        reset_kafka_config()
        config = KafkaConfig.from_env()

        assert config.bootstrap_servers == "localhost:19092"
        assert config.consumer.group_id == "archon-intelligence-dev"
