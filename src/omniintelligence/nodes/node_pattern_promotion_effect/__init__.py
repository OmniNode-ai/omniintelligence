# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Promotion Effect node - OMN-1680.

This node handles automatic promotion of provisional patterns to validated
status based on rolling window success metrics. Supports dry_run mode for
previewing promotions without committing changes.

Published Events:
    - onex.evt.omniintelligence.pattern-promoted.v1

Example:
    ```python
    from omnibase_core.models.container import ModelONEXContainer
    from omniintelligence.nodes.node_pattern_promotion_effect import (
        NodePatternPromotionEffect,
        ModelPromotionCheckRequest,
    )
    from omniintelligence.nodes.node_pattern_promotion_effect.registry import (
        RegistryPatternPromotionEffect,
    )

    # Create registry with wired dependencies
    registry = RegistryPatternPromotionEffect.create_registry(
        repository=pattern_repo,
        producer=kafka_producer,
    )

    # Create and configure node
    container = ModelONEXContainer()
    effect = NodePatternPromotionEffect(container, registry)

    # Check and promote patterns
    request = ModelPromotionCheckRequest(dry_run=False)
    result = await effect.execute(request)
    ```
"""

from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_promotion import (
    ProtocolKafkaPublisher,
    ProtocolPatternRepository,
)
from omniintelligence.nodes.node_pattern_promotion_effect.introspection import (
    PatternPromotionErrorCode,
    PatternPromotionIntrospection,
    PatternPromotionMetadataLoader,
    get_introspection_response,
)
from omniintelligence.nodes.node_pattern_promotion_effect.models import (
    ModelGateSnapshot,
    ModelPatternPromotedEvent,
    ModelPromotionCheckRequest,
    ModelPromotionCheckResult,
    ModelPromotionResult,
)
from omniintelligence.nodes.node_pattern_promotion_effect.node import (
    NodePatternPromotionEffect,
)
from omniintelligence.nodes.node_pattern_promotion_effect.registry import (
    RegistryPatternPromotionEffect,
    ServiceHandlerRegistry,
)

__all__ = [
    # Models
    "ModelGateSnapshot",
    "ModelPatternPromotedEvent",
    "ModelPromotionCheckRequest",
    "ModelPromotionCheckResult",
    "ModelPromotionResult",
    # Node
    "NodePatternPromotionEffect",
    # Introspection
    "PatternPromotionErrorCode",
    "PatternPromotionIntrospection",
    "PatternPromotionMetadataLoader",
    # Protocols (re-exported from handlers)
    "ProtocolKafkaPublisher",
    "ProtocolPatternRepository",
    # Registry
    "RegistryPatternPromotionEffect",
    "ServiceHandlerRegistry",
    "get_introspection_response",
]
