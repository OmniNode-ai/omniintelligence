# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Lifecycle Effect node - OMN-1805.

This node applies pattern status transition projections to the database.
It receives ModelPayloadUpdatePatternStatus intents from the reducer and
atomically updates learned_patterns.status + inserts audit records.

This is the ONLY code path that may update learned_patterns.status.

Key Features:
    - Idempotency via request_id deduplication
    - Atomic transaction: UPDATE + INSERT audit in same transaction
    - Status guard: from_status must match current state
    - PROVISIONAL guard: Rejects to_status == "provisional" (legacy protection)

Published Events:
    - onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1

Example:
    ```python
    from omnibase_core.models.container import ModelONEXContainer
    from omniintelligence.nodes.node_pattern_lifecycle_effect import (
        NodePatternLifecycleEffect,
        ModelTransitionResult,
    )
    from omniintelligence.nodes.node_pattern_lifecycle_effect.registry import (
        RegistryPatternLifecycleEffect,
    )

    # Create registry with wired dependencies
    registry = RegistryPatternLifecycleEffect.create_registry(
        repository=db_connection,
        idempotency_store=idempotency_store,
        producer=kafka_producer,  # Optional
    )

    # Create and configure node
    container = ModelONEXContainer()
    effect = NodePatternLifecycleEffect(container, registry)

    # Apply a transition intent from the reducer
    intent = ModelPayloadUpdatePatternStatus(...)
    result = await effect.execute(intent)
    ```

Ticket: OMN-1805
"""

from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
    ProtocolIdempotencyStore,
    ProtocolKafkaPublisher,
    ProtocolPatternRepository,
)
from omniintelligence.nodes.node_pattern_lifecycle_effect.models import (
    ModelTransitionResult,
)
from omniintelligence.nodes.node_pattern_lifecycle_effect.node import (
    NodePatternLifecycleEffect,
)
from omniintelligence.nodes.node_pattern_lifecycle_effect.registry import (
    RegistryPatternLifecycleEffect,
    ServiceHandlerRegistry,
)

__all__ = [
    # Models
    "ModelTransitionResult",
    # Node
    "NodePatternLifecycleEffect",
    # Protocols (re-exported from handlers)
    "ProtocolIdempotencyStore",
    "ProtocolKafkaPublisher",
    "ProtocolPatternRepository",
    # Registry
    "RegistryPatternLifecycleEffect",
    "ServiceHandlerRegistry",
]
