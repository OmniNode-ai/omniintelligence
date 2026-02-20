# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node Pattern Projection Effect — declarative effect node for pattern projection snapshots.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic — all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, handlers wired externally"

Triggered by pattern lifecycle change events (pattern-promoted,
pattern-deprecated, pattern-lifecycle-transitioned), this node queries the
full validated pattern set and publishes a materialized snapshot to the
pattern-projection topic. This is the produce side of the Kafka-based
projection that replaces the HTTP API escape hatch introduced in OMN-2355.

Node Responsibilities:
    - Define I/O model contract (dict → ModelPatternProjectionEvent)
    - Delegate all execution to handlers via base class
    - NO custom logic — pure declarative shell

Related:
    - contract.yaml: Handler routing and I/O model definitions
    - handlers/handler_projection.py: Query and publish logic

Related Tickets:
    - OMN-2424: Pattern projection snapshot publisher
    - OMN-2355: HTTP API escape hatch (superseded by this node on consume side)
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodePatternProjectionEffect(NodeEffect):
    """Declarative effect node for pattern projection snapshot publishing.

    Subscribes to pattern lifecycle events and publishes a full materialized
    snapshot of the validated pattern set to the projection topic on each
    trigger. This enables downstream consumers (e.g. omniclaude) to maintain
    an up-to-date local cache without needing direct database access.

    Supported Operations (defined in contract.yaml handler_routing):
        - publish_projection: Query validated patterns and publish snapshot

    Dependency Injection:
        Handlers are invoked by callers with their dependencies
        (pattern_query_store, kafka_producer, correlation_id). This node
        contains NO instance variables for handlers or registries.

    Example:
        ```python
        from omnibase_core.models.container import ModelONEXContainer
        from omniintelligence.nodes.node_pattern_projection_effect import (
            NodePatternProjectionEffect,
        )

        container = ModelONEXContainer()
        node = NodePatternProjectionEffect(container)

        # Handlers are invoked directly with their dependencies
        # Or use RuntimeHostProcess for event-driven execution
        ```
    """

    # Pure declarative shell — all behavior defined in contract.yaml


__all__ = ["NodePatternProjectionEffect"]
