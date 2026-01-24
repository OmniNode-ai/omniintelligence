"""Handler for unknown/unrouted events.

This handler acts as the default_handler in the handler_routing configuration.
It handles events that don't match any specific routing entry, logging them
for observability while returning an empty ModelHandlerOutput.

ONEX Compliance:
- Implements ProtocolMessageHandler protocol
- Returns ModelHandlerOutput.empty() (no events to publish)
- Logs unknown events for debugging/monitoring
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID, uuid4

from omnibase_core.enums.enum_execution_shape import EnumMessageCategory
from omnibase_core.enums.enum_node_kind import EnumNodeKind
from omnibase_core.models.dispatch.model_handler_output import ModelHandlerOutput
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

logger = logging.getLogger(__name__)

# Handler ID for registry and tracing
HANDLER_ID = "handler_unknown_event"


class HandlerUnknownEvent:
    """Default handler for unrouted events.

    This handler receives events that don't match any routing entry in the
    handler_routing configuration. It logs the event for observability
    and returns an empty ModelHandlerOutput (no events to publish).

    This is useful for:
    - Debugging routing issues
    - Monitoring unexpected event types
    - Gracefully handling schema evolution

    Example:
        >>> handler = HandlerUnknownEvent()
        >>> envelope = ModelEventEnvelope(
        ...     payload={"unexpected": "data"}
        ... )
        >>> output = await handler.handle(envelope)
        >>> assert not output.has_outputs()  # No events emitted
    """

    @property
    def handler_id(self) -> str:
        """Unique identifier for this handler."""
        return HANDLER_ID

    @property
    def category(self) -> EnumMessageCategory:
        """Message category this handler processes."""
        return EnumMessageCategory.EVENT

    @property
    def message_types(self) -> set[str]:
        """Specific message types this handler accepts.

        Empty set means this handler accepts all message types (as default).
        """
        return set()

    @property
    def node_kind(self) -> EnumNodeKind:
        """ONEX node kind this handler represents."""
        return EnumNodeKind.EFFECT

    async def handle(
        self,
        envelope: ModelEventEnvelope[Any],
    ) -> ModelHandlerOutput[None]:
        """Handle unknown/unrouted event.

        Logs the event for observability and returns empty output.

        Args:
            envelope: Event envelope with unknown payload type

        Returns:
            ModelHandlerOutput.empty() - no events to publish
        """
        start_time = time.perf_counter()

        # Extract info for logging
        payload_type = type(envelope.payload).__name__
        # correlation_id may be None, generate one if needed
        correlation_id: UUID = envelope.correlation_id or uuid4()

        logger.warning(
            f"Unknown event received - no handler configured | "
            f"correlation_id={correlation_id} | "
            f"payload_type={payload_type} | "
            f"event_type={getattr(envelope, 'event_type', 'unknown')}"
        )

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        # Return empty output - no events to publish
        return ModelHandlerOutput.empty(
            input_envelope_id=envelope.envelope_id,
            correlation_id=correlation_id,
            handler_id=self.handler_id,
            node_kind=self.node_kind,
            processing_time_ms=processing_time_ms,
        )


__all__ = ["HandlerUnknownEvent", "HANDLER_ID"]
