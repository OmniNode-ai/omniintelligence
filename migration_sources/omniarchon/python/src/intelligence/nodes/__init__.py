"""
Intelligence Adapter Nodes - ONEX Effect Nodes for Intelligence Operations.

This package contains ONEX-compliant Effect nodes that integrate Archon's
intelligence services with event-driven architecture via Kafka.

Nodes:
- NodeIntelligenceAdapterEffect: Core intelligence adapter with Kafka integration
  - Subscribes to code analysis request events
  - Routes requests to intelligence services
  - Publishes completion/failure events
  - Manages Kafka consumer lifecycle

Created: 2025-10-21
Reference: EVENT_BUS_ARCHITECTURE.md, ONEX patterns
"""

from intelligence.nodes.node_intelligence_adapter_effect import (
    NodeIntelligenceAdapterEffect,
)

__all__ = [
    "NodeIntelligenceAdapterEffect",
]
