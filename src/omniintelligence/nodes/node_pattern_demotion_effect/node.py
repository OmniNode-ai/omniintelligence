# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Demotion Effect - Thin shell node for pattern demotion.

This node follows the ONEX declarative pattern:
    - EFFECT node for database writes (pattern status updates) and Kafka events
    - Lightweight shell (~30 lines) that delegates to registry-wired handlers
    - No setters, no try/except, no logging in node class
    - Pattern: "Contract-driven, handlers wired externally via registry"

The node is initialized with a ServiceHandlerRegistry that contains handlers
with their dependencies (repository, producer) already bound. All error handling,
logging, and business logic resides in the handler functions.

Reference:
    - OMN-1681: Auto-demote logic for patterns failing quality thresholds
    - OMN-1678: Rolling window metrics (dependency)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from omnibase_core.nodes.node_effect import NodeEffect

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer
    from omniintelligence.nodes.node_pattern_demotion_effect.models import (
        ModelDemotionCheckRequest,
        ModelDemotionCheckResult,
    )
    from omniintelligence.nodes.node_pattern_demotion_effect.registry import (
        ServiceHandlerRegistry,
    )


class NodePatternDemotionEffect(NodeEffect):
    """Effect node for demoting validated patterns to deprecated status.

    This is a declarative thin shell - all business logic is in the handler.
    The node simply delegates to the registry-wired handler function.

    Example:
        >>> from omnibase_core.models.container import ModelONEXContainer
        >>> from omniintelligence.nodes.node_pattern_demotion_effect import (
        ...     NodePatternDemotionEffect,
        ... )
        >>> from omniintelligence.nodes.node_pattern_demotion_effect.registry import (
        ...     RegistryPatternDemotionEffect,
        ... )
        >>>
        >>> # Create registry with wired dependencies
        >>> registry = RegistryPatternDemotionEffect.create_registry(
        ...     repository=pattern_repo,
        ...     producer=kafka_producer,
        ... )
        >>>
        >>> # Create node with registry
        >>> container = ModelONEXContainer()
        >>> node = NodePatternDemotionEffect(container, registry)
        >>>
        >>> # Execute
        >>> request = ModelDemotionCheckRequest(dry_run=False)
        >>> result = await node.execute(request)
    """

    is_stub: ClassVar[bool] = True

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
        self, request: ModelDemotionCheckRequest
    ) -> ModelDemotionCheckResult:
        """Execute the effect node to check and demote patterns.

        Delegates to the registry-wired handler function.

        Args:
            request: The demotion check request with criteria and options.

        Returns:
            ModelDemotionCheckResult with demotion outcomes.
        """
        handler = self._registry.check_and_demote
        return await handler(request)


__all__ = ["NodePatternDemotionEffect"]
