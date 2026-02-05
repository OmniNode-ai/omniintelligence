# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Lifecycle Effect node.

This module exports the pattern lifecycle effect node and its supporting
models, handlers, and protocols. The node applies pattern status transition
projections to the database with atomic audit trail and idempotency.

This is the ONLY code path that may update learned_patterns.status.

Key Components:
    - NodePatternLifecycleEffect: Pure declarative effect node (thin shell)
    - ModelTransitionResult: Output for transition results
    - apply_transition: Handler function for applying transitions
    - ProtocolPatternRepository: Interface for database operations
    - ProtocolIdempotencyStore: Interface for idempotency tracking
    - ProtocolKafkaPublisher: Interface for Kafka event publishing

Key Features:
    - Idempotency via request_id deduplication
    - Atomic transaction: UPDATE + INSERT audit in same transaction
    - Status guard: from_status must match current state
    - PROVISIONAL guard: Rejects to_status == "provisional" (legacy protection)

Published Events:
    - onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1

Usage (Declarative Pattern):
    ```python
    from omnibase_core.models.container import ModelONEXContainer
    from omniintelligence.nodes.node_pattern_lifecycle_effect import (
        NodePatternLifecycleEffect,
        apply_transition,
        ModelTransitionResult,
    )

    # Create node via container (pure declarative shell)
    container = ModelONEXContainer()
    node = NodePatternLifecycleEffect(container)

    # Handlers are called directly with their dependencies
    result = await apply_transition(
        repository=db_conn,
        idempotency_store=idempotency_impl,
        producer=kafka_producer,  # Optional, can be None
        request_id=request_id,
        correlation_id=correlation_id,
        pattern_id=pattern_id,
        from_status="provisional",
        to_status="validated",
        trigger="promote",
        transition_at=datetime.now(UTC),
    )

    # For event-driven execution, use RuntimeHostProcess
    # which reads handler_routing from contract.yaml
    ```

Reference:
    - OMN-1805: Pattern lifecycle effect node implementation
    - OMN-1757: Refactor to declarative pattern
"""

from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers import (
    ProtocolIdempotencyStore,
    ProtocolKafkaPublisher,
    ProtocolPatternRepository,
    apply_transition,
)
from omniintelligence.nodes.node_pattern_lifecycle_effect.models import (
    ModelPatternLifecycleTransitionedEvent,
    ModelTransitionResult,
)
from omniintelligence.nodes.node_pattern_lifecycle_effect.node import (
    NodePatternLifecycleEffect,
)

__all__ = [
    # Models
    "ModelPatternLifecycleTransitionedEvent",
    "ModelTransitionResult",
    # Node
    "NodePatternLifecycleEffect",
    # Protocols
    "ProtocolIdempotencyStore",
    "ProtocolKafkaPublisher",
    "ProtocolPatternRepository",
    # Handler functions (for direct invocation)
    "apply_transition",
]
