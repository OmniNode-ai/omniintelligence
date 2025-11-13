"""
Events Module

Event-driven infrastructure for intelligence services.
Includes HybridEventRouter for intelligent Kafka/in-memory routing.

Created: 2025-10-14
"""

from uuid import UUID, uuid4

from .hybrid_event_router import HybridEventRouter

# Note: FreshnessEventCoordinator requires freshness module which is not yet implemented
# from .freshness_event_coordinator import FreshnessEventCoordinator

__all__ = [
    "HybridEventRouter",
    # "FreshnessEventCoordinator",
]
