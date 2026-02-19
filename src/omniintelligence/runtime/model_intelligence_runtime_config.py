"""Application-level configuration model for OmniIntelligence runtime host.

Architecture Context:
    The ModelIntelligenceRuntimeConfig tells the Runtime Host (from omnibase_infra):
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
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from omniintelligence.runtime.enum_handler_type import EnumHandlerType
from omniintelligence.runtime.enum_log_level import EnumLogLevel
from omniintelligence.runtime.model_event_bus_config import ModelEventBusConfig
from omniintelligence.runtime.model_handler_config import ModelHandlerConfig
from omniintelligence.runtime.model_runtime_profile_config import (
    ModelRuntimeProfileConfig,
)
from omniintelligence.runtime.model_topic_config import ModelTopicConfig


class ModelIntelligenceRuntimeConfig(BaseModel):
    """Application-level configuration for OmniIntelligence runtime host.

    This configuration tells the Runtime Host (from omnibase_infra):
    - Which handlers to bind (vector store, embedding, kafka, etc.)
    - Which topics to use (event bus configuration)
    - Configuration values for the intelligence runtime

    Architecture:
        ModelIntelligenceRuntimeConfig is passed to BaseRuntimeHostProcess
        (from omnibase_infra) during initialization. The runtime host
        uses this configuration to:
        1. Configure the event bus (Kafka consumer)
        2. Instantiate and wire handlers
        3. Load nodes from IntelligenceNodeRegistry
        4. Start the runtime event loop

    Environment Variable Interpolation:
        Values like "${KAFKA_BOOTSTRAP_SERVERS}" are interpolated from
        environment variables during configuration loading.

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
                        "bootstrap_servers": "kafka-broker:9092",
                        "consumer_group": "intelligence-runtime",
                        "topics": {
                            "commands": "onex.cmd.omniintelligence.claude-hook-event.v1",
                            "events": "onex.evt.omniintelligence.intent-classified.v1",
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
        """Validate runtime name follows naming conventions."""
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
        """Validate that health check and metrics ports are different."""
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
    def _interpolate_env_vars(value: object) -> object:
        """Recursively interpolate environment variables in configuration values.

        Supports ${VAR_NAME} syntax for environment variable references.

        Args:
            value: Value to interpolate (str, dict, list, or primitive).

        Returns:
            Value with environment variables interpolated.

        Raises:
            ValueError: If referenced environment variable is not set.
        """
        if isinstance(value, str):
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
        """Load configuration from a YAML file.

        Supports two YAML formats:

        1. **Plain config YAML** - Top-level keys are runtime config fields.

        2. **Contract YAML** - A full ONEX configuration contract where the
           actual runtime config values live under the ``defaults`` key.
           When a ``defaults`` key is present, only that section is parsed as
           runtime configuration.

        Args:
            path: Path to the YAML configuration file.
            interpolate_env: Whether to interpolate environment variables.

        Returns:
            ModelIntelligenceRuntimeConfig instance.

        Raises:
            FileNotFoundError: If configuration file does not exist.
            yaml.YAMLError: If YAML parsing fails.
            ValueError: If environment variable interpolation fails.
            pydantic.ValidationError: If configuration validation fails.
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            data = {}

        if isinstance(data, dict) and "defaults" in data:
            data = data["defaults"]
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
        """Load configuration from environment variables.

        Args:
            prefix: Environment variable prefix (default: INTELLIGENCE_RUNTIME_).

        Returns:
            ModelIntelligenceRuntimeConfig instance.
        """
        config_data: dict[str, object] = {}

        if runtime_name := os.environ.get(f"{prefix}NAME"):
            config_data["runtime_name"] = runtime_name

        if log_level := os.environ.get(f"{prefix}LOG_LEVEL"):
            config_data["log_level"] = log_level

        if health_port := os.environ.get(f"{prefix}HEALTH_CHECK_PORT"):
            try:
                config_data["health_check_port"] = int(health_port)
            except ValueError:
                raise ValueError(
                    f"{prefix}HEALTH_CHECK_PORT must be numeric, got: {health_port!r}"
                ) from None

        if metrics_enabled := os.environ.get(f"{prefix}METRICS_ENABLED"):
            config_data["metrics_enabled"] = metrics_enabled.lower() in (
                "true",
                "1",
                "yes",
            )

        if metrics_port := os.environ.get(f"{prefix}METRICS_PORT"):
            try:
                config_data["metrics_port"] = int(metrics_port)
            except ValueError:
                raise ValueError(
                    f"{prefix}METRICS_PORT must be numeric, got: {metrics_port!r}"
                ) from None

        event_bus_data: dict[str, object] = {}

        if event_bus_enabled := os.environ.get(f"{prefix}EVENT_BUS_ENABLED"):
            event_bus_data["enabled"] = event_bus_enabled.lower() in (
                "true",
                "1",
                "yes",
            )

        if bootstrap_servers := os.environ.get("KAFKA_BOOTSTRAP_SERVERS"):
            event_bus_data["bootstrap_servers"] = bootstrap_servers

        if consumer_group := os.environ.get(f"{prefix}CONSUMER_GROUP"):
            event_bus_data["consumer_group"] = consumer_group

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
            if "enabled" not in event_bus_data:
                kafka_intelligence_flag = os.environ.get(
                    "KAFKA_ENABLE_INTELLIGENCE", ""
                )
                event_bus_data["enabled"] = kafka_intelligence_flag.lower() in (
                    "true",
                    "1",
                    "yes",
                )
            config_data["event_bus"] = event_bus_data

        return cls.model_validate(config_data)

    @classmethod
    def default_development(cls) -> ModelIntelligenceRuntimeConfig:
        """Create default development configuration."""
        return cls(
            runtime_name="intelligence-dev",
            log_level=EnumLogLevel.DEBUG,
            event_bus=ModelEventBusConfig(
                enabled=True,
                bootstrap_servers="localhost:9092",
                consumer_group="intelligence-dev",
                topics=ModelTopicConfig(
                    commands="onex.cmd.omniintelligence.claude-hook-event.v1",
                    events="onex.evt.omniintelligence.intent-classified.v1",
                    dlq="onex.dlq.omniintelligence.v1",
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
        """Create default production configuration.

        Raises:
            ValueError: If required environment variables are not set.
        """
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
                enabled=True,
                bootstrap_servers=bootstrap_servers,
                consumer_group="intelligence-prod",
                topics=ModelTopicConfig(
                    commands="onex.cmd.omniintelligence.claude-hook-event.v1",
                    events="onex.evt.omniintelligence.intent-classified.v1",
                    dlq="onex.dlq.omniintelligence.v1",
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
        """Get configuration for a specific handler type.

        Args:
            handler_type: Type of handler to find.

        Returns:
            ModelHandlerConfig if found and enabled, None otherwise.
        """
        for handler in self.handlers:
            if handler.handler_type == handler_type and handler.enabled:
                return handler
        return None

    def has_handler(self, handler_type: EnumHandlerType) -> bool:
        """Check if a handler type is configured and enabled.

        Args:
            handler_type: Type of handler to check.

        Returns:
            True if handler is configured and enabled.
        """
        return self.get_handler_config(handler_type) is not None

    def to_yaml(self, path: str | Path) -> None:
        """Save configuration to a YAML file.

        Args:
            path: Path to write the YAML file.
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


__all__ = ["ModelIntelligenceRuntimeConfig"]
