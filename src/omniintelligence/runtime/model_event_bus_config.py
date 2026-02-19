"""Event bus configuration model for Kafka integration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omniintelligence.runtime.model_topic_config import ModelTopicConfig


class ModelEventBusConfig(BaseModel):
    """Event bus configuration for Kafka integration.

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
        default=False,
        description="Enable event bus for event-driven workflows. "
        "Defaults to disabled; set to true and provide bootstrap_servers to use Kafka.",
    )

    bootstrap_servers: str = Field(
        default="",
        description="Kafka bootstrap servers (supports env var interpolation). "
        "Empty string is valid when event_bus is disabled.",
        examples=[
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

    @model_validator(mode="after")
    def validate_bootstrap_servers_when_enabled(self) -> "ModelEventBusConfig":
        """Require non-empty bootstrap_servers when the event bus is enabled."""
        if self.enabled and not self.bootstrap_servers:
            raise ValueError(
                "bootstrap_servers must be set when event_bus is enabled. "
                "Set event_bus.enabled=false to run without Kafka, or provide "
                "a valid bootstrap_servers value."
            )
        return self


__all__ = ["ModelEventBusConfig"]
