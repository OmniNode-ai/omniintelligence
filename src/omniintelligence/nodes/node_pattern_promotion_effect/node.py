# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Promotion Effect - Thin shell node for pattern promotion.

This node follows the ONEX declarative pattern:
    - EFFECT node for database writes (pattern status updates) and Kafka events
    - Lightweight shell (~30 lines) that delegates to registry-wired handlers
    - No setters, no try/except, no logging in node class
    - Pattern: "Contract-driven, handlers wired externally via registry"

The node is initialized with a ServiceHandlerRegistry that contains handlers
with their dependencies (repository, producer) already bound. All error handling,
logging, and business logic resides in the handler functions.

Reference:
    - OMN-1680: Auto-promote logic for provisional patterns
    - OMN-1678: Rolling window metrics (dependency)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_effect import NodeEffect

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer
    from omniintelligence.nodes.node_pattern_promotion_effect.models import (
        ModelPromotionCheckRequest,
        ModelPromotionCheckResult,
    )
    from omniintelligence.nodes.node_pattern_promotion_effect.registry import (
        ServiceHandlerRegistry,
    )


class NodePatternPromotionEffect(NodeEffect):
    """Effect node for promoting provisional patterns to validated status.

    This is a declarative thin shell - all business logic is in the handler.
    The node simply delegates to the registry-wired handler function.

    Example:
        >>> from omnibase_core.models.container import ModelONEXContainer
        >>> from omniintelligence.nodes.node_pattern_promotion_effect import (
        ...     NodePatternPromotionEffect,
        ... )
        >>> from omniintelligence.nodes.node_pattern_promotion_effect.registry import (
        ...     RegistryPatternPromotionEffect,
        ... )
        >>>
        >>> # Create registry with wired dependencies
        >>> registry = RegistryPatternPromotionEffect.create_registry(
        ...     repository=pattern_repo,
        ...     producer=kafka_producer,
        ... )
        >>>
        >>> # Create node with registry
        >>> container = ModelONEXContainer()
        >>> node = NodePatternPromotionEffect(container, registry)
        >>>
        >>> # Execute
        >>> request = ModelPromotionCheckRequest(dry_run=False)
        >>> result = await node.execute(request)
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
        self, request: ModelPromotionCheckRequest
    ) -> ModelPromotionCheckResult:
        """Execute the effect node to check and promote patterns.

        Delegates to the registry-wired handler function.

        Args:
            request: The promotion check request with criteria and options.

        Returns:
            ModelPromotionCheckResult with promotion outcomes.
        """
        handler = self._registry.check_and_promote
        return await handler(request)


__all__ = ["NodePatternPromotionEffect"]
