# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Lifecycle Effect Node - Applies status transition projections.

This effect node receives ModelPayloadUpdatePatternStatus intents from the
reducer and applies the status transition to the database. It is the ONLY
code path that may update learned_patterns.status.

This node follows the ONEX declarative pattern:
    - EFFECT node for database writes (pattern status updates) and Kafka events
    - Lightweight shell (~30 lines) that delegates to registry-wired handlers
    - No setters, no try/except, no logging in node class
    - Pattern: "Contract-driven, handlers wired externally via registry"

The node is initialized with a ServiceHandlerRegistry that contains handlers
with their dependencies (repository, idempotency_store, producer) already bound.
All error handling, logging, and business logic resides in the handler functions.

Ticket: OMN-1805
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_effect import NodeEffect

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer
    from omniintelligence.nodes.node_intelligence_reducer.models import (
        ModelPayloadUpdatePatternStatus,
    )
    from omniintelligence.nodes.node_pattern_lifecycle_effect.models import (
        ModelTransitionResult,
    )
    from omniintelligence.nodes.node_pattern_lifecycle_effect.registry import (
        ServiceHandlerRegistry,
    )


class NodePatternLifecycleEffect(NodeEffect):
    """Effect node for applying pattern status transitions.

    This is a declarative thin shell - all business logic is in the handler.
    The node simply delegates to the registry-wired handler function.
    """

    def __init__(
        self,
        container: ModelONEXContainer,
        registry: ServiceHandlerRegistry,
    ) -> None:
        """Initialize the effect node with registry.

        Args:
            container: ONEX dependency injection container.
            registry: Service handler registry with wired dependencies.
        """
        super().__init__(container)
        self._registry = registry

    async def execute(
        self, intent: ModelPayloadUpdatePatternStatus
    ) -> ModelTransitionResult:
        """Execute the effect node to apply a pattern status transition.

        Delegates to the registry-wired handler function.

        Args:
            intent: The transition intent from the reducer containing
                pattern_id, from_status, to_status, and idempotency key.

        Returns:
            ModelTransitionResult with transition outcome.
        """
        handler = self._registry.apply_transition
        return await handler(intent)


__all__ = ["NodePatternLifecycleEffect"]
