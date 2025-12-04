"""Event publisher for Kafka message production."""

from omniintelligence._legacy.events.publisher.event_publisher import (
    EventPublisher,
    create_event_publisher,
)

__all__ = [
    "EventPublisher",
    "create_event_publisher",
]
