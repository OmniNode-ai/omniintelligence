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
    from omniintelligence.nodes.pattern_promotion_effect import (
        NodePatternPromotionEffect,
        ModelPromotionCheckRequest,
    )

    # Create and configure node
    container = ModelONEXContainer()
    effect = NodePatternPromotionEffect(container)
    effect.set_repository(pattern_repo)
    effect.set_kafka_producer(kafka_producer)

    # Check and promote patterns
    request = ModelPromotionCheckRequest(dry_run=False)
    result = await effect.execute(request)
    ```
"""

from omniintelligence.nodes.pattern_promotion_effect.handlers.handler_promotion import (
    ProtocolKafkaPublisher,
    ProtocolPatternRepository,
)
from omniintelligence.nodes.pattern_promotion_effect.introspection import (
    PatternPromotionErrorCode,
    PatternPromotionIntrospection,
    PatternPromotionMetadataLoader,
    get_introspection_response,
)
from omniintelligence.nodes.pattern_promotion_effect.models import (
    ModelGateSnapshot,
    ModelPatternPromotedEvent,
    ModelPromotionCheckRequest,
    ModelPromotionCheckResult,
    ModelPromotionResult,
)
from omniintelligence.nodes.pattern_promotion_effect.node import (
    NodePatternPromotionEffect,
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
    "get_introspection_response",
]
