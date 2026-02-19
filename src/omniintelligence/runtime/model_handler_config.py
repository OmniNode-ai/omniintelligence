"""Handler configuration model for runtime dependency injection."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.runtime.enum_handler_type import EnumHandlerType


class ModelHandlerConfig(BaseModel):
    """Handler configuration for runtime dependency injection.

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


__all__ = ["ModelHandlerConfig"]
