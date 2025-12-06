# SPDX-License-Identifier: Apache-2.0
"""
Intelligence Runtime Configuration Model.

This module provides the application-level configuration for the OmniIntelligence
runtime host. It defines which handlers to bind, which topics to use, and
configuration values for the intelligence runtime.

Architecture Context:
    The IntelligenceRuntimeConfig tells the Runtime Host (from omnibase_infra):
    - Which handlers to bind (vector store, embedding, kafka, etc.)
    - Which topics to use (event bus configuration)
    - Configuration values for the intelligence runtime

    This is the application-layer configuration that gets passed to
    BaseRuntimeHostProcess during initialization.

Design Decisions:
    - Uses Pydantic for validation and serialization
    - Supports environment variable interpolation (e.g., ${KAFKA_BOOTSTRAP_SERVERS})
    - Supports loading from YAML files
    - Supports loading from environment variables
    - Does NOT import from omnibase_infra (handlers are injected at runtime)
    - Does NOT import I/O libraries (confluent_kafka, qdrant_client, etc.)

Example:
    # Load from YAML
    config = IntelligenceRuntimeConfig.from_yaml("/path/to/runtime_config.yaml")

    # Load from environment
    config = IntelligenceRuntimeConfig.from_environment()

    # Use with RuntimeHostProcess (in omnibase_infra)
    process = IntelligenceRuntimeHostProcess(config=config)

Created: 2025-12-05
Pattern: ONEX Runtime Configuration Contract
"""

from __future__ import annotations

import os
import re
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EnumLogLevel(str, Enum):
    """Log level enumeration for runtime configuration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EnumHandlerType(str, Enum):
    """
    Handler types available for runtime configuration.

    These correspond to handler protocols defined in omnibase_spi
    and implementations in omnibase_infra.
    """

    KAFKA_PRODUCER = "kafka_producer"
    VECTOR_STORE = "vector_store"
    GRAPH_DATABASE = "graph_database"
    RELATIONAL_DATABASE = "relational_database"
    EMBEDDING = "embedding"
    HTTP_CLIENT = "http_client"


class ModelTopicConfig(BaseModel):
    """
    Kafka topic configuration for event bus.

    Defines the command and event topics used by the intelligence runtime
    for event-driven communication.

    Attributes:
        commands: Topic for incoming command messages.
        events: Topic for outgoing event messages.
        dlq: Optional dead letter queue topic for failed messages.
    """

    commands: str = Field(
        default="onex.intelligence.cmd.v1",
        description="Topic for incoming command messages",
        examples=["onex.intelligence.cmd.v1", "dev.intelligence.cmd.v1"],
    )

    events: str = Field(
        default="onex.intelligence.evt.v1",
        description="Topic for outgoing event messages",
        examples=["onex.intelligence.evt.v1", "dev.intelligence.evt.v1"],
    )

    dlq: str | None = Field(
        default=None,
        description="Dead letter queue topic for failed messages",
        examples=["onex.intelligence.dlq.v1"],
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class ModelEventBusConfig(BaseModel):
    """
    Event bus configuration for Kafka integration.

    Configures the ProtocolEventBus (KafkaEventBus in omnibase_infra)
    that feeds envelopes into the RuntimeHost.

    Note:
        This is the transport layer configuration. The event bus consumes
        Kafka messages, wraps them into ModelOnexEnvelope, and routes them
        to the appropriate nodes.

    Attributes:
        enabled: Whether the event bus is enabled.
        bootstrap_servers: Kafka bootstrap servers (supports env var interpolation).
        consumer_group: Consumer group identifier for load balancing.
        topics: Topic configuration for commands and events.
        auto_offset_reset: Kafka consumer auto offset reset policy.
        enable_auto_commit: Whether to enable auto commit of offsets.
        session_timeout_ms: Kafka session timeout in milliseconds.
    """

    enabled: bool = Field(
        default=True,
        description="Enable event bus for event-driven workflows",
    )

    bootstrap_servers: str = Field(
        default="${KAFKA_BOOTSTRAP_SERVERS}",
        description="Kafka bootstrap servers (supports env var interpolation)",
        examples=[
            "${KAFKA_BOOTSTRAP_SERVERS}",
            "localhost:9092",
            "192.168.86.200:29092",
        ],
    )

    consumer_group: str = Field(
        default="intelligence-runtime",
        description="Consumer group identifier for load balancing",
        examples=["intelligence-runtime", "intelligence-dev", "intelligence-prod"],
    )

    topics: ModelTopicConfig = Field(
        default_factory=ModelTopicConfig,
        description="Topic configuration for commands and events",
    )

    auto_offset_reset: Literal["earliest", "latest"] = Field(
        default="earliest",
        description="Kafka consumer auto offset reset policy",
    )

    enable_auto_commit: bool = Field(
        default=False,
        description="Enable auto commit of offsets (disabled for manual control)",
    )

    session_timeout_ms: int = Field(
        default=30000,
        ge=1000,
        le=300000,
        description="Kafka session timeout in milliseconds",
    )

    model_config = ConfigDict(
        extra="forbid",
    )


class ModelHandlerConfig(BaseModel):
    """
    Handler configuration for runtime dependency injection.

    Configures handlers that implement SPI protocols (from omnibase_spi)
    and are instantiated by omnibase_infra. Nodes access these handlers
    through protocol interfaces without direct I/O.

    Note:
        Handlers are for node-initiated operations (e.g., explicitly publishing
        an event, querying a vector store). This is distinct from the event bus
        which is the transport layer.

    Attributes:
        handler_type: Type of handler from EnumHandlerType.
        enabled: Whether this handler is enabled.
        config: Handler-specific configuration dictionary.
    """

    handler_type: EnumHandlerType = Field(
        description="Type of handler (maps to SPI protocol and infra implementation)",
    )

    enabled: bool = Field(
        default=True,
        description="Whether this handler is enabled",
    )

    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Handler-specific configuration (passed to handler constructor)",
        examples=[
            {"bootstrap_servers": "${KAFKA_BOOTSTRAP_SERVERS}"},
            {"url": "http://localhost:6333", "collection": "intelligence"},
            {"uri": "bolt://localhost:7687", "user": "neo4j"},
        ],
    )

    model_config = ConfigDict(
        extra="forbid",
    )


class ModelRuntimeProfileConfig(BaseModel):
    """
    Optional runtime profile configuration for node selection.

    Allows filtering which nodes are loaded based on profile configuration.
    Useful for running subset of nodes in development or specialized deployments.

    Attributes:
        profile_name: Profile name identifier.
        node_types: List of node types to include (compute, effect, reducer, orchestrator).
        node_names: Optional list of specific node names to include.
        exclude_nodes: Optional list of node names to exclude.
    """

    profile_name: str = Field(
        default="default",
        description="Profile name identifier",
        examples=["default", "development", "compute-only", "minimal"],
        alias="name",  # Backward compatibility alias
    )

    node_types: list[Literal["compute", "effect", "reducer", "orchestrator"]] = Field(
        default=["compute", "effect", "reducer", "orchestrator"],
        description="Node types to include in this profile",
    )

    node_names: list[str] | None = Field(
        default=None,
        description="Specific node names to include (None means all matching types)",
    )

    exclude_nodes: list[str] | None = Field(
        default=None,
        description="Node names to exclude from this profile",
    )

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,  # Allow both 'name' and 'profile_name'
    )


class ModelIntelligenceRuntimeConfig(BaseModel):
    """
    Application-level configuration for OmniIntelligence runtime host.

    This configuration tells the Runtime Host (from omnibase_infra):
    - Which handlers to bind (vector store, embedding, kafka, etc.)
    - Which topics to use (event bus configuration)
    - Configuration values for the intelligence runtime

    Architecture:
        IntelligenceRuntimeConfig is passed to BaseRuntimeHostProcess
        (from omnibase_infra) during initialization. The runtime host
        uses this configuration to:
        1. Configure the event bus (Kafka consumer)
        2. Instantiate and wire handlers
        3. Load nodes from IntelligenceNodeRegistry
        4. Start the runtime event loop

    Environment Variable Interpolation:
        Values like "${KAFKA_BOOTSTRAP_SERVERS}" are interpolated from
        environment variables during configuration loading.

    Example:
        # Load from YAML file
        config = IntelligenceRuntimeConfig.from_yaml("config.yaml")

        # Load from environment
        config = IntelligenceRuntimeConfig.from_environment()

        # Create with explicit values
        config = IntelligenceRuntimeConfig(
            runtime_name="intelligence-runtime",
            event_bus=EventBusConfig(
                bootstrap_servers="localhost:9092",
                consumer_group="intelligence-dev",
            ),
            handlers=[
                HandlerConfig(
                    handler_type=EnumHandlerType.KAFKA_PRODUCER,
                    config={"bootstrap_servers": "localhost:9092"},
                ),
            ],
        )

    Attributes:
        runtime_name: Unique identifier for this runtime instance.
        log_level: Logging level for the runtime.
        event_bus: Event bus (Kafka) configuration.
        handlers: List of handler configurations.
        profile: Optional runtime profile for node selection.
        health_check_port: Port for health check endpoint.
        metrics_enabled: Whether to enable Prometheus metrics.
        metrics_port: Port for metrics endpoint.
    """

    runtime_name: str = Field(
        default="intelligence-runtime",
        description="Unique identifier for this runtime instance",
        examples=["intelligence-runtime", "intelligence-dev", "intelligence-prod"],
        min_length=1,
        max_length=128,
    )

    log_level: EnumLogLevel = Field(
        default=EnumLogLevel.INFO,
        description="Logging level for the runtime",
    )

    event_bus: ModelEventBusConfig = Field(
        default_factory=ModelEventBusConfig,
        description="Event bus (Kafka) configuration",
    )

    handlers: list[ModelHandlerConfig] = Field(
        default_factory=list,
        description="List of handler configurations for dependency injection",
    )

    profile: ModelRuntimeProfileConfig | None = Field(
        default=None,
        description="Optional runtime profile for node selection",
    )

    health_check_port: int = Field(
        default=8080,
        ge=1,
        le=65535,
        description="Port for health check endpoint",
    )

    metrics_enabled: bool = Field(
        default=True,
        description="Enable Prometheus metrics collection",
    )

    metrics_port: int = Field(
        default=9090,
        ge=1,
        le=65535,
        description="Port for Prometheus metrics endpoint",
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "runtime_name": "intelligence-runtime",
                    "log_level": "INFO",
                    "event_bus": {
                        "enabled": True,
                        "bootstrap_servers": "${KAFKA_BOOTSTRAP_SERVERS}",
                        "consumer_group": "intelligence-runtime",
                        "topics": {
                            "commands": "onex.intelligence.cmd.v1",
                            "events": "onex.intelligence.evt.v1",
                        },
                    },
                    "handlers": [
                        {
                            "handler_type": "kafka_producer",
                            "enabled": True,
                            "config": {
                                "bootstrap_servers": "${KAFKA_BOOTSTRAP_SERVERS}"
                            },
                        }
                    ],
                }
            ]
        },
    )

    # ==========================================
    # Validators
    # ==========================================

    @field_validator("runtime_name")
    @classmethod
    def validate_runtime_name(cls, v: str) -> str:
        """
        Validate runtime name follows naming conventions.

        Args:
            v: Runtime name to validate.

        Returns:
            Validated runtime name.

        Raises:
            ValueError: If name contains invalid characters.
        """
        if not v or not v.strip():
            raise ValueError("Runtime name cannot be empty")

        v = v.strip()

        # Allow alphanumeric, hyphens, underscores
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", v):
            raise ValueError(
                f"Runtime name must start with a letter and contain only "
                f"alphanumeric characters, hyphens, and underscores: {v}"
            )

        return v

    @model_validator(mode="after")
    def validate_port_uniqueness(self) -> ModelIntelligenceRuntimeConfig:
        """
        Validate that health check and metrics ports are different.

        Returns:
            Validated configuration.

        Raises:
            ValueError: If ports conflict.
        """
        if self.metrics_enabled and self.health_check_port == self.metrics_port:
            raise ValueError(
                f"Health check port ({self.health_check_port}) and metrics port "
                f"({self.metrics_port}) must be different when metrics are enabled"
            )
        return self

    # ==========================================
    # Environment Variable Interpolation
    # ==========================================

    @staticmethod
    def _interpolate_env_vars(value: Any) -> Any:
        """
        Recursively interpolate environment variables in configuration values.

        Supports ${VAR_NAME} syntax for environment variable references.

        Args:
            value: Value to interpolate (str, dict, list, or primitive).

        Returns:
            Value with environment variables interpolated.

        Raises:
            ValueError: If referenced environment variable is not set.
        """
        if isinstance(value, str):
            # Find all ${VAR_NAME} patterns
            pattern = r"\$\{([A-Z_][A-Z0-9_]*)\}"
            matches = re.findall(pattern, value)

            for var_name in matches:
                env_value = os.environ.get(var_name)
                if env_value is None:
                    raise ValueError(
                        f"Environment variable '{var_name}' is not set "
                        f"(referenced in value: {value})"
                    )
                value = value.replace(f"${{{var_name}}}", env_value)

            return value

        if isinstance(value, dict):
            return {
                k: ModelIntelligenceRuntimeConfig._interpolate_env_vars(v)
                for k, v in value.items()
            }

        if isinstance(value, list):
            return [
                ModelIntelligenceRuntimeConfig._interpolate_env_vars(item)
                for item in value
            ]

        return value

    # ==========================================
    # Factory Methods
    # ==========================================

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        *,
        interpolate_env: bool = True,
    ) -> ModelIntelligenceRuntimeConfig:
        """
        Load configuration from a YAML file.

        Args:
            path: Path to the YAML configuration file.
            interpolate_env: Whether to interpolate environment variables.

        Returns:
            IntelligenceRuntimeConfig instance.

        Raises:
            FileNotFoundError: If configuration file does not exist.
            yaml.YAMLError: If YAML parsing fails.
            ValueError: If environment variable interpolation fails.
            pydantic.ValidationError: If configuration validation fails.

        Example:
            config = ModelIntelligenceRuntimeConfig.from_yaml(
                "/etc/omniintelligence/runtime.yaml"
            )
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            data = {}

        if interpolate_env:
            data = cls._interpolate_env_vars(data)

        return cls.model_validate(data)

    @classmethod
    def from_environment(
        cls,
        prefix: str = "INTELLIGENCE_RUNTIME_",
    ) -> ModelIntelligenceRuntimeConfig:
        """
        Load configuration from environment variables.

        Supports environment variables with the given prefix:
        - INTELLIGENCE_RUNTIME_NAME
        - INTELLIGENCE_RUNTIME_LOG_LEVEL
        - INTELLIGENCE_RUNTIME_HEALTH_CHECK_PORT
        - INTELLIGENCE_RUNTIME_METRICS_ENABLED
        - INTELLIGENCE_RUNTIME_METRICS_PORT

        For event bus configuration:
        - KAFKA_BOOTSTRAP_SERVERS
        - INTELLIGENCE_RUNTIME_CONSUMER_GROUP
        - INTELLIGENCE_RUNTIME_COMMAND_TOPIC
        - INTELLIGENCE_RUNTIME_EVENT_TOPIC

        Args:
            prefix: Environment variable prefix (default: INTELLIGENCE_RUNTIME_).

        Returns:
            IntelligenceRuntimeConfig instance.

        Example:
            # Set environment variables
            os.environ["INTELLIGENCE_RUNTIME_NAME"] = "my-runtime"
            os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "localhost:9092"

            config = ModelIntelligenceRuntimeConfig.from_environment()
        """
        # Build configuration from environment
        config_data: dict[str, Any] = {}

        # Runtime name
        if runtime_name := os.environ.get(f"{prefix}NAME"):
            config_data["runtime_name"] = runtime_name

        # Log level
        if log_level := os.environ.get(f"{prefix}LOG_LEVEL"):
            config_data["log_level"] = log_level

        # Health check port
        if health_port := os.environ.get(f"{prefix}HEALTH_CHECK_PORT"):
            config_data["health_check_port"] = int(health_port)

        # Metrics
        if metrics_enabled := os.environ.get(f"{prefix}METRICS_ENABLED"):
            config_data["metrics_enabled"] = metrics_enabled.lower() in (
                "true",
                "1",
                "yes",
            )

        if metrics_port := os.environ.get(f"{prefix}METRICS_PORT"):
            config_data["metrics_port"] = int(metrics_port)

        # Event bus configuration
        event_bus_data: dict[str, Any] = {}

        if bootstrap_servers := os.environ.get("KAFKA_BOOTSTRAP_SERVERS"):
            event_bus_data["bootstrap_servers"] = bootstrap_servers

        if consumer_group := os.environ.get(f"{prefix}CONSUMER_GROUP"):
            event_bus_data["consumer_group"] = consumer_group

        # Topics
        topics_data: dict[str, str] = {}
        if cmd_topic := os.environ.get(f"{prefix}COMMAND_TOPIC"):
            topics_data["commands"] = cmd_topic
        if evt_topic := os.environ.get(f"{prefix}EVENT_TOPIC"):
            topics_data["events"] = evt_topic
        if dlq_topic := os.environ.get(f"{prefix}DLQ_TOPIC"):
            topics_data["dlq"] = dlq_topic

        if topics_data:
            event_bus_data["topics"] = topics_data

        if event_bus_data:
            config_data["event_bus"] = event_bus_data

        return cls.model_validate(config_data)

    @classmethod
    def default_development(cls) -> ModelIntelligenceRuntimeConfig:
        """
        Create default development configuration.

        Returns:
            ModelIntelligenceRuntimeConfig with development defaults.
        """
        return cls(
            runtime_name="intelligence-dev",
            log_level=EnumLogLevel.DEBUG,
            event_bus=ModelEventBusConfig(
                bootstrap_servers="localhost:9092",
                consumer_group="intelligence-dev",
                topics=ModelTopicConfig(
                    commands="dev.intelligence.cmd.v1",
                    events="dev.intelligence.evt.v1",
                    dlq="dev.intelligence.dlq.v1",
                ),
            ),
            handlers=[
                ModelHandlerConfig(
                    handler_type=EnumHandlerType.KAFKA_PRODUCER,
                    config={"bootstrap_servers": "localhost:9092"},
                ),
            ],
            health_check_port=8080,
            metrics_enabled=True,
            metrics_port=9090,
        )

    @classmethod
    def default_production(cls) -> ModelIntelligenceRuntimeConfig:
        """
        Create default production configuration.

        Returns:
            ModelIntelligenceRuntimeConfig with production defaults.

        Raises:
            ValueError: If required environment variables are not set.
        """
        # Validate required environment variables
        required_vars = ["KAFKA_BOOTSTRAP_SERVERS"]
        missing = [var for var in required_vars if not os.environ.get(var)]
        if missing:
            raise ValueError(
                f"Required environment variables not set for production: {missing}"
            )

        bootstrap_servers = os.environ["KAFKA_BOOTSTRAP_SERVERS"]

        return cls(
            runtime_name="intelligence-prod",
            log_level=EnumLogLevel.INFO,
            event_bus=ModelEventBusConfig(
                bootstrap_servers=bootstrap_servers,
                consumer_group="intelligence-prod",
                topics=ModelTopicConfig(
                    commands="onex.intelligence.cmd.v1",
                    events="onex.intelligence.evt.v1",
                    dlq="onex.intelligence.dlq.v1",
                ),
            ),
            handlers=[
                ModelHandlerConfig(
                    handler_type=EnumHandlerType.KAFKA_PRODUCER,
                    config={"bootstrap_servers": bootstrap_servers},
                ),
            ],
            health_check_port=8080,
            metrics_enabled=True,
            metrics_port=9090,
        )

    # ==========================================
    # Helper Methods
    # ==========================================

    def get_handler_config(
        self,
        handler_type: EnumHandlerType,
    ) -> ModelHandlerConfig | None:
        """
        Get configuration for a specific handler type.

        Args:
            handler_type: Type of handler to find.

        Returns:
            HandlerConfig if found and enabled, None otherwise.
        """
        for handler in self.handlers:
            if handler.handler_type == handler_type and handler.enabled:
                return handler
        return None

    def has_handler(self, handler_type: EnumHandlerType) -> bool:
        """
        Check if a handler type is configured and enabled.

        Args:
            handler_type: Type of handler to check.

        Returns:
            True if handler is configured and enabled.
        """
        return self.get_handler_config(handler_type) is not None

    def to_yaml(self, path: str | Path) -> None:
        """
        Save configuration to a YAML file.

        Args:
            path: Path to write the YAML file.

        Example:
            config = ModelIntelligenceRuntimeConfig.default_development()
            config.to_yaml("/etc/omniintelligence/runtime.yaml")
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                self.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )


# ==========================================================================
# Backward Compatibility Aliases (deprecated, use Model* versions)
# ==========================================================================

# These aliases maintain backward compatibility with existing code.
# New code should use the Model* prefixed versions.
TopicConfig = ModelTopicConfig
EventBusConfig = ModelEventBusConfig
HandlerConfig = ModelHandlerConfig
RuntimeProfileConfig = ModelRuntimeProfileConfig
IntelligenceRuntimeConfig = ModelIntelligenceRuntimeConfig
