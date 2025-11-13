"""
Lifecycle Event Publishing for ONEX Integration

Publishes service lifecycle events for observability and ONEX compliance.
Events are logged locally and can be consumed by monitoring systems.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class LifecycleEvent:
    """Model for service lifecycle events following ONEX event patterns."""

    event_type: str
    payload: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    domain: str = "archon"
    service_id: str = "archon-backend"


class LifecycleEventPublisher:
    """
    Lightweight event publisher for service lifecycle events.

    Publishes events to logs for observability. Future enhancement can
    integrate with message queues or event buses.
    """

    def __init__(self):
        self._events: list[LifecycleEvent] = []

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """
        Publish a lifecycle event.

        Args:
            event_type: Type of lifecycle event (e.g., service_lifecycle_started)
            payload: Event payload with service metadata
        """
        try:
            event = LifecycleEvent(event_type=event_type, payload=payload)

            # Store event for potential future queries
            self._events.append(event)

            # Log event for observability
            event_data = asdict(event)
            logger.info(
                f"📡 Lifecycle Event: {event_type}", extra={"event": event_data}
            )

            # Pretty print for console visibility
            print(f"\n{'='*60}")
            print(f"📡 LIFECYCLE EVENT: {event_type}")
            print(f"{'='*60}")
            print(json.dumps(event_data, indent=2))
            print(f"{'='*60}\n")

        except Exception as e:
            logger.warning(f"Failed to publish lifecycle event: {e}")

    async def initialize(self) -> None:
        """Initialize the event publisher (no-op for local implementation)."""
        logger.info("Lifecycle event publisher initialized")

    async def shutdown(self) -> None:
        """Shutdown the event publisher."""
        logger.info(
            f"Lifecycle event publisher shutdown ({len(self._events)} events published)"
        )

    def get_events(self) -> list[dict[str, Any]]:
        """Get all published events."""
        return [asdict(event) for event in self._events]


# Singleton instance
_lifecycle_publisher: Optional[LifecycleEventPublisher] = None


def get_lifecycle_publisher() -> LifecycleEventPublisher:
    """Get the singleton lifecycle event publisher."""
    global _lifecycle_publisher
    if _lifecycle_publisher is None:
        _lifecycle_publisher = LifecycleEventPublisher()
    return _lifecycle_publisher
