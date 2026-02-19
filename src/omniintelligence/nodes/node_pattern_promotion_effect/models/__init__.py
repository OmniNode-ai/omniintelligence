"""Models for pattern_promotion_effect.

This module exports all input and output models for the pattern promotion
effect node, which checks and promotes eligible provisional patterns to
validated status based on rolling window success metrics.
"""

# Import ModelGateSnapshot from shared domain to avoid circular imports
# Re-export for backward compatibility
from omniintelligence.models.domain import ModelGateSnapshot
from omniintelligence.nodes.node_pattern_promotion_effect.models.model_pattern_promoted_event import (
    ModelPatternPromotedEvent,
)
from omniintelligence.nodes.node_pattern_promotion_effect.models.model_promotion_check_result import (
    ModelPromotionCheckResult,
)
from omniintelligence.nodes.node_pattern_promotion_effect.models.model_promotion_request import (
    ModelPromotionCheckRequest,
)
from omniintelligence.nodes.node_pattern_promotion_effect.models.model_promotion_result import (
    ModelPromotionResult,
)

__all__ = [
    # Gate snapshot and event models
    "ModelGateSnapshot",
    "ModelPatternPromotedEvent",
    # Request and result models
    "ModelPromotionCheckRequest",
    "ModelPromotionCheckResult",
    "ModelPromotionResult",
]
