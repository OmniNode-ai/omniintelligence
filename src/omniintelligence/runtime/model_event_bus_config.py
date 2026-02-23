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

    # NOTE(OMN-2438/OMN-2439): PluginIntelligence.start_consumers() bypasses this
    # field entirely and reads OMNIINTELLIGENCE_CONSUMER_GROUP directly so that all
    # runtime containers share a single Kafka consumer group regardless of how this
    # model is instantiated.  This field is retained for documentation purposes and
    # for consumers that configure their own event bus independently of the plugin.
    consumer_group: str = Field(
        default="omniintelligence",
        description=(
            "Consumer group identifier for load balancing. "
            "Note: PluginIntelligence.start_consumers() bypasses this field and "
            "reads OMNIINTELLIGENCE_CONSUMER_GROUP directly (OMN-2438/OMN-2439)."
        ),
        examples=["omniintelligence", "omniintelligence-dev", "omniintelligence-prod"],
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
